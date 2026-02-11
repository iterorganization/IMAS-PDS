"""
Script to build valid inputs for the PDS couplings from DINA output data.
"""

import logging
import argparse
import numpy as np
from scipy.integrate import cumulative_trapezoid as cumtrapz
from scipy.interpolate import interp1d as interp1
from imas import DBEntry, IDSFactory, convert_ids
from imas.ids_defs import CLOSEST_INTERP
from packaging import version


def handle_args():
    parser = argparse.ArgumentParser(description='Get preprocessed input data for NICE from DINA')
    parser.add_argument("--source_uri", type=str, help='URI to load DINA output data from')
    parser.add_argument("--summary_uri", type=str, help='URI to load DINA summary data from')
    parser.add_argument("--backup_uri", type=str, help='URI to load backup DINA output data from')
    parser.add_argument("--sink_uri", type=str, help='URI to write NICE input data to')
    parser.add_argument("--n_timeslices", type=int, default=51, help='Number of timeslices')
    args = parser.parse_args()
    return args


def main():
    """
    convert to DDV4
    find interesting timeslices
    convert boundary_separatrix to boundary
    """
    args = handle_args()

    db_in = DBEntry(args.source_uri, "r")
    db_sum = DBEntry(args.summary_uri, "r")
    db_backup = DBEntry(args.backup_uri, "r")
    db_out = DBEntry(args.sink_uri, "w")

    summary = db_sum.get("summary", autoconvert=False)
    time_array = summary.time
    interesting_time_slices = find_interesting_time_slices(summary, args.n_timeslices)
    skipped = []

    for idx in interesting_time_slices:
        # equilibrium ids
        for i in range(10):
            t = time_array[idx]
            eq_orig = db_in.get_slice(
                "equilibrium",
                time_requested=t,
                interpolation_method=CLOSEST_INTERP,
                autoconvert=False,
            )
            if version.parse(eq_orig._dd_version) < version.parse('4.0.0'):
                bndr_len = len(eq_orig.time_slice[0].boundary_separatrix.outline.r)
            else:
                bndr_len = len(eq_orig.time_slice[0].boundary.outline.r)
            if  bndr_len>= 1:
                break
            idx += 1
        if bndr_len < 1:
            t = time_array[idx]
            skipped.append(t)
            continue
        if version.parse(eq_orig._dd_version) < version.parse('4.0.0'):
            eq_orig_ts = eq_orig.time_slice[0]

            # DINA input - NICE output defined at psi_norm: 
            # profiles_1d.psi: 0..0.995 - 0..1
            # boundary: 0.995 - 1
            # boundary_separatrix: 1 - na
            eq_orig_ts.boundary.psi = eq_orig_ts.boundary_separatrix.psi
            eq_orig_ts.boundary.outline.r = eq_orig_ts.boundary_separatrix.outline.r
            eq_orig_ts.boundary.outline.z = eq_orig_ts.boundary_separatrix.outline.z
        eq = convert_ids(eq_orig, "4.0.0")
        psi = eq.time_slice[0].profiles_1d.psi
        psi_a = psi[0]
        psi_b = eq.time_slice[0].boundary.psi
        eq.time_slice[0].profiles_1d.psi_norm = abs(psi - psi_a) / abs(psi_b - psi_a)
        db_out.put_slice(eq)

        # pf_active ids
        slice_orig = db_in.get_slice(
            'pf_active',
            time_requested=t,
            interpolation_method=CLOSEST_INTERP,
            autoconvert=False,
        )
        slice_backup = db_backup.get_slice(
            'pf_active',
            time_requested=t,
            interpolation_method=CLOSEST_INTERP,
            autoconvert=False,
        )
        # VS coils have incompatible geometry_type for NICE in input,
        # should be identical across shots so getting geometry from backup is fine
        slice = convert_ids(slice_orig, "4.0.0")
        for i, coil in enumerate(slice.coil):
            if len(slice.coil) == len(slice_backup.coil):
                assert slice.coil[i].name == slice_backup.coil[i].name
                # make sure geometry_type is nice compatible
                slice.coil[i].element[0].geometry = slice_backup.coil[i].element[0].geometry
                # make sure resistance is filled
                slice.coil[i].resistance = slice_backup.coil[i].resistance
            else:
                slice.coil[i].resistance = slice_backup.coil[0].resistance
                if len(coil.element) > 1:
                    if 'VS' in coil.name:
                        slice.coil[i].resistance = slice_backup.coil[-2].resistance + slice_backup.coil[-1].resistance
                    else:
                        slice.coil[i].resistance *= len(coil.element)
                for j, element in enumerate(coil.element):
                    slice.coil[i].element[j].geometry.geometry_type = 2
                
        db_out.put_slice(slice)

        # time dependent standard
        for (ids_name, db) in [
            ('pf_passive', db_backup),
            ('core_profiles', db_in),
            ('core_sources', db_sum),
        ]:
            slice_orig = db.get_slice(
                ids_name,
                time_requested=t,
                interpolation_method=CLOSEST_INTERP,
                autoconvert=False,
            )
            slice = convert_ids(slice_orig, "4.0.0")
            db_out.put_slice(slice)

    # time independent standard
    for (ids_name, db) in [
        ('wall', db_backup),
        ('iron_core', db_backup),
    ]:
        ids_orig = db.get(ids_name, autoconvert=False)
        ids = convert_ids(ids_orig, "4.0.0")
        db_out.put(ids)

    db_in.close()
    db_backup.close()
    db_out.close()
    print(skipped)


def find_interesting_time_slices(sm, n_timeslices):
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
        list(set([int(idx) for idx in f_nearest(np.linspace(0, 1, n_timeslices))]))
    )
    return indice_selected


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.WARNING,
    )
    main()
