#!/usr/bin/env python3
"""Copy the IDSs METIS reads out of a DINA entry, converting them to a target DD version.

    convert_for_metis.py <source_uri> <output_uri> <dd_version>

The DINA sources are DD 3.x and METIS reads them through a DD 4.x IMAS-MATLAB, so they have
to be converted first. Two things make this more than a one-liner:

  * Implicit conversion on read does not cross a major version -- imas-python refuses and
    tells you to convert explicitly. So the source is opened AT its own version (discovered
    below) and each IDS is passed through imas.convert_ids by hand.
  * `imas convert --ids` cannot build the entry either: it takes one IDS name and creates
    its output entry, so a second call against the same entry writes nothing, and the files
    cannot be merged afterwards because master.h5 is an index, not a bag of files.

Only the IDSs init_metis_from_dina_ids.m:496 actually reads. Converting a whole DINA entry
takes many minutes and trips validation on dataset_description, which METIS never touches.
"""

import re
import sys

import imas

IDS_NAMES = [
    "summary",
    "equilibrium",
    "pulse_schedule",
    "core_profiles",
    "core_sources",
]


def source_dd_version(uri: str) -> str | None:
    """The DD version the entry is stored in, or None if it needs no conversion.

    imas-python reports it in the error it raises for a major-version mismatch, which is
    the only place it is exposed -- DBEntry.dd_version is the version you asked for, not
    the version on disk.
    """
    try:
        with imas.DBEntry(uri, "r") as entry:
            entry.get(IDS_NAMES[0])
        return None
    except Exception as exc:
        match = re.search(r"stored in DD ([\d.]+)", str(exc))
        if match:
            return match.group(1)
        raise


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    src_uri, out_uri, dd_version = sys.argv[1:4]

    src_dd = source_dd_version(src_uri)
    print(f"  source DD {src_dd or dd_version} -> {dd_version}")

    with (
        imas.DBEntry(src_uri, "r", dd_version=src_dd) as src,
        imas.DBEntry(out_uri, "w", dd_version=dd_version) as out,
    ):
        for name in IDS_NAMES:
            try:
                ids = src.get(name)
            except Exception as exc:
                print(f"  {name}: not in the source ({type(exc).__name__}), skipped")
                continue
            out.put(imas.convert_ids(ids, dd_version) if src_dd else ids)
            print(f"  {name}: converted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
