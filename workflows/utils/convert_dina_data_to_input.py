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
import datetime


def handle_args():
    parser = argparse.ArgumentParser(
        description="Get preprocessed input data for NICE from DINA"
    )
    parser.add_argument(
        "--source_uri", type=str, help="URI to load DINA output data from"
    )
    parser.add_argument(
        "--summary_uri", type=str, help="URI to load DINA summary data from"
    )
    parser.add_argument(
        "--md_pf_active_uri", type=str, help="URI to load machine description data for pf_active"
    )
    parser.add_argument(
        "--md_pf_passive_uri", type=str, help="URI to load machine description data for pf_passive"
    )
    parser.add_argument(
        "--md_wall_uri", type=str, help="URI to load machine description data for wall"
    )
    parser.add_argument(
        "--md_iron_core_uri", type=str, help="URI to load machine description data for iron_core"
    )
    parser.add_argument("--sink_uri", type=str, help="URI to write NICE input data to")
    parser.add_argument(
        "--n_timeslices", type=int, default=51, help="Number of timeslices"
    )
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
    db_md_pf_active = DBEntry(args.md_pf_active_uri, "r")
    db_md_pf_passive = DBEntry(args.md_pf_passive_uri, "r")
    db_md_wall = DBEntry(args.md_wall_uri, "r")
    db_md_iron_core = DBEntry(args.md_iron_core_uri, "r")
    db_out = DBEntry(args.sink_uri, "w")

    summary = db_sum.get("summary", autoconvert=False)
    time_array = summary.time
    interesting_time_slices = find_interesting_time_slices(summary, args.n_timeslices)
    skipped = []
    t_list = []

    # time independent
    preprocess_wall(db_out, db_md_wall)
    preprocess_iron_core(db_out, db_md_iron_core)

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
            if version.parse(eq_orig._dd_version) < version.parse("4.0.0"):
                bndr_len = len(eq_orig.time_slice[0].boundary_separatrix.outline.r)
            else:
                bndr_len = len(eq_orig.time_slice[0].boundary.outline.r)
            if bndr_len >= 1:
                break
        if bndr_len == 0:
            skipped.append(t)
            continue
        if version.parse(eq_orig._dd_version) < version.parse("4.0.0"):
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
            slice = convert_ids(slice_orig, "4.0.0")
            db_out.put_slice(slice)
        t_list.append(t)

    preprocess_pf_active(db_out, db_in, db_md_pf_active, t_list)
    preprocess_pf_passive(db_out, db_md_pf_passive, t_list)

    db_in.close()
    db_md_pf_active.close()
    db_md_pf_passive.close()
    db_md_wall.close()
    db_md_iron_core.close()
    db_out.close()
    print(skipped)

