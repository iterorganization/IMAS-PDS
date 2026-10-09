"""
Preprocessing of the DINA-derived data (equilibrium, core_profiles, core_sources
and the pf_active coil-current trace) into valid PDS coupling input.
"""

import contextlib
import copy
import logging

import numpy as np
from imas import convert_ids
from imas.ids_defs import CLOSEST_INTERP
from packaging.version import Version
from preprocess_machine_description import (
    _fix_pf_active_md_geometry,
    quiet_expected_conversion_drops,
)
from scipy.integrate import cumulative_trapezoid as cumtrapz
from scipy.interpolate import interp1d as interp1

logger = logging.getLogger(__name__)

DD_VERSION = "4.0.0"


# Two selected times closer than this are the same slice (written once).
DUPLICATE_TIME_TOL = 1e-9


def write_dina_data(
    db_out,
    db_in,
    db_sum,
    db_md_pf_active,
    n_timeslices=None,
    dt_step=None,
    report_window=None,
):
    """Write the data derived from the DINA source run: equilibrium, core_profiles and
    core_sources at the selected timeslices, plus a pf_active trace that merges DINA's
    actual coil currents onto machine-description geometry (kept for later validation
    plots comparing DINA's currents against NICE's inverse solution).

    The slices are selected by exactly one of ``n_timeslices`` (that many targets
    uniform over the viable range) or ``dt_step`` (one target every ``dt_step`` seconds
    from the first viable time), see find_interesting_time_slices. A selected slice
    whose time equals one already written (both picks walked forward onto the same raw
    sample) is written only once. ``report_window`` (t_start, t_end), optional, adds
    the number of slices inside that window to the summary line logged at the end.

    Returns the list of selected timeslices.
    """
    summary = db_sum.get("summary", autoconvert=False)
    time_array = summary.time
    interesting_time_slices = find_interesting_time_slices(
        summary, n_timeslices, dt_step=dt_step
    )
    skipped = []
    duplicates = []
    t_list = []

    for idx in interesting_time_slices:
        # equilibrium ids
        for i in range(10):
            if idx + i >= len(time_array):
                break
            t = time_array[idx + i]
            eq_orig = db_in.get_slice(
                "equilibrium",
                time_requested=t,
                interpolation_method=CLOSEST_INTERP,
                autoconvert=False,
            )
            if Version(eq_orig._dd_version) < Version(DD_VERSION):
                bndr_len = len(eq_orig.time_slice[0].boundary_separatrix.outline.r)
            else:
                bndr_len = len(eq_orig.time_slice[0].boundary.outline.r)
            if bndr_len >= 1:
                break
        if bndr_len == 0:
            skipped.append(t)
            continue
        if any(abs(t - t_done) <= DUPLICATE_TIME_TOL for t_done in t_list):
            duplicates.append(t)
            continue
        if Version(eq_orig._dd_version) < Version(DD_VERSION):
            eq_orig_ts = eq_orig.time_slice[0]

            # DINA input - NICE output defined at psi_norm:
            # profiles_1d.psi: 0..0.995 - 0..1
            # boundary: 0.995 - 1
            # boundary_separatrix: 1 - na
            # DINA fills boundary.geometric_axis.r but never .z; the PCSSP magnetic
            # controller uses geometric_axis.z as its vertical-position reference and
            # otherwise reads IMAS's empty-float sentinel (-9e40). Take the midpoints of
            # the ORIGINAL closed boundary outline (psi_norm 0.995 surface; its r midpoint
            # matches DINA's own geometric_axis.r to 1e-3) before it is replaced below by
            # the separatrix outline, whose open divertor legs (z down to -6 m) would put
            # the midpoint 1.5 m too low on diverted slices.
            r_out = np.asarray(eq_orig_ts.boundary.outline.r)
            z_out = np.asarray(eq_orig_ts.boundary.outline.z)
            if r_out.size == 0:
                r_out = np.asarray(eq_orig_ts.boundary_separatrix.outline.r)
                z_out = np.asarray(eq_orig_ts.boundary_separatrix.outline.z)
            if r_out.size:
                if not eq_orig_ts.boundary.geometric_axis.r.has_value:
                    eq_orig_ts.boundary.geometric_axis.r = (
                        r_out.min() + r_out.max()
                    ) / 2
                if not eq_orig_ts.boundary.geometric_axis.z.has_value:
                    eq_orig_ts.boundary.geometric_axis.z = (
                        z_out.min() + z_out.max()
                    ) / 2
            eq_orig_ts.boundary.psi = eq_orig_ts.boundary_separatrix.psi
            eq_orig_ts.boundary.outline.r = eq_orig_ts.boundary_separatrix.outline.r
            eq_orig_ts.boundary.outline.z = eq_orig_ts.boundary_separatrix.outline.z
        with quiet_expected_conversion_drops():
            eq = convert_ids(eq_orig, DD_VERSION)
        psi = eq.time_slice[0].profiles_1d.psi
        psi_a = psi[0]
        psi_b = eq.time_slice[0].boundary.psi
        eq.time_slice[0].profiles_1d.psi_norm = abs(psi - psi_a) / abs(psi_b - psi_a)
        db_out.put_slice(eq)

        # time dependent standard
        for ids_name, db in [
            ("core_profiles", db_in),
            ("core_sources", db_sum),
        ]:
            slice_orig = db.get_slice(
                ids_name,
                time_requested=t,
                interpolation_method=CLOSEST_INTERP,
                autoconvert=False,
            )
            with quiet_expected_conversion_drops():
                slice = convert_ids(slice_orig, DD_VERSION)
            _snap_rho_grid_end(slice, ids_name)
            db_out.put_slice(slice)
        t_list.append(t)

    preprocess_pf_active(db_out, db_in, db_md_pf_active, t_list)

    logger.info(
        "Following timeslices during preprocessing were not viable: %s", skipped
    )
    if duplicates:
        logger.warning(
            "time slices already written (two selections reached the same raw time),"
            " skipped: %s",
            ", ".join(f"{t:.4f} s" for t in duplicates),
        )
    logger.warning(
        "%s",
        selection_summary(
            t_list, summary, n_timeslices, dt_step, report_window=report_window
        ),
    )
    return t_list


