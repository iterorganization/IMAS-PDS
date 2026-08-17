"""Outer Picard driver as a MUSCLE3 submodel: one full-pulse exchange per iteration.

Each iteration sends a whole-trace pulse on the O_I ports (designed target, core_profiles)
and receives one on the S ports (coils from NICE, evolved equilibrium + core_profiles from
TORAX). It restores the prescribed boundary outline on the evolved equilibrium and iterates
until the max coil-current change drops below `tolerance`, or its relative change stalls
below `rel_tolerance`. The driver only paces the iteration; the coupling itself is a
pipeline (loop -> waveform_editor -> nice -> torax -> loop).

The boundary is held from the input IDS until a shape editor is wired in; Ip is held by the
waveform_editor. Both the equilibrium target and core_profiles reach TORAX via
`waveform_editor` -- the equilibrium drives its export time base, core_profiles is mirrored
through unchanged.

Three things deliberately never travel around the loop, because they do not change between
iterations: the static machine description (wall, pf_passive, iron_core) and the
coil-current seed, both re-exported by `waveform_editor` straight to NICE. Only the
pf_active NICE *returns* flows through the loop, since that is what convergence watches.
"""

import logging

import numpy as np
from imas import DBEntry, IDSFactory
from imas.ids_defs import CLOSEST_INTERP
from imas_muscle3.utils import get_setting_optional
from libmuscle import Instance, Message
from ymmsl import Operator

logger = logging.getLogger()
IDS_LIST = ["equilibrium", "core_profiles"]
S_LIST = ["equilibrium", "core_profiles", "pf_active"]


def _split(trace, name, times):
    # Skip any t whose CLOSEST_INTERP result has a time already in the list; this prevents
    # duplicate timestamps when a downstream solver (e.g. TORAX) produces fewer output
    # slices than the input and the last slice is reused for many requested times.
    with DBEntry("imas:memory?path=/", "w") as db:
        ids = IDSFactory().new(name)
        ids.deserialize(trace)
        db.put(ids)
        slices, seen = [], set()
        for t in times:
            s = db.get_slice(name, t, CLOSEST_INTERP)
            actual_t = float(s.time[0])
            if actual_t in seen:
                continue
            seen.add(actual_t)
            slices.append(s.serialize())
        return slices


def _assemble(slices, name):
    with DBEntry("imas:memory?path=/", "w") as db:
        for s in slices:
            ids = IDSFactory().new(name)
            ids.deserialize(s)
            db.put_slice(ids)
        return db.get(name).serialize()


def _hold_boundary(evolved_ser, ref_ser):
    """Restore the prescribed boundary outline on an evolved slice; keep its profiles.

    Ip is no longer held here -- the waveform editor overlays it on the forward pass.
    """
    ev = IDSFactory().new("equilibrium")
    ev.deserialize(evolved_ser)
    rf = IDSFactory().new("equilibrium")
    rf.deserialize(ref_ser)
    es, rs = ev.time_slice[0], rf.time_slice[0]
    es.boundary.outline.r = rs.boundary.outline.r
    es.boundary.outline.z = rs.boundary.outline.z
    return ev.serialize()


MU0 = 4e-7 * np.pi
R0, A_MINOR = 6.2, 2.0  # ITER scale lengths, used only to size the cold-start guess


