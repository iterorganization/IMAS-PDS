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
    F0 = 16.82
    dF = -0.53
    mg = 1.18e6
    F_tp4K = 190e6
    sum_vertical = 0
    cs_force_dict = {
        "CS3U": None,
        "CS2U": None,
        "CS1U": None,
        "CS1L": None,
        "CS2L": None,
        "CS3L": None,
    }
    for coil in ids.coil:
        for key in cs_force_dict:
            if key in coil.name:
                cs_force_dict[key] = coil.force_vertical.data.value
    if any(val is None for val in cs_force_dict.values()):
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
        # ty can't see that the `any(val is None ...)` guard above already ensures
        # every cs_force_dict value -- and hence every F_z entry -- is not None.
        F_gap = [F_gap[0] + F_z[i] - mg, *F_gap]  # ty: ignore[unsupported-operator]

    for F_gap_j in F_gap:
        assert F_gap_j < -26e6
    assert sum_vertical < F0 + dF * F_gap[0]
    assert abs(sum_vertical) < 60e6


@validator("pf_active")
def validate_force_limits_pf(ids):
    """Validate forces in poloidal field coils are within operational limits"""
    for coil in ids.coil:
        for key in pf_force_limits:
            if key in coil.name and coil.force_vertical.data.value:
                assert coil.force_vertical.data.value < pf_force_limits[key][0]
                assert coil.force_vertical.data.value > pf_force_limits[key][1]


@validator("pf_active")
def validate_current_limits_pf(pf_active):
    """Validate currents in poloidal field coils are within operational limits"""
    for coil in pf_active.coil:
        for key, limits in pf_current_limits.items():
            if key in coil.name and coil.current.data.value:
                assert len(coil.current.data.value) == len(
                    coil.b_field_max_timed.data.value
                )
                I_limit = [
                    interpolate_current(b_field, limits)
                    for b_field in coil.b_field_max_timed.data.value
                ]
                assert all(
                    coil.current.data.value[i] < I_limit[i] for i in range(len(I_limit))
                )


@validator("pf_active")
def validate_current_limits_cs(pf_active):
    """Validate currents in central solenoid coils are within operational limits"""
    for coil in pf_active.coil:
        for key, limits in cs_current_limits.items():
            if key in coil.name and coil.current.data.value:
                assert len(coil.current.data.value) == len(
                    coil.b_field_max_timed.data.value
                )
                I_limit = [
                    interpolate_current(b_field, limits)
                    for b_field in coil.b_field_max_timed.data.value
                ]
                assert all(
                    coil.current.data.value[i] < I_limit[i] for i in range(len(I_limit))
                )


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
        for key in I_pf_dict:
            if key in coil.name:
                I_pf_dict[key] = coil.current.data.value
    for key, val in I_pf_dict.items():
        assert val is not None, f"{key} coil not found"
    assert (
        # ty can't see that the loop above already asserted every value is not None.
        abs(I_pf_dict["PF2"] + I_pf_dict["PF3"] - I_pf_dict["PF4"] - I_pf_dict["PF5"])  # ty: ignore[unsupported-operator]
        <= 22500
    )


# TODO: add vertical stability coil tests?
