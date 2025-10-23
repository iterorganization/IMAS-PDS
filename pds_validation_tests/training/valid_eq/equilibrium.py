"""
Test validation for equilibrium
"""


@validator("equilibrium")
def validate_ip(ids):
    for ts in ids.time_slice:
        assert abs(ts.global_quantities.ip < 1.7e7)