def _viable_indices(sm):
    """Raw summary indices with magnetic axis R > 1 m and |Ip| > 50 kA."""
    R = sm.boundary.magnetic_axis_r.value
    ip = sm.global_quantities.ip.value
    return [i for i in range(len(R)) if R[i] > 1 and abs(ip[i]) > 50e3]


def _spacing(times):
    """'min/median/max = a/b/c s' of the intervals between consecutive times."""
    if len(times) < 2:
        return "spacing n/a (fewer than 2 slices)"
    d = np.diff(np.asarray(times, dtype=float))
    return f"spacing min/median/max = {d.min():.3f}/{np.median(d):.3f}/{d.max():.3f} s"


def selection_summary(t_list, sm, n_timeslices, dt_step, report_window=None):
    """One line describing the written time slices (for the preparation log)."""
    method = (
        f"dt_step={dt_step:g} s"
        if dt_step is not None
        else f"n_timeslices={n_timeslices}"
    )
    valid = _viable_indices(sm)
    if valid:
        t = sm.time
        viable = f"viable range {t[valid[0]]:.2f}..{t[valid[-1]]:.2f} s"
    else:
        viable = "no viable raw sample"
    line = f"time slices: {len(t_list)} written (method: {method}, {viable})"
    if report_window is None:
        return f"{line}; {_spacing(t_list)}"
    t0, t1 = report_window
    inside = [t for t in t_list if t0 <= t <= t1]
    return (
        f"{line}; {len(inside)} inside the simulation window [{t0:g}, {t1:g}] s;"
        f" {_spacing(inside)} in window"
    )


