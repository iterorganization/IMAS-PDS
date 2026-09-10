"""
MUSCLE3 actor rebasing a controller's reference trace onto a NICE-inverse
solution at the workflow start time.

Why this exists
---------------
``metis_nice_evol_from_dina``'s magnetic controller
(``controllers/KCURR_RZIp/muscle_controller_NICE_IMAS_iter_init.m``) reads its
whole reference trajectory once, from its two F_INIT ports, and never re-reads
it (its S ports carry measurements only)::

    equilibrium.time                                    -> Simulink StartTime/StopTime
    time_slice{i}.global_quantities.ip            (abs) -> Ipl_ref  timeseries  (:104,:115)
    time_slice{i}.boundary.geometric_axis.r             -> Rpl_ref  timeseries  (:105,:125)
    time_slice{i}.boundary.geometric_axis.z             -> Zpl_ref  timeseries  (:106,:126)
    pf_active.coil{i}.current.data                      -> CSPF_curr_ref        (:82,:116)
    pf_active.coil{i}.resistance                        -> CSPF_volt_cmd_FF     (:83,:118)

Those references come from the DINA scenario (``source_nice``), while the
plant the controller drives is started from NICE's own inverse solve at the
first time of the run.  The two disagree by a few percent at t0, and the
current loop answers that offset with saturated coil voltages on the very
first steps -- the flux kick that threw NICE's evolutive solve into NaN
(2026-09-04).

Wiring the bare ``nice_inv`` output into the controller's F_INIT instead does
not work either: ``nice_inv`` produces a *single* time slice, whereas the
controller needs the whole trace (it takes ``time(1)``/``time(end)`` as the
Simulink start/stop times and builds one timeseries per reference).

This actor keeps the scenario trace -- its shape, its time base, its length --
and merely *rebases* it so that at t0 it agrees exactly with the NICE inverse
solution, exactly as the JT-60SA simulator does::

    X_ff(t) = X_src(t) - X_src(t0) + X_nice(t0)

applied to every quantity the controller actually reads: per-coil
feed-forward currents, the plasma-current reference and the plasma-position
references.  ``X_src(t0)`` is interpolated linearly (``numpy.interp``, which
clamps outside the source range) in each IDS's own time base, so the actor is
safe when t0 falls on, before or after the first scenario sample.

What is *not* rebased
---------------------
Nothing else is touched.  In particular no flux quantity is shifted: the
controller reads no ``psi`` (neither ``psi_boundary`` nor ``profiles_1d.psi``)
from its F_INIT ports -- verified in
``muscle_controller_NICE_IMAS_iter_init.m`` (the F_INIT block, lines 67-126)
and in ``muscle_IDS_NICE_output.m`` (the S block, lines 89-96).  Coil
resistances are references only in the sense that the controller multiplies
them by the *rebased* current, so they need no shift of their own.

Position references and the controller's fallback chain
-------------------------------------------------------
``geo_ref_with_fallback`` (init script, lines 153-179) falls back from
``boundary.geometric_axis.<f>`` to the boundary-outline midpoint and then to
``global_quantities.magnetic_axis.<f>`` when the primary value is empty or
carries IMAS's empty-float sentinel.  This actor evaluates *the same* chain on
both the scenario slice and the NICE slice, shifts the resulting effective
values, and writes the result back into ``boundary.geometric_axis`` -- so the
controller reads a valid geometric axis directly and its fallback never fires.
The outline itself is left untouched.

Ports
-----
F_INIT
    ``equilibrium_in``      -- scenario equilibrium trace (from ``source_nice``)
    ``pf_active_in``        -- scenario pf_active trace   (from ``source_nice``)
    ``equilibrium_ref_in``  -- NICE inverse equilibrium at t0 (from ``nice_inv``)
    ``pf_active_ref_in``    -- NICE inverse pf_active at t0   (from ``nice_inv``)
O_F
    ``equilibrium_out``     -- rebased equilibrium trace
    ``pf_active_out``       -- rebased pf_active trace

A ``*_ref_in`` port left unconnected turns its channel into a plain
passthrough (logged as a warning); a ``*_out`` port whose matching ``*_in`` is
unconnected is a configuration error.

Settings (all optional)
-----------------------
``rebase_currents`` (bool, default ``true``)
    Shift ``pf_active.coil[].current.data``.
``rebase_ip`` (bool, default ``true``)
    Shift ``equilibrium.time_slice[].global_quantities.ip``.
``rebase_position`` (bool, default ``true``)
    Shift ``equilibrium.time_slice[].boundary.geometric_axis.r/.z``.
``shift_mode`` (str, default ``additive``)
    ``additive`` applies the formula above; ``none`` makes the actor a pure
    passthrough (for A/B debugging without rewiring the workflow).

Notes on the NICE-inverse payload
---------------------------------
``nice_imas_inv_muscle3`` copies its *input* ``pf_active`` through and replaces
only ``coil(i).current.data(0)`` with the solved current, so the reference
currents are read at index 0 and the coil list (names and order) is whatever
``source_nice`` sent -- name matching therefore succeeds, and the index
fallback below is only a safety net.  Its ``equilibrium`` output carries one
solved time slice; slice 0 is used, and t0 is that slice's time (falling back
to the message timestamp).
"""

