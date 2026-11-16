#!/usr/bin/env python3
"""CLI: export a designer's Ip reference (Waveform-Editor-style YAML) three ways.

    python3 ip_waveform_export.py --yaml examples/ip_105073_like.yaml --out-dir out \
        [--refgen] [--psps-json] [--ids [--dd-version 4.0.0]] [--stop-id 99] \
        [--refgen-eh-example] [--psc-config] [--cut-at T] \
        [--validate [--limits limits/ip_limits_example.yaml]]

Without an export flag, --refgen and --psps-json are written (unless --validate
is given alone, which only validates). --ids needs imas-python (e.g. module
IMAS-MUSCLE3/1.0.0-intel-2025b-pds). --refgen-eh-example (PROPOSAL /
ILLUSTRATIVE) needs an input with an 'exceptions:' block, e.g.
examples/ip_105073_like_with_exceptions.yaml. --psc-config (PROPOSAL, PSC-3)
writes the four PSC mask files into <out-dir>/psc_config_<name>/ from the
'psc:', 'events:' and 'exception_handling:' blocks (examples/ip_105073_psc.yaml).
--cut-at T (D20) starts the schedule at designer time T (PSC clock t = 0) for
every export. With --validate, exports are written only when no violation is
found.

Exit codes: 0 ok, 2 invalid input, 3 IMAS unavailable, 4 validation violations.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    # The package directory next to this script has the same name; a package wins
    # over a module of the same name on import, so this imports the package (the
    # explicit path entry is needed under python3 -I, which does not add it).
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ip_waveform_export import ValidationError, load_design
    from ip_waveform_export.export_psps_json import write_psps_json
    from ip_waveform_export.export_refgen_xml import write_refgen_xml
    from ip_waveform_export.validate import DEFAULT_LIMITS, check, load_limits, report

    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--yaml",
        required=True,
        help="input YAML (Waveform-Editor style + segments block)",
    )
    ap.add_argument("--out-dir", help="output directory (required for exports)")
    ap.add_argument(
        "--refgen",
        action="store_true",
        help="write <name>_refgen.xml (PCSSP PSC RefGen)",
    )
    ap.add_argument(
        "--psps-json",
        action="store_true",
        help="write <name>_psps_wf.json (BEST-GUESS)",
    )
    ap.add_argument(
        "--ids",
        action="store_true",
        help="write pulse_schedule IDS to <out-dir>/ids (HDF5)",
    )
    ap.add_argument(
        "--dd-version",
        default=None,
        help="DD version of the IDS export (default: globals.dd_version, else 4.0.0)",
    )
    ap.add_argument(
        "--stop-id", type=int, default=None, help="id of the STOP segment (default 99)"
    )
    ap.add_argument(
        "--refgen-eh-example",
        action="store_true",
        help="PROPOSAL: also write <name>_refgen_eh.xml and <name>_btree_eh.xml "
        "(nominal + soft/hard exception segments, behaviour tree)",
    )
    ap.add_argument(
        "--psc-config",
        action="store_true",
        help="PROPOSAL (PSC-3): write PSCIntConfig.xml, PSCGlobalMonConfig.xml, BTree.xml, "
        "PS.xml into <out-dir>/psc_config_<name>/",
    )
    ap.add_argument(
        "--cut-at",
        type=float,
        default=None,
        help="D20: drop the segments ending before T (designer time, s) and start the "
        "first kept segment at T = PSC clock 0",
    )
    ap.add_argument(
        "--validate",
        action="store_true",
        help="P5 seed: check structure and limits, list the violations",
    )
    ap.add_argument(
        "--limits",
        default=str(DEFAULT_LIMITS),
        help="limits YAML for --validate (default: PLACEHOLDER example)",
    )
    args = ap.parse_args(argv)

    exports = (
        args.refgen
        or args.psps_json
        or args.ids
        or args.refgen_eh_example
        or args.psc_config
    )
    if not exports and not args.validate:
        args.refgen = args.psps_json = True
        exports = True
    if args.refgen_eh_example:
        args.refgen = True  # the EH example comes in addition to the nominal schedule
    if exports and not args.out_dir:
        print("--out-dir is required for exports", file=sys.stderr)
        return 2

    try:
        design = load_design(
            args.yaml, stop_id=args.stop_id, validate=not args.validate
        )
    except ValidationError as e:
        print(e, file=sys.stderr)
        return 2
    if args.cut_at is not None:
        from ip_waveform_export.cut import cut_design, cut_note

        try:
            design = cut_design(design, args.cut_at)
        except ValidationError as e:
            print(e, file=sys.stderr)
            return 2
        print("Cut        :", cut_note(design))
    if args.validate:
        limits = load_limits(args.limits)
        violations = check(design, limits)
        print(report(violations, limits))
        if violations:
            return 4
    if not exports:
        return 0

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if args.refgen:
        print(
            "RefGen XML :", write_refgen_xml(design, out / f"{design.name}_refgen.xml")
        )
    if args.refgen_eh_example:
        from ip_waveform_export.export_refgen_eh_example import write_eh_example

        try:
            xml_path, bt_path = write_eh_example(design, out)
        except ValidationError as e:
            print(e, file=sys.stderr)
            return 2
        print("RefGen EH  :", xml_path, "[PROPOSAL / ILLUSTRATIVE]")
        print("BT EH      :", bt_path, "[PROPOSAL / ILLUSTRATIVE]")
    if args.psc_config:
        from ip_waveform_export.export_psc_config import write_psc_config

        try:
            d = write_psc_config(design, out)
        except ValidationError as e:
            print(e, file=sys.stderr)
            return 2
        print("PSC config :", d, "[PROPOSAL]")
    if args.psps_json:
        print(
            "PSPS JSON  :", write_psps_json(design, out / f"{design.name}_psps_wf.json")
        )
    if args.ids:
        try:
            from ip_waveform_export.export_pulse_schedule_ids import (
                write_pulse_schedule_ids,
            )
        except ImportError as e:  # pragma: no cover
            print(f"IDS export unavailable: {e}", file=sys.stderr)
            return 3
        try:
            print(
                "IDS        :",
                write_pulse_schedule_ids(design, out / "ids", args.dd_version),
            )
        except ModuleNotFoundError as e:
            print(f"IDS export needs imas-python: {e}", file=sys.stderr)
            return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
