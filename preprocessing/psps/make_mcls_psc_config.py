#!/usr/bin/env python3
"""MCLS integration: add the PSC -> MCLS hook signal to an existing PSC configuration folder.

Copies <src_dir> (the four PSC files written by the converter, export_psc_config.py:
PSCIntConfig.xml, PS.xml, BTree.xml, PSCGlobalMonConfig.xml) to <dst_dir> and declares one more
schedule OUTPUT, ``force_control_mode`` (bus field ``psc_ref__force_control_mode``), the way the
FWHL test of the old framework declares its mode reference ``mag_cntrlMdRef``
(pcssp@2233365 generic/psc/Tests/assets/PS_FWHLEH.xml:24-28; same mechanism as the constant
references CSPF_curr_ref / Rpl_ref / Zpl_ref of export_psc_config.py build_interface /
build_schedule):

* PSCIntConfig.xml: a USAGE class="Output" ``o:force_control_mode`` with SIGNAL
  ``psc_ref__force_control_mode`` (double, dimension 1, value 0), inserted after the last Output
  USAGE (the PSC_Out_Bus keeps the interface order, PSCIntConfig.xml -> PSC.MODEL.MaskCallBacks);
* PS.xml: a DECLARATIONS/OUTPUTS SIGNAL ``force_control_mode`` (value 0) and, in every SEGMENT that
  has SIGNAL_TRAJECTORIES, a constant SIGNAL_TRAJECTORY (Step entry, last exit) whose value is
  ``--force <segment name>=<mode>`` for the named segments and 0 elsewhere. Segments without
  trajectories (hold-type soft overlays) hold the last value (SignalGenClass.m:164-169). The STOP
  segment (``STOP_NAME``) also holds the last value unless ``--force STOP=<mode>`` is given: since
  2026-11-16 the converter writes an explicit Ipl_ref = 0 trajectory in STOP, and a default force 0
  there would hand the mode back to the MCLS at STOP (PSC files made before that have no STOP
  trajectory and give the same result).
  The BT (unchanged) plays a segment's trajectories with ``signal="all"`` for the nominal and the
  HARD segments only; the SOFT overlays name ``Ipl_ref`` and leave force_control_mode on the base
  trajectory (0). Hence a non-zero value is effective in HARD segments (ip_termination,
  eof_termination): "the PSC forces a magnetic control mode from a hard segment".
* BTree.xml, PSCGlobalMonConfig.xml: copied unchanged.

The MCLS block (controllers/CCS/mcls/third_party/MCLS.m lines 19-23) applies ``iactualmode = round(ForceControlMode)`` whenever it
is non-zero, on every tick; 0 = the MCLS decides.

usage: make_mcls_psc_config.py <src_dir> <dst_dir> [--force <segment>=<mode> ...]
example: the PSC configuration of cases/input/psc/ip_story_mockup/psc_config
(--force eof_termination=3 --force ip_termination=3); see the README.md of that folder.
"""

import argparse
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SIG = "force_control_mode"
STOP_NAME = "STOP"  # name of the terminal segment (ip_waveform_export model.STOP_NAME)
BUS = "psc_ref__force_control_mode"
DESC = (
    "MCLS ForceControlMode (0 = the MCLS decides, k = force magnetic control mode k); "
    "MCLS hook, make_mcls_psc_config.py"
)