import logging
from typing import Any

import numpy as np
from imas_muscle3.utils import ids_from_message
from libmuscle import Instance, Message
from ymmsl import Operator

logger = logging.getLogger()

# IMAS's empty-float sentinel is -9e40; anything beyond this magnitude (or not
# finite) counts as "not filled", same test as the controller's
# geo_ref_with_fallback.
EMPTY_FLOAT_THRESHOLD = 1e30

CHANNELS = ("equilibrium", "pf_active")

# t0 falling just outside a source range is normal (the run's start time need not
# coincide with a scenario sample) and identical for every coil, so the clamping
# notice is emitted once per process, like the controller's own fallback warning.
_clamp_warned = False


def _is_unset(value: float | None) -> bool:
    """True when a scalar is absent or carries IMAS's empty-float sentinel."""
    if value is None:
        return True
    val = float(value)
    return not np.isfinite(val) or abs(val) > EMPTY_FLOAT_THRESHOLD


def _slice_times(equilibrium) -> np.ndarray:
    """Time base of an equilibrium's slices, homogeneous or not."""
    times = np.asarray(equilibrium.time, dtype=float)
    if times.size == len(equilibrium.time_slice):
        return times
    return np.array(
        [float(time_slice.time) for time_slice in equilibrium.time_slice],
        dtype=float,
    )


def _coil_times(pf_active, coil) -> np.ndarray:
    """Time base of one coil's current trace, homogeneous or not."""
    times = np.asarray(coil.current.time, dtype=float)
    if times.size:
        return times
    return np.asarray(pf_active.time, dtype=float)


def _interp(t0: float, times: np.ndarray, values: np.ndarray) -> float:
    """Linear interpolation clamped to the ends of `times`.

    numpy.interp already clamps, which is exactly the behaviour wanted when t0
    sits on or just outside the first scenario sample (``source_nice.t_min``
    trims the trace, and METIS's start time need not coincide with a DINA
    sample).
    """
    if values.size == 0:
        raise ValueError("empty value array")
    if values.size == 1 or times.size != values.size:
        return float(values[0])
    global _clamp_warned
    if (t0 < times[0] or t0 > times[-1]) and not _clamp_warned:
        logger.warning(
            "t0 = %g s is outside the source range [%g, %g] s -- clamping "
            "to the nearest end point (reported once)",
            t0,
            times[0],
            times[-1],
        )
        _clamp_warned = True
    return float(np.interp(t0, times, values))


def _effective_axis(time_slice, field: str) -> tuple[float, str]:
    """Plasma-position reference the controller would read, and its origin.

    Mirrors geo_ref_with_fallback in
    muscle_controller_NICE_IMAS_iter_init.m: geometric_axis, then the boundary
    outline midpoint, then the magnetic axis.
    """
    value = getattr(time_slice.boundary.geometric_axis, field)
    if not _is_unset(value):
        return float(value), "geometric_axis"
    outline = np.asarray(getattr(time_slice.boundary.outline, field), dtype=float)
    if outline.size:
        return float((outline.max() + outline.min()) / 2.0), "outline midpoint"
    return (
        float(getattr(time_slice.global_quantities.magnetic_axis, field)),
        "magnetic_axis",
    )


def _t0_from(equilibrium, fallback: float) -> float:
    """Time of the NICE-inverse slice: its own timestamp, else the message's."""
    times = np.asarray(equilibrium.time, dtype=float)
    if times.size and not _is_unset(times[0]):
        return float(times[0])
    if len(equilibrium.time_slice):
        candidate = equilibrium.time_slice[0].time
        if not _is_unset(candidate):
            return float(candidate)
    return float(fallback)


