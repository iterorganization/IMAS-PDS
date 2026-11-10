"""Export to a BEST-GUESS PSPS "WF" dataset JSON (target format 3).

The PCS dataset schema is not available; the structure below is inferred from
IDM 97XLXP (slide 10) and IDM ATPUWU (2024 demo: segments init / setup /
startup / plasma / soft-landing / stop, per-segment set-points ``segment_id``,
``ip_reference``, ``modulation_gate`` with X/Y vectors, X relative to the
segment start). Only ``ip_reference`` is written.

SIGN RULE (decision D11, 2026-11-02): the values are written as displayed to the
Session Leader, i.e. -Ip (positive for ITER), y = IMAS_TO_MINUS_IP_SIGN x Ip; a
``_sign_note`` field says so. The sign convention of the real PSPS dataset is
still to be confirmed (open item).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .cut import cut_note
from .model import IMAS_TO_MINUS_IP_SIGN, PulseDesign, segment_points

NOTE = (
    "structure inferred from IDM 97XLXP slide 10 and ATPUWU; to be replaced by the "
    "PCS v1.1 dataset schema from pulseconfig.iter.org"
)
SIGN_NOTE = "displayed as -Ip; sign convention of the real PSPS dataset to be confirmed"


def build_dataset(design: PulseDesign) -> dict:
    wf = design.waveform
    segments = []
    for seg in design.segments:
        setpoints = {}
        if not seg.is_stop:
            x, y = segment_points(wf, seg)
            setpoints[wf.designer_name] = {
                "x": [float(a) for a in x],
                "y": [float(IMAS_TO_MINUS_IP_SIGN * b) + 0.0 for b in y],
            }
        segments.append(
            {
                "name": seg.name,
                "id": seg.id,
                "duration": float(seg.duration),
                "setpoints": setpoints,
            }
        )
    return {
        "pulse_schedule": {
            "name": design.name,
            "id": design.globals.get("pulse", design.name),
            "segments": segments,
        },
        "_note": NOTE,
        "_status": "BEST-GUESS",
        "_sign_note": SIGN_NOTE,
        "_conventions": {
            "x": "s, relative to the segment start",
            "y": f"{wf.units}, -Ip as displayed to the Session Leader (ITER: positive)",
            "time_origin": design.time_origin,
            "time_offset_s": design.time_offset_s,
            "source": wf.ids_path,
            "dd_version": design.globals.get("dd_version"),
            **(
                {"psc_clock_offset_s": design.cut_at, "cut_note": cut_note(design)}
                if design.cut_at is not None
                else {}
            ),
        },
    }


def dumps(dataset: dict) -> str:
    """Indented JSON with numeric arrays kept on one line."""
    text = json.dumps(dataset, indent=2)
    return re.sub(
        r"\[\s+([-+0-9.eE,\s]+?)\s+\]",
        lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]",
        text,
    )


def write_psps_json(design: PulseDesign, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.write_text(dumps(build_dataset(design)) + "\n", encoding="utf-8")
    return out_path