def preprocess_pf_active(db_out, db_in, db_md_pf_active, t_list):
    """
    -The resistance for coils 0 to 11 were missing, I added them by hand
    -size(time) was different from size(current.data) for coils 0 to 7, I corrected this
    -I modified the representation of coils 12 and 13 to fit Nice requirements (see doxygen)
    -I added missing voltage data in the supply
    """
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

        ## add missing coils resistance values
        for i in range(12):
            slice_backup.coil[i].resistance=5.0e-4
        ## modify representation of coils 12 and 13
        for i in (12,13):
            coil=slice_backup.coil[i]
            rc=np.zeros(4); zc=np.zeros(4)
            radius=coil.element[0].geometry.annulus.radius_outer
            r=np.zeros(4); z=np.zeros(4) #new contour points 
            for j in range(4):
                rc[j]=coil.element[j].geometry.annulus.r
                zc[j]=coil.element[j].geometry.annulus.z
            index=[0,2,3,1] #anticlockwise reordering
            rc=rc[index]; zc=zc[index]
            for j in range(4):
                if j == 0:
                    jp1=j+1
                    jm1=3
                elif j == 3:
                    jp1=0
                    jm1=j-1
                else:
                    jp1=j+1
                    jm1=j-1
                tm1=np.array([rc[j]-rc[jm1],zc[j]-zc[jm1]])
                tm1=tm1/np.linalg.norm(tm1)
            
                tp1=np.array([rc[j]-rc[jp1],zc[j]-zc[jp1]])
                tp1=tp1/np.linalg.norm(tp1)

                r[j]=rc[j]+radius*(tm1[0]+tp1[0])
                z[j]=zc[j]+radius*(tm1[1]+tp1[1])

            #resize from 4 to 1 element
            coil.element.resize(1)
            #fill the element
            coil.element[0].turns_with_sign=4.0
            coil.element[0].geometry.geometry_type=1
            coil.element[0].geometry.outline.r=r
            coil.element[0].geometry.outline.z=z

        # VS coils have incompatible geometry_type for NICE in input,
        # should be identical across shots so getting geometry from backup is fine
        slice = convert_ids(slice_orig, "4.0.0")
        for i, coil in enumerate(slice.coil):
            if len(slice.coil) == len(slice_backup.coil):
                assert slice.coil[i].name == slice_backup.coil[i].name
                # make sure geometry_type is nice compatible
                slice.coil[i].element[0].geometry = (
                    slice_backup.coil[i].element[0].geometry
                )
                # make sure resistance is filled
                slice.coil[i].resistance = slice_backup.coil[i].resistance
            else:
                slice.coil[i].resistance = slice_backup.coil[0].resistance
                if len(coil.element) > 1:
                    if "VS" in coil.name:
                        slice.coil[i].resistance = (
                            slice_backup.coil[-2].resistance
                            + slice_backup.coil[-1].resistance
                        )
                    else:
                        slice.coil[i].resistance *= len(coil.element)
                for j, element in enumerate(coil.element):
                    slice.coil[i].element[j].geometry.geometry_type = 2

        db_out.put_slice(slice)

def preprocess_pf_passive(db_out, db_md_pf_passive, t_list):
    """
    -I kept only the first 2 loops. The others are another more complicated representation of the vessel which we already have in wall.
    -added the resistivity by hand
    """
    pf_passive = db_md_pf_passive.get('pf_passive')

    ## keep only the first 2
    tmp=pf_passive.loop
    #print(tmp)
    pf_passive.loop.resize(2, keep=True)
    pf_passive.loop[0]=tmp[0]
    pf_passive.loop[1]=tmp[1]

    ## add missing resistivity
    pf_passive.loop[0].resistivity=2.703e-8
    pf_passive.loop[1].resistivity=9.001e-7
    ids = convert_ids(pf_passive, "4.0.0")
    db_out.put(ids)

def preprocess_iron_core(db_out, db_md_iron_core):
    """
    -ids needed for WEST, created an empty one for ITER.
    """
    ids_orig = db_md_iron_core.get('iron_core', autoconvert=False)
    ids = convert_ids(ids_orig, "4.0.0")
    db_out.put(ids)

def preprocess_wall(db_out, db_md_wall):
    """
    -the limiter has 2 units. In the first one points are given clockwise wheras in the second points are given anticlockwise. I reversed the first unit orientation. 
    -vessel. I kept only the first 2 units. Don't remember what the others are, but not needed by Nice.
    """
    wallIn = db_md_wall.get('wall', autoconvert=False)
    wall = IDSFactory(version='4.0.0').wall()
    wall.ids_properties.homogeneous_time = 2 #static
    wall.ids_properties.creation_date = datetime.datetime.now().strftime("%y-%m-%d")
    wall.description_2d.resize(1)
    wall.description_2d[0].type.index=2

    ## copy all 2 limiter units from wallIn
    wall.description_2d[0].limiter=wallIn.description_2d[0].limiter
    ## reverse the first unit so that it is anticlockwise
    wall.description_2d[0].limiter.unit[0].outline.r[:]=wall.description_2d[0].limiter.unit[0].outline.r[::-1]
    wall.description_2d[0].limiter.unit[0].outline.z[:]=wall.description_2d[0].limiter.unit[0].outline.z[::-1]

    ## copy 2 first unit from vessel
    wall.description_2d[0].vessel=wallIn.description_2d[0].vessel
    tmp= wall.description_2d[0].vessel.unit
    wall.description_2d[0].vessel.unit.resize(2)
    wall.description_2d[0].vessel.unit[0]=tmp[0]
    wall.description_2d[0].vessel.unit[1]=tmp[1]

    # ids = convert_ids(wall, "4.0.0")
    db_out.put(wall)


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