def rebase_pf_active(source, reference, t0: float) -> None:
    """Shift every coil's current trace onto the NICE solution at t0.

    ``source`` is modified in place:
    ``I(t) <- I(t) + I_nice(t0) - I_src(t0)``, per coil, matched by name and
    falling back to position in the coil list when the names differ.
    """
    ref_coils: dict[str, Any] = {}
    for coil in reference.coil:
        name = str(coil.name).strip()
        if name:
            ref_coils[name] = coil

    by_name = len(ref_coils) == len(reference.coil) and all(
        str(coil.name).strip() in ref_coils for coil in source.coil
    )
    if not by_name:
        logger.warning(
            "pf_active coil names do not match one-to-one between the "
            "scenario trace and the NICE-inverse solution -- falling back to "
            "matching by index (scenario: %s; NICE: %s)",
            [str(c.name) for c in source.coil],
            [str(c.name) for c in reference.coil],
        )

    for index, coil in enumerate(source.coil):
        name = str(coil.name).strip() or f"coil[{index}]"
        if by_name:
            ref_coil = ref_coils[str(coil.name).strip()]
        elif index < len(reference.coil):
            ref_coil = reference.coil[index]
        else:
            logger.warning(
                "no NICE-inverse counterpart for coil %s -- left unshifted", name
            )
            continue

        data = np.asarray(coil.current.data, dtype=float)
        ref_data = np.asarray(ref_coil.current.data, dtype=float)
        if data.size == 0 or ref_data.size == 0:
            logger.warning(
                "coil %s has no current data on one side -- left unshifted", name
            )
            continue
        # NICE writes the solved current at index 0 of the pf_active it copies
        # through, whatever the length of that copied trace.
        i_nice = float(ref_data[0])
        i_src = _interp(t0, _coil_times(source, coil), data)
        shift = i_nice - i_src
        coil.current.data = data + shift
        logger.info(
            "pf_active %-42s I_src(t0)=%+12.6g A  I_nice(t0)=%+12.6g A  "
            "shift=%+12.6g A",
            name,
            i_src,
            i_nice,
            shift,
        )


def rebase_equilibrium(
    source, reference, t0: float, rebase_ip: bool, rebase_position: bool
) -> None:
    """Shift the plasma-current and plasma-position references onto NICE's.

    ``source`` is modified in place; every other field (time base, number of
    slices, profiles, boundary outline, ...) is left exactly as received.
    """
    if not len(reference.time_slice):
        logger.warning(
            "the NICE-inverse equilibrium carries no time slice -- "
            "equilibrium left unshifted"
        )
        return
    ref_slice = reference.time_slice[0]
    if len(reference.time_slice) > 1:
        logger.info(
            "the NICE-inverse equilibrium carries %d slices; using slice 0 "
            "(t = %g s) as the reference",
            len(reference.time_slice),
            t0,
        )

    times = _slice_times(source)

    if rebase_ip:
        ip_values = np.array(
            [
                float(time_slice.global_quantities.ip)
                for time_slice in source.time_slice
            ],
            dtype=float,
        )
        ip_src = _interp(t0, times, ip_values)
        ip_nice = float(ref_slice.global_quantities.ip)
        if ip_src * ip_nice < 0.0:
            logger.warning(
                "the scenario and NICE plasma currents have opposite signs at "
                "t0 (%+.6g A vs %+.6g A) -- the additive shift is applied on "
                "the signed values, check the COCOS convention",
                ip_src,
                ip_nice,
            )
        shift = ip_nice - ip_src
        for time_slice, value in zip(source.time_slice, ip_values, strict=False):
            time_slice.global_quantities.ip = value + shift
        logger.info(
            "equilibrium %-42s ip_src(t0)=%+12.6g A  ip_nice(t0)=%+12.6g A  "
            "shift=%+12.6g A",
            "global_quantities.ip",
            ip_src,
            ip_nice,
            shift,
        )

    if rebase_position:
        for field in ("r", "z"):
            effective = np.array(
                [_effective_axis(ts, field)[0] for ts in source.time_slice],
                dtype=float,
            )
            src_value = _interp(t0, times, effective)
            nice_value, nice_origin = _effective_axis(ref_slice, field)
            shift = nice_value - src_value
            for time_slice, value in zip(source.time_slice, effective, strict=False):
                setattr(time_slice.boundary.geometric_axis, field, value + shift)
            logger.info(
                "equilibrium %-42s src(t0)=%+12.6g m  nice(t0)=%+12.6g m  "
                "shift=%+12.6g m  (NICE value from %s)",
                f"boundary.geometric_axis.{field}",
                src_value,
                nice_value,
                shift,
                nice_origin,
            )


