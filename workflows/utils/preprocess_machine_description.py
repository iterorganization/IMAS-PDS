"""
Preprocessing of the machine-description reference data (wall, iron_core,
pf_passive and the pf_active coil-current seed) into valid PDS coupling input.
"""

import datetime
import logging
from contextlib import contextmanager

import numpy as np
from imas import IDSFactory, convert_ids


@contextmanager
def quiet_expected_conversion_drops():
    """convert_ids() warns on every call about source fields that have no home in the
    target DD version (its missing-path dedup only covers a single call). Here that's
    pf_active identifiers/vertical_force and similar fields this preprocessing already
    accounts for and does not use downstream, so silence just those "Data is not
    copied." messages, the same way imas.ids_convert itself scopes a logging filter
    around its own special-case calls.
    """
    convert_logger = logging.getLogger("imas.ids_convert")

    def _drop_filter(record):
        return not record.getMessage().endswith("Data is not copied.")

    convert_logger.addFilter(_drop_filter)
    try:
        yield
    finally:
        convert_logger.removeFilter(_drop_filter)


def write_machine_description_data(
    db_out,
    db_md_wall,
    db_md_iron_core,
    db_md_pf_passive,
    db_md_pf_active,
    write_pf_active=True,
):
    """Write the machine-description reference data the waveform editor uses for
    wall, pf_passive, iron_core, and (when write_pf_active) the NICE coil-current
    seed pf_active."""
    preprocess_wall(db_out, db_md_wall)
    preprocess_iron_core(db_out, db_md_iron_core)
    preprocess_pf_passive(db_out, db_md_pf_passive)
    if write_pf_active:
        preprocess_pf_active_md(db_out, db_md_pf_active)


def _fix_pf_active_md_geometry(slice_backup):
    """
    Fix up a machine-description pf_active slice in place:
    -The resistance for coils 0 to 11 were missing, I added them by hand as 5e-4
    -I modified the representation of coils 12 and 13 to fit Nice requirements (see doxygen)
    - https://blfauger.gitlabpages.inria.fr/nice/
    """
    # add missing coils resistance values
    for i in range(12):
        slice_backup.coil[i].resistance = 5.0e-4
    # modify representation of coils 12 and 13
    for i in (12, 13):
        coil = slice_backup.coil[i]
        rc = np.zeros(4)
        zc = np.zeros(4)
        radius = coil.element[0].geometry.annulus.radius_outer
        r = np.zeros(4)
        z = np.zeros(4)  # new contour points
        for j in range(4):
            rc[j] = coil.element[j].geometry.annulus.r
            zc[j] = coil.element[j].geometry.annulus.z
        index = [0, 2, 3, 1]  # anticlockwise reordering
        rc = rc[index]
        zc = zc[index]
        for j in range(4):
            if j == 0:
                jp1 = j + 1
                jm1 = 3
            elif j == 3:
                jp1 = 0
                jm1 = j - 1
            else:
                jp1 = j + 1
                jm1 = j - 1
            tm1 = np.array([rc[j] - rc[jm1], zc[j] - zc[jm1]])
            tm1 = tm1 / np.linalg.norm(tm1)

            tp1 = np.array([rc[j] - rc[jp1], zc[j] - zc[jp1]])
            tp1 = tp1 / np.linalg.norm(tp1)

            r[j] = rc[j] + radius * (tm1[0] + tp1[0])
            z[j] = zc[j] + radius * (tm1[1] + tp1[1])

        # resize from 4 to 1 element
        coil.element.resize(1)
        # fill the element
        coil.element[0].turns_with_sign = 4.0
        coil.element[0].geometry.geometry_type = 1
        coil.element[0].geometry.outline.r = r
        coil.element[0].geometry.outline.z = z


def preprocess_pf_active_md(db_out, db_md_pf_active):
    """Write the machine-description pf_active reference (corrected geometry and
    resistance, no DINA current data) that the waveform editor uses as NICE's
    coil-current seed. Like wall/pf_passive/iron_core, the machine-description
    pf_active source is time-independent, so it is read/written once with get/put
    rather than per-timeslice with get_slice/put_slice."""
    backup = db_md_pf_active.get("pf_active", autoconvert=False)
    _fix_pf_active_md_geometry(backup)
    with quiet_expected_conversion_drops():
        db_out.put(convert_ids(backup, "4.0.0"))


def preprocess_pf_passive(db_out, db_md_pf_passive):
    """
    -I kept only the first 2 loops. The others are another more complicated representation of the vessel which we already have in wall.
    -added the resistivity by hand
    """
    pf_passive = db_md_pf_passive.get("pf_passive")

    # keep only the first 2
    tmp = pf_passive.loop
    pf_passive.loop.resize(2, keep=True)
    pf_passive.loop[0] = tmp[0]
    pf_passive.loop[1] = tmp[1]

    # add missing resistivity
    pf_passive.loop[0].resistivity = 2.703e-8
    pf_passive.loop[1].resistivity = 9.001e-7
    with quiet_expected_conversion_drops():
        ids = convert_ids(pf_passive, "4.0.0")
    db_out.put(ids)


def preprocess_iron_core(db_out, db_md_iron_core):
    """
    -ids needed for WEST, created an empty one for ITER.
    """
    ids_orig = db_md_iron_core.get("iron_core", autoconvert=False)
    with quiet_expected_conversion_drops():
        ids = convert_ids(ids_orig, "4.0.0")
    db_out.put(ids)


def preprocess_wall(db_out, db_md_wall):
    """
    -the limiter has 2 units. In the first one points are given clockwise wheras in the second points are given anticlockwise. I reversed the first unit orientation.
    -vessel. I kept only the first 2 units. Don't remember what the others are, but not needed by Nice.
    """
    wallIn = db_md_wall.get("wall", autoconvert=False)
    wall = IDSFactory(version="4.0.0").wall()
    wall.ids_properties.homogeneous_time = 2  # static
    wall.ids_properties.creation_date = datetime.datetime.now().strftime("%y-%m-%d")
    wall.description_2d.resize(1)
    wall.description_2d[0].type.index = 2

    # copy all 2 limiter units from wallIn
    wall.description_2d[0].limiter = wallIn.description_2d[0].limiter
    # reverse the first unit so that it is anticlockwise
    wall.description_2d[0].limiter.unit[0].outline.r[:] = (
        wall.description_2d[0].limiter.unit[0].outline.r[::-1]
    )
    wall.description_2d[0].limiter.unit[0].outline.z[:] = (
        wall.description_2d[0].limiter.unit[0].outline.z[::-1]
    )

    # copy 2 first unit from vessel
    wall.description_2d[0].vessel = wallIn.description_2d[0].vessel
    tmp = wall.description_2d[0].vessel.unit
    wall.description_2d[0].vessel.unit.resize(2)
    wall.description_2d[0].vessel.unit[0] = tmp[0]
    wall.description_2d[0].vessel.unit[1] = tmp[1]

    db_out.put(wall)
