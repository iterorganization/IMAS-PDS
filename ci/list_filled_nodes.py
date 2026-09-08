#!/usr/bin/env python3
"""List which IDSs a data entry holds, and which of their nodes are filled.

Point it at the DBEntries a run left behind -- the taps of
``ymmsl_files/debug/*_taps.ymmsl``, or any ``out_*`` entry:

    ci/list_filled_nodes.py cases/runs/<run>/taps/*
    ci/list_filled_nodes.py "imas:hdf5?path=cases/runs/<run>/out_nice"

A bare path is turned into an ``imas:hdf5?path=...`` URI; a full URI is used as given.

By default paths are collapsed over array-of-structure indices, so a pf_active with
twelve coils prints one ``coil[*]/current/data`` line with a count instead of twelve
lines. Use --full to see every index, and --values to print the values themselves
rather than just their type and shape.
"""

import argparse
import re
import sys
from pathlib import Path

import imas
import imas.util

INDEX_RE = re.compile(r"\[\d+\]")


def uri_of(target: str) -> str:
    """Accept a full IMAS URI, a netCDF file, or a directory holding an HDF5 entry."""
    if "?" in target or target.startswith("imas:"):
        return target
    path = Path(target).resolve()
    if path.suffix == ".nc":
        return str(path)
    return f"imas:hdf5?path={path}"


def describe(node) -> str:
    """One-line description of a filled leaf node: its type, and shape or value."""
    value = node.value
    shape = getattr(value, "shape", None)
    if shape:
        return f"{node.metadata.data_type.value} {tuple(shape)}"
    return f"{node.metadata.data_type.value}"


def format_value(node, width: int = 60) -> str:
    text = " ".join(str(node.value).split())
    return text if len(text) <= width else text[: width - 3] + "..."


# Every IDS an actor writes carries these, and they say nothing about the physics data
# that was passed, so they are dropped unless --provenance is given.
PROVENANCE_PREFIX = "ids_properties/version_put/"


def filled_nodes(ids, provenance: bool = False) -> list:
    nodes = imas.util.tree_iter(ids, leaf_only=True, visit_empty=False)
    if provenance:
        return list(nodes)
    return [
        n for n in nodes if not imas.util.get_full_path(n).startswith(PROVENANCE_PREFIX)
    ]


def report_ids(ids, ids_name: str, occurrence: int, args) -> None:
    nodes = filled_nodes(ids, args.provenance)
    dd = ids._dd_version if hasattr(ids, "_dd_version") else "?"
    occ = "" if occurrence == 0 else f" (occurrence {occurrence})"
    print(f"\n  {ids_name}{occ} -- {len(nodes)} filled nodes, DD {dd}")

    if args.full:
        for node in nodes:
            path = imas.util.get_full_path(node)
            extra = format_value(node) if args.values else describe(node)
            print(f"    {path:<62} {extra}")
        return

    # Collapse indices: one line per distinct path shape, with how many nodes it covers.
    seen: dict[str, list] = {}
    for node in nodes:
        seen.setdefault(INDEX_RE.sub("[*]", imas.util.get_full_path(node)), []).append(
            node
        )
    for path, group in seen.items():
        first = group[0]
        extra = format_value(first) if args.values else describe(first)
        count = f" x{len(group)}" if len(group) > 1 else ""
        print(f"    {path:<62} {extra}{count}")


def report_entry(target: str, args) -> int:
    uri = uri_of(target)
    print(f"\n=== {uri} ===")
    found = 0
    with imas.DBEntry(uri, "r") as entry:
        for ids_name in entry.factory.ids_names():
            try:
                occurrences = entry.list_all_occurrences(ids_name)
            except Exception:  # backend cannot list; fall back to occurrence 0
                occurrences = [0]
            for occurrence in occurrences:
                try:
                    ids = entry.get(ids_name, occurrence)
                except Exception:
                    continue
                if not filled_nodes(ids, args.provenance):
                    continue
                found += 1
                report_ids(ids, ids_name, occurrence, args)
    if not found:
        print("  (no filled IDSs)")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("targets", nargs="+", help="DBEntry paths or IMAS URIs")
    parser.add_argument(
        "--full",
        action="store_true",
        help="list every index instead of collapsing them",
    )
    parser.add_argument(
        "--values", action="store_true", help="print values instead of type and shape"
    )
    parser.add_argument(
        "--provenance",
        action="store_true",
        help="also list the ids_properties/version_put nodes every actor writes",
    )
    args = parser.parse_args()

    for target in args.targets:
        try:
            report_entry(target, args)
        except Exception as exc:
            print(f"\n=== {target} ===\n  could not read: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