def _connected(instance: Instance, port: str) -> bool:
    return instance.is_connected(port)


def main() -> None:
    ports = {
        Operator.F_INIT: (
            [f"{channel}_in" for channel in CHANNELS]
            + [f"{channel}_ref_in" for channel in CHANNELS]
        ),
        Operator.O_F: [f"{channel}_out" for channel in CHANNELS],
    }
    instance = Instance(ports)

    while instance.reuse_instance():
        active: list[str] = [
            channel for channel in CHANNELS if _connected(instance, f"{channel}_in")
        ]
        for channel in CHANNELS:
            if _connected(instance, f"{channel}_out") and channel not in active:
                raise RuntimeError(
                    f"'{channel}_out' is connected but '{channel}_in' is not -- "
                    "an output channel needs its matching input wired."
                )
        if not active:
            raise RuntimeError(
                "none of "
                + ", ".join(f"{channel}_in" for channel in CHANNELS)
                + " is connected -- nothing to rebase."
            )

        shift_mode = instance.get_setting("shift_mode", "str", default="additive")
        if shift_mode not in ("additive", "none"):
            raise ValueError(
                f"shift_mode must be 'additive' or 'none', got {shift_mode!r}"
            )
        rebase_currents = instance.get_setting("rebase_currents", "bool", default=True)
        rebase_ip = instance.get_setting("rebase_ip", "bool", default=True)
        rebase_position = instance.get_setting("rebase_position", "bool", default=True)
        logger.info(
            "active channels: %s; shift_mode=%s, rebase_currents=%s, "
            "rebase_ip=%s, rebase_position=%s",
            active,
            shift_mode,
            rebase_currents,
            rebase_ip,
            rebase_position,
        )

        messages = {}
        sources = {}
        references = {}
        ref_messages = {}
        for channel in active:
            message = instance.receive(f"{channel}_in")
            messages[channel] = message
            sources[channel] = ids_from_message(channel, message.data)
            ref_port = f"{channel}_ref_in"
            if _connected(instance, ref_port):
                ref_message = instance.receive(ref_port)
                ref_messages[channel] = ref_message
                references[channel] = ids_from_message(channel, ref_message.data)
            else:
                logger.warning(
                    "'%s' is not connected -- forwarding the %s trace unchanged",
                    ref_port,
                    channel,
                )

        # t0 is the time of the NICE-inverse slice: the reference equilibrium
        # carries it in its own time array, the reference pf_active only
        # echoes the scenario time base, so fall back to the timestamp of the
        # message NICE sent rather than to any scenario time.
        t0: float | None = None
        if "equilibrium" in references:
            t0 = _t0_from(
                references["equilibrium"], ref_messages["equilibrium"].timestamp
            )
        elif ref_messages:
            t0 = float(ref_messages[next(iter(ref_messages))].timestamp)
        if t0 is not None:
            logger.info("rebasing the controller references onto t0 = %g s", t0)

        if shift_mode == "none":
            logger.warning("shift_mode='none' -- forwarding both traces unchanged")
        else:
            if rebase_currents and "pf_active" in sources and "pf_active" in references:
                if t0 is None:
                    raise RuntimeError(
                        "t0 could not be determined even though a NICE-inverse "
                        "pf_active reference was received -- this should not happen"
                    )
                rebase_pf_active(sources["pf_active"], references["pf_active"], t0)
            if (
                (rebase_ip or rebase_position)
                and "equilibrium" in sources
                and "equilibrium" in references
            ):
                if t0 is None:
                    raise RuntimeError(
                        "t0 could not be determined even though a NICE-inverse "
                        "equilibrium reference was received -- this should not happen"
                    )
                rebase_equilibrium(
                    sources["equilibrium"],
                    references["equilibrium"],
                    t0,
                    rebase_ip,
                    rebase_position,
                )

        for channel in active:
            port = f"{channel}_out"
            if not _connected(instance, port):
                continue
            message = messages[channel]
            instance.send(
                port,
                Message(
                    message.timestamp,
                    next_timestamp=message.next_timestamp,
                    data=sources[channel].serialize(),
                ),
            )


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    main()