def preprocess_pf_active(db_out, db_in, db_md_pf_active, t_list):
    """
    Merge DINA's actual per-timeslice coil currents onto machine-description geometry
    (kept for later validation plots comparing DINA's currents against NICE's inverse
    solution -- not used by the waveform editor, see preprocess_pf_active_md):
    -size(time) was different from size(current.data) for coils 0 to 7, I corrected this
    """
    name_mismatches = set()
    layout = None
    for t in t_list:
        # pf_active ids
        slice_orig = db_in.get_slice(
            "pf_active",
            time_requested=t,
            interpolation_method=CLOSEST_INTERP,
            autoconvert=False,
        )
        slice_backup = db_md_pf_active.get_slice(
            "pf_active",
            time_requested=t,
            interpolation_method=CLOSEST_INTERP,
            autoconvert=False,
        )
        _fix_pf_active_md_geometry(slice_backup)

        # VS coils have incompatible geometry_type for NICE in input,
        # should be identical across shots so getting geometry from backup is fine
        with quiet_expected_conversion_drops():
            slice = convert_ids(slice_orig, DD_VERSION)
        if layout is None:
            # The coil layout does not change between slices: decide once.
            layout = _pf_active_layout(slice, slice_backup)
        if layout == "md14":
            for i, _coil in enumerate(slice.coil):
                if slice.coil[i].name != slice_backup.coil[i].name:
                    # Source (DINA-derived) and machine-description pf_active use
                    # different naming conventions (e.g. "CS3U" vs "Central Solenoid
                    # 3U (CS3U)", or "VS3U" vs "...(VSU)" -- not even a substring
                    # match). Coil order is fixed ITER machine geometry and lines up
                    # correctly by index (verified), so this is not a misalignment.
                    # Collected and reported once, rather than 14 lines per timeslice:
                    # at 41 slices that buried the rest of the output entirely.
                    name_mismatches.add(
                        (i, str(slice.coil[i].name), str(slice_backup.coil[i].name))
                    )
                # make sure geometry_type is nice compatible
                slice.coil[i].element[0].geometry = (
                    slice_backup.coil[i].element[0].geometry
                )
                # make sure resistance is filled
                slice.coil[i].resistance = slice_backup.coil[i].resistance
        else:
            # Older DINA runs (e.g. 105033) carry 12 coils with multi-element CS1
            # and VS3: convert onto the 14 machine-description coils following the
            # DINA developer's pf.py (update_pfa).
            _split_multi_element_coils(slice, slice_backup)

        db_out.put_slice(slice)

    if name_mismatches:
        logger.warning(
            "pf_active coil names differ between source and machine description for %d of"
            " %d coils; matched by index instead. e.g. %s",
            len(name_mismatches),
            len(slice.coil),
            ", ".join(
                f"[{i}] {a!r} vs {b!r}" for i, a, b in sorted(name_mismatches)[:2]
            ),
        )


def _pf_active_layout(slice, slice_backup):
    """Decide how the DINA pf_active maps onto the machine description (logged once).

    Returns "md14" when the DINA entry already has the machine description's coils,
    each with exactly one element (native 14-coil DINA run, or an entry already
    converted, e.g. by the DINA developer's pf.py): the coils are merged one to one.
    Returns "dina12" for the 12-coil layout of older DINA runs (CS1 and VS3 as
    two-element coils), converted by _split_multi_element_coils. Raises ValueError
    for any other layout.
    """
    n_src = len(slice.coil)
    n_md = len(slice_backup.coil)
    n_elements = [len(coil.element) for coil in slice.coil]
    if n_src == n_md == 14 and all(n == 1 for n in n_elements):
        logger.info(
            "pf_active: DINA entry already has the 14 single-element coils of the"
            " machine description; no 12->14 conversion"
        )
        return "md14"
    if n_src == 12 and n_md == 14:
        return "dina12"
    raise ValueError(
        f"pf_active: unsupported pf_active layout: DINA has {n_src} coils, the machine"
        f" description {n_md}; DINA coils (elements): "
        + ", ".join(
            f"{coil.name} ({n})"
            for coil, n in zip(slice.coil, n_elements, strict=False)
        )
    )


_RHO_SNAP_REPORTED = set()


