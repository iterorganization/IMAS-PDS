#!/usr/bin/env python3
"""Compare the IDSs written by two runs, and report any difference.

A flatten-diff proves two graphs have the same shape; only comparing outputs proves they
compute the same thing. Run both definitions on the same scenario, then point this at the
two output entries.

    python ci/compare_ids.py <reference_uri> <new_uri> [--ids equilibrium,pf_active]
    python ci/compare_ids.py <reference_dir> <new_dir>      # bare paths are taken as
                                                            # imas:hdf5?path=<dir>

    --rtol / --atol   tolerate small numeric differences (default: exact)
    --max-report      how many differing fields to list per IDS (default 20)

Exits non-zero if anything differs, so it can be used as a gate in a script.

Comparison walks the whole IDS via imas.util.idsdiffgen rather than a hand-picked field
list, so a difference in a field nobody thought to check still fails the run.
"""

import argparse
import sys

import imas
import imas.util
import numpy as np

DEFAULT_IDS = ("equilibrium", "pf_active", "core_profiles", "core_sources", "summary")

# version_put/* and source are deliberately NOT here: a difference there means the runs
# used different data dictionaries or different inputs.
RUN_VARYING = ("ids_properties/creation_date", "ids_properties/provider")


def as_uri(s: str) -> str:
    return s if "?" in s or s.startswith("imas:") else f"imas:hdf5?path={s}"


def describe(v) -> str:
    """One-line rendering of a value, whatever its rank."""
    if v is None:
        return "<empty>"
    a = np.asarray(v)
    if a.dtype.kind in "US":
        s = "".join(a.ravel().astype(str)) if a.ndim else str(a)
        return repr(s if len(s) <= 40 else s[:37] + "...")
    if a.ndim == 0:
        return f"{a}"
    return f"array{a.shape}"


def magnitude(v1, v2):
    """(max absolute difference, max relative difference), or None if not numeric."""
    try:
        a, b = np.asarray(v1, float), np.asarray(v2, float)
    except (TypeError, ValueError):
        return None
    if a.shape != b.shape:
        return None
    d = np.abs(a - b)
    if not d.size:
        return None
    scale = np.where(
        np.maximum(np.abs(a), np.abs(b)) == 0, 1.0, np.maximum(np.abs(a), np.abs(b))
    )
    abs_d = float(np.max(d))
    if np.isnan(abs_d):  # one side unfilled, or the physics went NaN
        return None
    return abs_d, float(np.max(d / scale))


def compare_ids(ref, new, name, rtol, atol, max_report, all_fields):
    """Return (n_differences, printed_lines) for one IDS."""
    if imas.util.calc_hash(ref) == imas.util.calc_hash(new):
        return 0, [f"  {name:<16} identical (hash match)"]

    diffs, worst_abs, worst_rel, shown, skipped = 0, 0.0, 0.0, [], 0
    for path, v1, v2 in imas.util.idsdiffgen(ref, new):
        if not all_fields and path in RUN_VARYING:
            skipped += 1
            continue
        mag = magnitude(v1, v2)
        if mag is not None:
            abs_d, rel_d = mag
            if abs_d <= atol or rel_d <= rtol:
                continue
            worst_abs, worst_rel = max(worst_abs, abs_d), max(worst_rel, rel_d)
            detail = f"max|d|={abs_d:.6g} rel={rel_d:.6g}"
        else:
            detail = f"{describe(v1)} vs {describe(v2)}"
        diffs += 1
        if len(shown) < max_report:
            shown.append(f"    {path}  {detail}")

    if not diffs:
        note = f" ({skipped} run-varying field(s) skipped)" if skipped else ""
        return 0, [f"  {name:<16} equal{note}"]

    lines = [
        f"  {name:<16} {diffs} DIFFERENT field(s)"
        + (f", worst max|d|={worst_abs:.6g} rel={worst_rel:.6g}" if worst_abs else "")
    ]
    lines += shown
    if diffs > len(shown):
        lines.append(f"    ... and {diffs - len(shown)} more")
    return diffs, lines


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("reference")
    p.add_argument("new")
    p.add_argument(
        "--ids", help="comma-separated IDS names (default: the usual PDS set)"
    )
    p.add_argument("--rtol", type=float, default=0.0)
    p.add_argument("--atol", type=float, default=0.0)
    p.add_argument("--max-report", type=int, default=20)
    p.add_argument(
        "--all-fields",
        action="store_true",
        help="also compare creation_date/provider, which vary per run",
    )
    args = p.parse_args()

    names = args.ids.split(",") if args.ids else list(DEFAULT_IDS)
    ref_uri, new_uri = as_uri(args.reference), as_uri(args.new)
    print(f"reference : {ref_uri}\nnew       : {new_uri}\n")

    total, compared = 0, 0
    with imas.DBEntry(ref_uri, "r") as ref_e, imas.DBEntry(new_uri, "r") as new_e:
        for name in names:
            # Read the two sides separately. Reading both in one try cannot tell "this
            # workflow does not write this IDS" from "the new run died before writing it":
            # the second is a regression, and folding it into the skip lets a half-finished
            # run pass the gate on whatever it did manage to write.
            try:
                ref = ref_e.get(name)
            except Exception:
                continue  # not written by this workflow
            if not len(getattr(ref, "time", [])) and not len(getattr(ref, "coil", [])):
                continue  # present but empty
            compared += 1
            try:
                new = new_e.get(name)
            except Exception as e:
                total += 1
                print(f"{name}: MISSING from the new run ({e})")
                continue
            n, lines = compare_ids(
                ref, new, name, args.rtol, args.atol, args.max_report, args.all_fields
            )
            total += n
            print("\n".join(lines))

    if not compared:
        print("no IDSs in common -- check the URIs and --ids", file=sys.stderr)
        return 2
    print(f"\n{compared} IDS(s) compared, {total} differing field(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
