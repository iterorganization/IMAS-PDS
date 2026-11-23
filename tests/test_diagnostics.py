import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "workflows/lib/actors"))
from diagnostics import CurrentCentre  # ty: ignore[unresolved-import]


def test_area_weighted_centre_is_not_the_node_mean():
    # rectangle [0, 2] x [0, 1] with four of its six nodes crowded at r <= 0.1: the node mean
    # is pulled to the left, the area-weighted centre of a uniform j is the rectangle's centre
    r = np.array([0.0, 0.0, 0.1, 0.1, 2.0, 2.0])
    z = np.array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    centre = CurrentCentre()
    assert np.allclose(centre(r, z, np.ones(6)), (1.0, 0.5))
    assert np.allclose(centre(r, z, 2 * np.ones(6)), (1.0, 0.5))  # cached triangulation
    assert abs(r.mean() - 1.0) > 0.2