def _snap_rho_grid_end(ids, ids_name):
    """Move the last rho_tor_norm grid node to exactly 1.0 when it is within 1 % of it.

    Older DINA runs (e.g. 105033) end their 50-point radial grid at rho_tor_norm =
    0.9964; TORAX requires a profile value at rho = 1.0 as boundary condition. Only the
    grid node is moved (profile values are left untouched), so the edge value already
    carried by the last node is simply declared at the boundary. Logged once per IDS.
    """
    if ids_name == "core_profiles":
        profiles_1d = list(ids.profiles_1d)
    elif ids_name == "core_sources":
        profiles_1d = [p for source in ids.source for p in source.profiles_1d]
    else:
        profiles_1d = []

    snapped_last = None
    for p in profiles_1d:
        grid = p.grid.rho_tor_norm
        if not grid.has_value or len(grid) == 0:
            continue
        last = float(grid[-1])
        if 0.99 <= last < 1.0:
            arr = np.array(grid, dtype=float)
            arr[-1] = 1.0
            p.grid.rho_tor_norm = arr
            snapped_last = last

    if snapped_last is not None and ids_name not in _RHO_SNAP_REPORTED:
        _RHO_SNAP_REPORTED.add(ids_name)
        logger.warning(
            "%s: last rho_tor_norm grid node %.6f snapped to 1.0 (TORAX needs a"
            " rho=1 boundary value)",
            ids_name,
            snapped_last,
        )


_SPLIT_REPORTED = set()


def _copy_optional(src, dst, attr):
    """Copy src.<attr> to dst.<attr> when the field exists in both DD versions and is filled."""
    try:
        value = getattr(src, attr)
        if value.has_value:
            setattr(dst, attr, value)
    except AttributeError:
        # field absent from the source's or the destination's data-dictionary version
        return


# 12-coil DINA pf_active -> 14-coil ITER machine description, as done by the DINA
# developer's conversion script (pf.py, update_pfa): md index -> (DINA index,
# current factor, voltage factor). The VS3 current in the DINA IMAS entry is already the
# per-turn current of the 4-turn VS coils (the DINA IMAS wrapper divides by 4), so it is
# not rescaled: only its sign differs between the upper and lower coil.
_DINA12_TO_MD14 = (
    (0, 1.0, 1.0),  # CS3U
    (1, 1.0, 1.0),  # CS2U
    (2, 1.0, 0.5),  # CS1U <- CS1
    (2, 1.0, 0.5),  # CS1L <- CS1
    (3, 1.0, 1.0),  # CS2L
    (4, 1.0, 1.0),  # CS3L
    (5, 1.0, 1.0),  # PF1
    (6, 1.0, 1.0),  # PF2
    (7, 1.0, 1.0),  # PF3
    (8, 1.0, 1.0),  # PF4
    (9, 1.0, 1.0),  # PF5
    (10, 1.0, 1.0),  # PF6
    (11, -1.0, -0.5),  # VSU <- VS3 (upper element)
    (11, 1.0, 0.5),  # VSL <- VS3 (lower element)
)
# Supplies (pf.py, update_pfa, branch for a source without 14 supplies): md supply index
# -> DINA coil index; supply 11 (VS1) is -PF2 - PF3 + PF4 + PF5 with no voltage.
# pf.py lacks the `for i in range(14):` loop around the first two assignments of that
# branch (as written it fills only supply 13); the loop is its evident intent.
_DINA12_SUPPLY_FROM_COIL = (0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 11)
_DINA12_VS1_COMBINATION = ((6, -1.0), (7, -1.0), (8, 1.0), (9, 1.0))


def _optional_time(node):
    """Return node.time as an array when the field exists and is filled, else None."""
    try:
        time = node.time
        return np.array(time, dtype=float) if time.has_value else None
    except AttributeError:
        return None