def _parse(path):
    # keep the comments of the generated files (provenance of every value)
    return ET.parse(
        path, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    )


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("src_dir")
    ap.add_argument("dst_dir")
    ap.add_argument(
        "--force",
        action="append",
        default=[],
        metavar="SEGMENT=MODE",
        help="segment name and forced mode (integer); repeatable; others get 0",
    )
    a = ap.parse_args(argv)
    src, dst = Path(a.src_dir), Path(a.dst_dir)
    forced = {}
    for f in a.force:
        name, _, val = f.partition("=")
        if not name or not val.lstrip("-").isdigit():
            sys.exit(f"--force expects SEGMENT=INTEGER, got {f!r}")
        forced[name] = int(val)
    for fn in ("PSCIntConfig.xml", "PS.xml", "BTree.xml", "PSCGlobalMonConfig.xml"):
        if not (src / fn).is_file():
            sys.exit(f"{src / fn} missing")
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "BTree.xml", dst / "BTree.xml")
    shutil.copy2(src / "PSCGlobalMonConfig.xml", dst / "PSCGlobalMonConfig.xml")

    # --- interface
    tree = _parse(src / "PSCIntConfig.xml")
    root = tree.getroot()
    if any(s.get("name") == BUS for s in root.iter("SIGNAL")):
        sys.exit(f"{src}/PSCIntConfig.xml already declares {BUS}")
    usages = list(root)
    last_out = max(
        i
        for i, u in enumerate(usages)
        if u.tag == "USAGE" and u.get("class") == "Output"
    )
    u = ET.Element("USAGE", {"name": f"o:{SIG}", "class": "Output"})
    ET.SubElement(
        u,
        "SIGNAL",
        {
            "name": BUS,
            "type": "double",
            "dimension": "1",
            "value": "0",
            "description": DESC,
        },
    )
    root.insert(last_out + 1, u)
    root.insert(
        last_out + 1,
        ET.Comment(
            f" MCLS: PSC -> MCLS hook ({SIG}), added by make_mcls_psc_config.py "
        ),
    )
    ET.indent(root, space="\t")
    tree.write(dst / "PSCIntConfig.xml", encoding="UTF-8", xml_declaration=True)

    # --- schedule
    tree = _parse(src / "PS.xml")
    root = tree.getroot()
    outs = root.find("DECLARATIONS/OUTPUTS")
    if outs is None:
        sys.exit("PS.xml: no DECLARATIONS/OUTPUTS")
    if any(s.get("name") == SIG for s in outs.findall("SIGNAL")):
        sys.exit(f"{src}/PS.xml already declares {SIG}")
    outs.append(
        ET.Comment(
            f" {SIG}: PSC -> MCLS hook; 0 = MCLS decides; forced per segment: "
            f"{forced or 'none'} "
        )
    )
    ET.SubElement(
        outs,
        "SIGNAL",
        {
            "name": SIG,
            "signal_type": "Amplitude",
            "type": "double",
            "dimension": "1",
            "comment": "MCLS ForceControlMode (make_mcls_psc_config.py)",
            "value": "0",
        },
    )
    seen = set()
    rows = []
    for seg in root.find("SEGMENTS").findall("SEGMENT"):
        name = seg.get("name", "")
        trajs = seg.find("SIGNAL_TRAJECTORIES")
        if trajs is None or (name == STOP_NAME and name not in forced):
            rows.append((name, seg.get("id"), "hold last"))
            continue
        val = forced.get(name, 0)
        seen.add(name)
        wd = float(seg.get("wd_time", "0") or 0)
        tr = ET.SubElement(trajs, "SIGNAL_TRAJECTORY", {"name": SIG})
        ET.SubElement(tr, "ENTRY_RULE", {"is": "Step"})
        ET.SubElement(tr, "EXIT_RULE", {"is": "Last"})
        ET.SubElement(tr, "EXECUTION_RULE", {"is": "Step"})
        ref = ET.SubElement(tr, "REFERENCE")
        ET.SubElement(ref, "POINT", {"time": "0.0", "value": str(float(val))})
        if wd > 0:
            ET.SubElement(ref, "POINT", {"time": str(wd), "value": str(float(val))})
        rows.append((name, seg.get("id"), str(val)))
    missing = set(forced) - seen
    if missing:
        sys.exit(
            f"--force names not found among the segments with trajectories: {sorted(missing)}"
        )
    root.set(
        "comment",
        (root.get("comment") or "")
        + f"; MCLS: {SIG} output added (make_mcls_psc_config.py)",
    )
    ET.indent(root, space="  ")
    tree.write(dst / "PS.xml", encoding="ISO-8859-1", xml_declaration=True)
    print(f"{dst}: {BUS} declared; per segment (name, id, value): {rows}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
