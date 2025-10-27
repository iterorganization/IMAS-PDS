"""
Test validation rule set for the equilibrium IDS. This is a dummy ruleset only
to be used for training purposes.
"""


@validator("equilibrium")
def validate_ip(ids):
    for ts in ids.time_slice:
        assert abs(ts.global_quantities.ip) < 1.7e7