def _cold_equilibrium(ser):
    """Replace the DINA profile state on one target slice with a neutral guess.

    The design part of the slice (time, boundary outline, Ip) is kept; the
    profiles_1d state the waveform editor forwards to NICE (psi, dpressure_dpsi,
    f_df_dpsi) is replaced by a generic low-beta guess: a linear psi coordinate
    spanning the internal flux of a li~1 current channel at this slice's Ip, and
    (1 - psi_norm) shaped p'/ff'. Only the sign conventions (one bit each) and the
    boundary-flux anchor (one scalar, the design gauge -- without it TORAX evolves
    the whole pulse ~100 Wb off the DINA level and every psi plot shifts) are taken
    from the DINA slice, so no profile information survives; NICE rescales the
    amplitude pair to match Ip (algoWithIp), so only the shapes and the p'/ff'
    ratio (~beta_p 0.05 here) matter.
    """
    eq = IDSFactory().new("equilibrium")
    eq.deserialize(ser)
    ts = eq.time_slice[0]
    p1 = ts.profiles_1d
    ip = abs(float(ts.global_quantities.ip))
    s_psi = 1.0 if p1.psi[-1] >= p1.psi[0] else -1.0
    s_ffp = -1.0 if np.mean(p1.f_df_dpsi) < 0 else 1.0
    psib = (
        float(ts.global_quantities.psi_boundary)
        if ts.global_quantities.psi_boundary.has_value
        else float(p1.psi[-1])
    )
    dpsi = 0.5 * MU0 * R0 * ip
    # Keep the original grid size: the slice's other profiles_1d arrays (psi_norm,
    # pressure, q, ...) are coordinated on psi, so resizing psi would invalidate them.
    x = np.linspace(0.0, 1.0, len(p1.psi))
    b_pol = MU0 * ip / (2 * np.pi * A_MINOR)
    p_axis = 0.05 * b_pol**2 / MU0
    p1.psi = psib - s_psi * dpsi * (1.0 - x)
    if p1.psi_norm.has_value:
        p1.psi_norm = x.copy()
    p1.dpressure_dpsi = -2 * p_axis * (1 - x) / (s_psi * dpsi)
    p1.f_df_dpsi = s_ffp * MU0 * R0 * ip / (np.pi * A_MINOR**2) * (1 - x)
    return eq.serialize()


def _cold_core_profiles(ser):
    """Same, for one core_profiles slice: generic parabolic Te/Ti (2 keV core,
    100 eV edge), flat-current parabolic psi(rho) sized like _cold_equilibrium
    and anchored on the slice's own edge flux (the design gauge -- TORAX keeps
    its initial psi level for the whole pulse), v_loop zeroed. Density is
    deliberately kept: with evolve_density=False it is a prescription of the run
    (like Ip or the heating), not an evolved initial state, so removing it would
    change the physics target rather than the start.
    """
    cp = IDSFactory().new("core_profiles")
    cp.deserialize(ser)
    p1 = cp.profiles_1d[0]
    ip = abs(float(cp.global_quantities.ip[0]))
    rho = np.asarray(p1.grid.rho_tor_norm)
    s_psi = 1.0 if p1.grid.psi[-1] >= p1.grid.psi[0] else -1.0
    psib = float(p1.grid.psi[-1])
    te = 100.0 + 1900.0 * (1 - rho**2)
    p1.grid.psi = psib - s_psi * 0.5 * MU0 * R0 * ip * (1 - rho**2)
    p1.electrons.temperature = te
    p1.t_i_average = te.copy()
    if cp.global_quantities.v_loop.has_value:
        cp.global_quantities.v_loop = np.zeros(len(cp.global_quantities.v_loop))
    return cp.serialize()


def _coils(pf_trace):
    pf = IDSFactory().new("pf_active")
    pf.deserialize(pf_trace)
    return np.array([[c.current.data[i] for c in pf.coil] for i in range(len(pf.time))])


