"""
Script to build valid inputs for the PDS couplings from DINA output data.
"""

import numpy as np
from scipy.integrate import cumulative_trapezoid as cumtrapz
from scipy.interpolate import interp1d as interp1
from imas import DBEntry, IDSFactory, convert_ids
from imas.ids_defs import CLOSEST_INTERP

SOURCE_PATH = "/work/imas/shared/imasdb/ITER/3/105084/1"
TARGET_PATH = "/home/ITER/sanderm/gitrepos/pds/run/temp_data/beepboop_data"
IRON_CORE_PATH = "/home/ITER/vanschr/public/imasdb/ITER/4/666666/3"
N_TIMESLICES = 51


def main():
    # convert to DDV4
    # find interesting timeslices
    # convert boundary_separatrix to boundary

    db_in = DBEntry(f"imas:hdf5?path={SOURCE_PATH}", "r")
    db_iron_core = DBEntry(f"imas:hdf5?path={IRON_CORE_PATH}", "r")
    db_out = DBEntry(f"imas:hdf5?path={TARGET_PATH}", "w")

    summary = db_in.get("summary", autoconvert=False)
    interesting_time_slices = find_interesting_time_slices(summary)

    for t in interesting_time_slices:
        # equilibrium ids
        eq_orig = db_in.get_slice(
            "equilibrium",
            time_requested=t,
            interpolation_method=CLOSEST_INTERP,
            autoconvert=False,
        )
        eq_orig.time_slice[0].boundary.psi = eq_orig.time_slice[
            0
        ].boundary_separatrix.psi
        eq_orig.time_slice[0].boundary.outline.r = eq_orig.time_slice[
            0
        ].boundary_separatrix.outline.r
        eq_orig.time_slice[0].boundary.outline.z = eq_orig.time_slice[
            0
        ].boundary_separatrix.outline.z
        eq = convert_ids(eq_orig, "4.0.0")
        db_out.put_slice(eq)

        # pf_active ids
        pfa_orig = db_in.get_slice(
            "pf_active",
            time_requested=t,
            interpolation_method=CLOSEST_INTERP,
            autoconvert=False,
        )
        pfa = convert_ids(pfa_orig, "4.0.0")
        db_out.put_slice(pfa)

        # pf_passive ids
        pfp_orig = db_in.get_slice(
            "pf_passive",
            time_requested=t,
            interpolation_method=CLOSEST_INTERP,
            autoconvert=False,
        )
        pfp = convert_ids(pfp_orig, "4.0.0")
        db_out.put_slice(pfp)

    # wall ids
    wall_orig = db_in.get("wall", autoconvert=False)
    wall = convert_ids(wall_orig, "4.0.0")
    db_out.put(wall)

    # core ids
    core_orig = db_iron_core.get("iron_core", autoconvert=False)
    core = convert_ids(core_orig, "4.0.0")
    db_out.put(core)

    db_in.close()
    db_iron_core.close()
    db_out.close()


def find_interesting_time_slices(sm):
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
    # indice_valid = (R>1) & (abs(ip) > 50e3)
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
    f = (fwi + fbvi + ft) / 3
    # juste to take into account validity
    f = (f - min(f[indice_valid])) / (max(f[indice_valid] - min(f[indice_valid])))
    # time selection
    f_nearest = interp1(
        f[indice_valid],
        list(range(len(f[indice_valid]))),
        kind="linear",
    )
    indice_selected = sorted(
        list(set([int(idx) for idx in f_nearest(np.linspace(0, 1, N_TIMESLICES))]))
    )
    return indice_selected


if __name__ == "__main__":
    main()
