"""Copy core_profiles, dropping radial points whose grid/psi repeats the next one.

TORAX writes psi at the rho=0 face equal to the first cell's value (zero-gradient axis
condition), so its psiN starts 0, 0, ... NICE evo_rd's F decomposition interpolates over
psiN without guarding that, and returns NaN on the very first solve. Keeping the cell
rather than the face hands TORAX back its own cell values unchanged.

usage: dedup_core_profiles_grid.py <in-uri> <out-uri>
"""

import sys

import imas
import numpy as np
from imas.ids_primitive import IDSNumericArray


def dedup_profile(profile):
    """Drop every radial point whose grid/psi equals the next one, in place.

    Every 1D leaf of `profile` (one core_profiles.profiles_1d entry) with the radial
    grid's length is trimmed. Returns the number of points dropped.
    """
    keep = np.append(np.diff(profile.grid.psi) != 0, True)
    n = len(keep)
    for leaf in imas.util.tree_iter(profile, leaf_only=True):
        if (
            isinstance(leaf, IDSNumericArray)
            and leaf.metadata.ndim == 1
            and len(leaf) == n
        ):
            leaf.value = np.asarray(leaf)[keep]
    return n - keep.sum()


def main(uri_in, uri_out):
    """Read core_profiles from `uri_in`, dedup every slice, write it to `uri_out`."""
    with imas.DBEntry(uri_in, "r") as db:
        cp = db.get("core_profiles")
    dropped = [dedup_profile(p) for p in cp.profiles_1d]
    print(
        f"dropped {max(dropped)} repeated psi point(s) per slice from {len(dropped)} slices"
    )
    with imas.DBEntry(uri_out, "w") as db:
        db.put(cp)


if __name__ == "__main__":
    main(*sys.argv[1:3])
