"""
PDS-OLC-specific validation rules for the ``pf_active`` IDS for ITER scenarios.
Based on ITER 33NHXN document
"""

pf_current_limits = {
    # linear interpolation setpoints based on temperature of 4.3K
    # [(current 1, magnetic field 1), (current 2, magnetic field 2)]
    "PF1": [(48000, 6.4), (41000, 6.5)],
    "PF2": [(55000, 4.8), (50000, 5.0)],
    "PF3": [(55000, 4.8), (50000, 5.0)],
    "PF4": [(55000, 4.8), (50000, 5.0)],
    "PF5": [(52000, 4.7), (33000, 6.0)],
    "PF6": [(48000, 6.4), (41000, 6.5)],
}
cs_current_limits = {
    # linear interpolation setpoints based on temperature of 4.3K
    # [(current 1, magnetic field 1), (current 2, magnetic field 2)]
    "CS3U": [(45000, 12.6), (40000, 13.0)],
    "CS2U": [(45000, 12.6), (40000, 13.0)],
    "CS1U": [(45000, 12.6), (40000, 13.0)],
    "CS1L": [(45000, 12.6), (40000, 13.0)],
    "CS2L": [(45000, 12.6), (40000, 13.0)],
    "CS3L": [(45000, 12.6), (40000, 13.0)],
}
pf_force_limits = {
    # (maximum upwards force, maximum downwards force)
    "PF1": (110e6, -150e6),
    "PF2": (15e6, -75e6),
    "PF3": (40e6, -90e6),
    "PF4": (90e6, -40e6),
    "PF5": (160e6, -10e6),
    "PF6": (170e6, -190e6),
}


def interpolate_current(B_value, setpoints):
    a = (setpoints[1][0] - setpoints[0][0]) / (setpoints[1][1] - setpoints[0][1])
    b = setpoints[0][0] - a * setpoints[0][1]
    I_limit = a * B_value + b
    return I_limit


@validator("pf_active")
def validate_force_limits_cs(ids):
    """Validate forces on central solenoid coils are within operational limits"""
    # Skip until more clarity about F_tp4K and fci
    return
    alpha = -0.0019
    beta = [0.0389, 0, 1161, 0, 1933, 0.2696, 0.3468, 0.4239]
    gamma = 0.0739
    F0 = 16.82
    dF = -0.53
    mg = 1.18e6
    # TODO: F_tp4K not defined
    F_tp4K = None
    sum_radial = 0
    sum_vertical = 0
    sum_vertical_beta = 0
    sum_c = 0
    cs_force_dict = {
        "CS3U": None,
        "CS2U": None,
        "CS1U": None,
        "CS1L": None,
        "CS2L": None,
        "CS3L": None,
    }
    for coil in ids.coil:
        for key in cs_force_dict.keys():
            if key in coil.name:
                cs_force_dict = coil.force_vertical.data.value
                # TODO: not clear how F_ci is defined (combination of crushing vertical and crushing radial?)
                # sum_radial +=
                # sum_vertical +=
                # sum_vertical_beta +=
                # sum_c +=
    if all([val is not None for val in cs_force_dict.values()]):
        return

    F_z = [
        cs_force_dict["CS3L"],
        cs_force_dict["CS2L"],
        cs_force_dict["CS1L"],
        cs_force_dict["CS1U"],
        cs_force_dict["CS2U"],
        cs_force_dict["CS3U"],
    ]
    Ftp = F_tp4K
    F_gap = [-Ftp]
    for i in reversed(range(6)):
        F_gap = [F_gap[0] + F_z[i] - mg] + F_gap

    for F_gap_j in F_gap:
        assert F_gap_j < -26e6
    assert sum_vertical < F0 + dF * F_gap[0]
    assert abs(sum_vertical) < 60e6


@validator("pf_active")
def validate_force_limits_pf(ids):
    """Validate forces in poloidal field coils are within operational limits"""
    for coil in ids.coil:
        for key in pf_force_limits.keys():
            if key in coil.name:
                if coil.force_vertical.data.value:
                    assert coil.force_vertical.data.value < pf_force_limits[key][0]
                    assert coil.force_vertical.data.value > pf_force_limits[key][1]


@validator("pf_active")
def validate_current_limits_pf(ids):
    """Validate currents in poloidal field coils are within operational limits"""
    for coil in ids.coil:
        for key in pf_current_limits.keys():
            if key in coil.name:
                if coil.current.data.value:
                    I_limit = interpolate_current(
                        coil.b_field_max, pf_current_limits[key]
                    )
                    assert coil.current.data.value < I_limit
                    # also compare against coil.current_limit_max?


@validator("pf_active")
def validate_current_limits_cs(ids):
    """Validate currents in central solenoid coils are within operational limits"""
    for coil in ids.coil:
        for key in cs_current_limits.keys():
            if key in coil.name:
                if coil.current.data.value:
                    I_limit = interpolate_current(
                        coil.b_field_max, cs_current_limits[key]
                    )
                    assert coil.current.data.value < I_limit
                    # also compare against coil.current_limit_max?


@validator("pf_active")
def validate_imbalance_current_limits(ids):
    """Validate current imbalance in poloidal field coils is within operational limits"""
    # I_pf2 + I_pf3 - I_pf4 - I_pf5 <= 22500
    I_pf_dict = {
        "PF2": None,
        "PF3": None,
        "PF4": None,
        "PF5": None,
    }
    for coil in ids.coil:
        for key in I_pf_dict.keys():
            if key in coil.name:
                I_pf_dict[key] = coil.current.data.value
    for key, val in I_pf_dict.items():
        assert val is not None, f"{key} coil not found"
    assert (
        abs(I_pf_dict["PF2"] + I_pf_dict["PF3"] - I_pf_dict["PF4"] - I_pf_dict["PF5"])
        <= 22500
    )


# TODO: add vertical stability coil tests?