def _split_multi_element_coils(slice, slice_backup):
    """Convert a 12-coil DINA pf_active onto the 14-coil ITER machine description,
    following the DINA developer's conversion script (pf.py, update_pfa).

    Older DINA runs (e.g. 105033) carry 12 coils: CS1 as one coil (two elements) and
    VS3 as one coil (two elements), where the machine description has 14 single-element
    coils (CS1U, CS1L, VSU, VSL). As in pf.py, CS1U and CS1L both take the CS1 current
    and half its voltage; VSU takes -I_VS3 and -V_VS3/2, VSL takes +I_VS3 and +V_VS3/2
    (the DINA IMAS VS3 current is already the per-turn current of the 4-turn VS coils,
    so it is not rescaled); all other coils map one to one. Name, identifier,
    resistance, geometry and turns come from the machine description (NICE needs its
    geometry type). When the DINA entry lacks the 14 supplies, supplies, circuits and
    vertical_force are taken from the machine description and filled from the coil
    traces as in pf.py. Raises ValueError for any other coil-count combination.
    """
    n_src = len(slice.coil)
    n_md = len(slice_backup.coil)
    if n_src != 12 or n_md != 14:
        raise ValueError(
            f"pf_active: DINA has {n_src} coils and the machine description {n_md};"
            " only the 12 -> 14 conversion of the DINA developer's pf.py is"
            " implemented. DINA coils: "
            + ", ".join(str(coil.name) for coil in slice.coil)
        )

    # slice_backup (machine description) is read with autoconvert=False in DD 3.x,
    # where coil/supply names are the long form (e.g. "Central Solenoid 1U (CS1U)").
    # slice has already been converted to DD_VERSION (4.x), where convert_ids renames
    # them to the short DD4 form (e.g. "CS1U", "VS3U"). Convert slice_backup once so
    # the names written here line up with NICE's DD4 names ("VS3U"/"VS3L") instead of
    # copying the DD3 long names.
    with quiet_expected_conversion_drops():
        md_dd4 = convert_ids(slice_backup, DD_VERSION)
    md_names = [str(c.name) for c in md_dd4.coil]

    # Snapshot the DINA traces before the AoS is resized (resize resets the entries).
    currents, current_times, voltages, voltage_times = [], [], [], []
    for coil in slice.coil:
        currents.append(np.array(coil.current.data, dtype=float))
        current_times.append(_optional_time(coil.current))
        if coil.voltage.data.has_value:
            voltages.append(np.array(coil.voltage.data, dtype=float))
        else:
            voltages.append(None)
        voltage_times.append(_optional_time(coil.voltage))

    slice.coil.resize(n_md)
    for k, (src, f_current, f_voltage) in enumerate(_DINA12_TO_MD14):
        md = slice_backup.coil[k]
        dst = slice.coil[k]
        dst.name = md_names[k]
        _copy_optional(md, dst, "identifier")
        dst.resistance = md.resistance
        dst.element.resize(0)
        dst.element.resize(1)
        dst.element[0].geometry = md.element[0].geometry
        dst.element[0].turns_with_sign = md.element[0].turns_with_sign
        _copy_optional(md.element[0], dst.element[0], "name")
        dst.current.data = currents[src] * f_current
        if current_times[src] is not None:
            dst.current.time = current_times[src]
        if voltages[src] is not None:
            dst.voltage.data = voltages[src] * f_voltage
            if voltage_times[src] is not None:
                dst.voltage.time = voltage_times[src]

    if len(slice.supply) != 14:
        # supply/circuit names are renamed the same way by convert_ids, so take them
        # (not just names) from the DD4-converted copy rather than slice_backup.
        slice.supply = copy.deepcopy(md_dd4.supply)
        slice.circuit = copy.deepcopy(md_dd4.circuit)
        # AttributeError: field absent from the source's or the destination's
        # data-dictionary version
        with contextlib.suppress(AttributeError):
            slice.vertical_force = copy.deepcopy(slice_backup.vertical_force)
        for i, src in enumerate(_DINA12_SUPPLY_FROM_COIL):
            supply = slice.supply[i]
            if i == 11:
                supply.current.data = sum(
                    f * currents[c] for c, f in _DINA12_VS1_COMBINATION
                )
                supply.voltage.data = np.array([])
            else:
                supply.current.data = currents[src]
                if voltages[src] is not None:
                    factor = 0.5 if i in (2, 3) else 1.0
                    supply.voltage.data = voltages[src] * factor
            if current_times[src] is not None:
                with contextlib.suppress(AttributeError):
                    supply.current.time = current_times[src]

    if "reported" not in _SPLIT_REPORTED:
        _SPLIT_REPORTED.add("reported")
        logger.warning(
            "pf_active: 12-coil DINA entry converted to the 14-coil machine description"
            " following the DINA developer's pf.py (CS1 -> CS1U/CS1L, VS3 -> VSU -I /"
            " VSL +I, no rescaling; supplies and circuits from the machine description)"
        )