def main() -> None:
    inst = Instance(
        {
            Operator.F_INIT: [f"{lane}_in_f" for lane in IDS_LIST],
            Operator.O_I: [f"{lane}_out_i" for lane in IDS_LIST],
            Operator.S: [f"{lane}_in_s" for lane in S_LIST],
            Operator.O_F: [
                "equilibrium_out_f",
                "pf_active_out_f",
                "core_profiles_out_f",
                "equilibrium_target_out_f",
            ],
        }
    )
    while inst.reuse_instance():
        max_iter = int(get_setting_optional(inst, "max_iterations", 4))
        tol = float(get_setting_optional(inst, "tolerance", 1e3))
        rel_tol = float(get_setting_optional(inst, "rel_tolerance", 0.03))
        max_slices = int(get_setting_optional(inst, "max_slices", 0))
        cold_start = bool(get_setting_optional(inst, "cold_start", False))
        t_min = get_setting_optional(inst, "t_min")
        t_max = get_setting_optional(inst, "t_max")

        init = {lane: inst.receive(f"{lane}_in_f").data for lane in IDS_LIST}
        eq_ids = IDSFactory().new("equilibrium")
        eq_ids.deserialize(init["equilibrium"])
        times = [float(t) for t in eq_ids.time]
        if t_min is not None:
            times = [t for t in times if t >= float(t_min)]
        if t_max is not None:
            times = [t for t in times if t <= float(t_max)]
        if max_slices:
            times = times[:max_slices]
        boundary = _split(init["equilibrium"], "equilibrium", times)
        cp_slices = _split(init["core_profiles"], "core_profiles", times)
        if cold_start:
            # No DINA warm start: iteration 0 gets a generic, Ip-scaled state. `boundary`
            # is replaced too, so the padding path cannot reintroduce DINA profiles.
            logger.info(
                "cold_start: replacing the DINA initial state with generic profiles"
            )
            boundary = [_cold_equilibrium(s) for s in boundary]
            cp_slices = [_cold_core_profiles(s) for s in cp_slices]
        cp = _assemble(cp_slices, "core_profiles")
        t0 = times[0]
        target = _assemble(boundary, "equilibrium")
        prev = None
        prev_dI = None
        torax_eq = coilr = None

        # A pruned `transport` hole leaves these S ports unconnected, and receiving on an
        # unconnected port blocks forever.
        transport_connected = (
            inst.is_connected("equilibrium_in_s") and inst.is_connected("core_profiles_in_s"))

        for it in range(max_iter):
            # --- O_I: emit the full pulse (no receives yet) ---
            inst.send(
                "equilibrium_out_i", Message(t0, data=target)
            )  # -> waveform_editor (+Ip) -> nice
            inst.send(
                "core_profiles_out_i", Message(t0, data=cp)
            )  # -> waveform_editor -> torax

            # --- S: receive the full pulse (coils from nice, evolved state from torax) ---
            coilr = inst.receive("pf_active_in_s").data

            if not transport_connected:
                # Nothing to iterate against: NICE has solved the prescribed boundary
                # once, so keep `target`/`cp` and stop after this pass.
                logger.info("no transport connected: single pass, emitting the design target")
                break

            torax_eq = inst.receive("equilibrium_in_s").data
            torax_cp = inst.receive("core_profiles_in_s").data

            cur = _coils(coilr)
            dI = None if prev is None else float(np.max(np.abs(cur - prev)))
            logger.info(
                "iter %d: NICE+TORAX done (%d slices), max|dI|=%s", it, len(times), dI
            )
            prev = cur

            ev = _split(torax_eq, "equilibrium", times)
            if len(ev) < len(boundary):
                logger.info(
                    "iter %d: TORAX covered %d/%d slices; padding remaining from boundary",
                    it,
                    len(ev),
                    len(boundary),
                )
                ev = ev + boundary[len(ev) :]
            target = _assemble(
                [_hold_boundary(ev[i], boundary[i]) for i in range(len(ev))],
                "equilibrium",
            )
            cp = _assemble(_split(torax_cp, "core_profiles", times), "core_profiles")

            stalled = False
            if dI is not None and prev_dI is not None and prev_dI != 0:
                rel_change = abs(dI - prev_dI) / prev_dI
                stalled = rel_change < rel_tol
                if stalled:
                    logger.info(
                        "iter %d: relative change in max|dI| = %.4f < %.4f, stalled",
                        it,
                        rel_change,
                        rel_tol,
                    )
            prev_dI = dI

            if dI is not None and dI < tol:
                logger.info("converged at iteration %d", it)
                break
            if stalled:
                logger.info("converged (stalled) at iteration %d", it)
                break
            if it == max_iter - 1:
                logger.info("reached max_iterations=%d", max_iter)
                break

        # With no transport there is no evolved equilibrium; the design target is the
        # only meaningful result, so send that on both lanes.
        final_eq = torax_eq if torax_eq is not None else target
        inst.send("equilibrium_out_f", Message(t0, data=final_eq))
        inst.send("pf_active_out_f", Message(t0, data=coilr))
        inst.send("core_profiles_out_f", Message(t0, data=cp))
        inst.send("equilibrium_target_out_f", Message(t0, data=target))
        logger.info("sent %d final slices", len(times))


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    main()
