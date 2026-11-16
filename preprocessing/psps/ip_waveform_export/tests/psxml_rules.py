"""Python re-implementation of the reading rules of parsePSXML.m, shared by the tests."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np


def parse_psxml(path: Path) -> dict:
    """Mini re-implementation of the reading rules of parsePSXML.m (pcssp-nightly@ebf3ee0).

    Mirrors: DECLARATIONS/PARAMETERS (ListParams only defined there, needed by every
    segment), OUTPUTS/SIGNAL attributes; SEGMENT attributes (id, name, others kept);
    SIGNAL_TRAJECTORIES/SIGNAL_TRAJECTORY with exactly ONE attribute (Attributes.Value),
    signal must be declared; REFERENCE whose first child is POINT (exactly two
    attributes time/value, str2double for a dimension-1 double) or FUNCTION (``code``,
    with the PARAMETER names replaced by their values as strrep does), anything else
    is an error; ENTRY/EXECUTION/EXIT_RULE one attribute each.
    """
    root = ET.parse(path).getroot()
    assert root.tag == "SCHEDULE"
    decl = root.find("DECLARATIONS")
    params = decl.find("PARAMETERS") if decl is not None else None
    outputs = (
        {s.get("name"): dict(s.attrib) for s in decl.find("OUTPUTS")}
        if decl is not None
        else {}
    )
    params_values = (
        {p.get("name"): p.get("value") for p in params} if params is not None else {}
    )
    segments = []
    for seg in root.find("SEGMENTS"):
        attrib = dict(seg.attrib)
        trajs = {}
        for child in seg:
            if child.tag != "SIGNAL_TRAJECTORIES":
                continue
            if params is None:
                raise RuntimeError(
                    "parsePSXML.m: ListParams undefined (no PARAMETERS block)"
                )
            for tr in child:
                assert len(tr.attrib) == 1, (
                    "SIGNAL_TRAJECTORY needs exactly one attribute"
                )
                (name,) = tr.attrib.values()
                if name not in outputs:
                    raise RuntimeError(
                        f"signal {name} in segment {attrib['name']} is not declared"
                    )
                rec = {}
                for el in tr:
                    if el.tag == "REFERENCE":
                        pts = list(el)
                        if pts and pts[0].tag == "FUNCTION":
                            code = pts[0].get("code", "")
                            for pname, pval in params_values.items():
                                code = code.replace(pname, pval)  # strrep of ListParams
                            rec["code"] = code
                            rec["points"] = []
                            continue
                        if not pts or pts[0].tag != "POINT":
                            raise RuntimeError("REFERENCE definition incorrect")
                        vals = []
                        for p in pts:
                            assert set(p.attrib) == {"time", "value"}
                            dim = int(outputs[name].get("dimension", "1"))
                            raw = p.get("value")
                            if dim == 1:
                                value = float(raw)  # str2double
                            elif "," in raw:
                                value = [
                                    float(x) for x in raw.strip("()[] ").split(",")
                                ]
                            else:  # parser fills with the declared default value
                                value = [float(outputs[name]["value"])] * dim
                            vals.append((float(p.get("time")), value))
                        rec["points"] = vals
                    elif el.tag in ("ENTRY_RULE", "EXECUTION_RULE", "EXIT_RULE"):
                        assert len(el.attrib) == 1
                        rec[el.tag] = next(iter(el.attrib.values()))
                trajs[name] = rec
        segments.append({"attrib": attrib, "trajectories": trajs})
    return {"outputs": outputs, "segments": segments}


def reconstruct(parsed: dict, signal: str) -> tuple[np.ndarray, np.ndarray]:
    """Absolute waveform: follow the wd_target chain from the first segment, t0 += wd_time."""
    by_name = {s["attrib"]["name"]: s for s in parsed["segments"]}
    seg = parsed["segments"][0]
    t0, ts, vs = 0.0, [], []
    seen = set()
    while seg is not None and seg["attrib"]["name"] not in seen:
        seen.add(seg["attrib"]["name"])
        tr = seg["trajectories"].get(signal)
        if tr is None:
            break
        for t, v in tr["points"]:
            ts.append(t0 + t)
            vs.append(v)
        t0 += float(seg["attrib"]["wd_time"])
        seg = by_name.get(seg["attrib"].get("wd_target"))
    return np.array(ts), np.array(vs)