def find_interesting_time_slices(sm, n_timeslices=None, dt_step=None):
    """Raw summary indices of the slices to prepare, sorted and unique.

    Exactly one of ``n_timeslices`` and ``dt_step`` is given. ``dt_step``: target times
    first viable time, +dt_step, +2 dt_step, ... up to the last viable time, each
    mapped to the nearest viable raw index. ``n_timeslices``: ``n_timeslices`` targets
    uniform over the viable range (the original selection, kept unchanged).
    """
    if (n_timeslices is None) == (dt_step is None):
        raise ValueError("give exactly one of n_timeslices and dt_step")
    if dt_step is not None:
        return _time_slices_by_dt(sm, dt_step)
    assert n_timeslices is not None
    t = sm.time
    # energy signal
    wth = sm.global_quantities.energy_thermal.value
    wbp = sm.global_quantities.energy_b_field_pol.value
    # for Bv
    ip = sm.global_quantities.ip.value
    li = sm.global_quantities.li.value
    betap = sm.global_quantities.beta_pol.value
    R = sm.boundary.magnetic_axis_r.value
    a = sm.boundary.minor_radius.value
    K = sm.boundary.elongation.value
    indice_valid = [i for i in range(len(R)) if R[i] > 1 and abs(ip[i]) > 50e3]
    R = max(np.array(R) + np.array([1]))
    # constante
    mu0 = 4 * np.pi * 1e-7
    # proxy for vertical magnetic field
    denom = 4 * np.pi * R * (8 * R / a / np.sqrt(K) + betap + li / 2 - 3 / 2)
    bv = mu0 * ip / denom
    # time derivative
    dwthdt = np.gradient(wth, t, edge_order=1)
    dwbpdt = np.gradient(wbp, t, edge_order=1)
    dbvdt = np.gradient(bv, t, edge_order=1)
    # control variable
    fwi = cumtrapz(t, abs(dwthdt) + abs(dwbpdt), initial=0)
    fwi = (fwi - min(fwi)) / (max(fwi) - min(fwi))
    fbvi = cumtrapz(t, abs(dbvdt), initial=0)
    fbvi = (fbvi - min(fbvi)) / (max(fbvi) - min(fbvi))
    # added to be strictely monotonic and have some points in flattop
    ft = (t - min(t)) / (max(t) - min(t))
    # f = (fwi + fbvi + ft) / 3
    f = ft
    # juste to take into account validity
    f = (f - min(f[indice_valid])) / (max(f[indice_valid] - min(f[indice_valid])))
    # time selection
    f_nearest = interp1(
        f[indice_valid],
        list(range(len(f[indice_valid]))),
        kind="linear",
    )
    indice_selected = sorted(
        {int(idx) for idx in f_nearest(np.linspace(0, 1, n_timeslices))}
    )
    return indice_selected


def _time_slices_by_dt(sm, dt_step):
    """Nearest viable raw index to each of t_v0, t_v0 + dt, ... <= t_v1."""
    if not dt_step > 0:
        raise ValueError(f"dt_step must be > 0, got {dt_step}")
    valid = np.asarray(_viable_indices(sm), dtype=int)
    if valid.size == 0:
        return []
    if valid.size == 1:
        return [int(valid[0])]
    t_valid = np.asarray(sm.time, dtype=float)[valid]
    t0, t1 = t_valid[0], t_valid[-1]
    # Tolerance so that a last target landing on t1 up to rounding is kept.
    n = int(np.floor((t1 - t0) / dt_step + 1e-9)) + 1
    targets = t0 + dt_step * np.arange(n)
    # Nearest viable sample: t_valid is increasing, compare the two neighbours.
    pos = np.clip(np.searchsorted(t_valid, targets), 1, len(t_valid) - 1)
    left = t_valid[pos - 1]
    right = t_valid[pos]
    pos = np.where(targets - left <= right - targets, pos - 1, pos)
    return sorted({int(i) for i in valid[pos]})
