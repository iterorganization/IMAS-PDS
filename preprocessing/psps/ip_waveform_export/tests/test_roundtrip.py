"""Round-trip tests of the three exports (run from the tool directory: python3 -I -m pytest -q)."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest
from psxml_rules import parse_psxml, reconstruct

from ip_waveform_export import (
    IpWaveform,
    PulseDesign,
    Segment,
    ValidationError,
    load_design,
)
from ip_waveform_export.export_psps_json import build_dataset, write_psps_json
from ip_waveform_export.export_refgen_xml import IMAS_TO_PCS_IP_SIGN, write_refgen_xml

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
REF_XML = TOOL / "reference" / "PS_NominalWaveforms.xml"
EXAMPLE = TOOL / "examples" / "ip_105073_like.yaml"


# --------------------------------------------------------------------------- helpers
def synthetic(stop_id: int = 99) -> PulseDesign:
    """Segment boundaries fall inside linear slopes (cuts are interpolated)."""
    wf = IpWaveform(
        time=[0.0, 2.0, 7.3, 20.0, 31.1, 40.0],
        value=[0.0, -1e5, -2.2e6, -5e6, -5e6, -0.3e6],
    )
    segs = [  # D8 identifiers: ramp-up 0, then 1, 2, STOP
        Segment("ramp-up", 0, 0.0, 13.37, "flat-top"),
        Segment("flat-top", 1, 13.37, 33.0, "ramp-down"),
        Segment("ramp-down", 2, 33.0, 40.0, "STOP"),
        Segment("STOP", stop_id, 40.0, 40.0, None),
    ]
    d = PulseDesign(
        waveform=wf,
        segments=segs,
        globals={"dd_version": "4.0.0", "pulse": 1},
        name="syn",
        stop_id=stop_id,
    )
    d.validate()
    return d


@pytest.fixture(params=["example", "synthetic"])
def design(request):
    return load_design(EXAMPLE) if request.param == "example" else synthetic()


def signature(el: ET.Element, path: str = "") -> set[tuple[str, frozenset]]:
    """Set of (tag path, attribute names) of an element subtree."""
    here = f"{path}/{el.tag}"
    out = {(here, frozenset(el.attrib))}
    for c in el:
        if isinstance(c.tag, str):  # skip comments
            out |= signature(c, here)
    return out


# --------------------------------------------------------------------------- (a) XML structure
def test_xml_structure_matches_reference(design, tmp_path):
    out = write_refgen_xml(design, tmp_path / "s.xml")
    ref = ET.parse(REF_XML).getroot()
    gen = ET.parse(out).getroot()  # parses
    assert set(gen.attrib) == set(ref.attrib)

    def ip_traj_sig(root):
        sigs = set()
        for seg in root.iter("SEGMENT"):
            for tr in seg.iter("SIGNAL_TRAJECTORY"):
                if tr.get("name") == "Ipl_ref":
                    sigs |= signature(tr)
        return sigs

    assert ip_traj_sig(gen) == ip_traj_sig(ref)

    def decl(r):
        return next(s for s in r.iter("SIGNAL") if s.get("name") == "Ipl_ref")

    def seg_attrs(r):
        return {frozenset(s.attrib) for s in r.iter("SEGMENT")}

    def rules(r):
        return {
            (e.tag, e.get("is"))
            for e in r.iter()
            if isinstance(e.tag, str) and e.tag.endswith("_RULE")
        }

    assert decl(gen).attrib == decl(ref).attrib
    assert seg_attrs(gen) == seg_attrs(ref)
    assert rules(gen) == rules(ref)
    stop = [s for s in gen.iter("SEGMENT") if s.get("name") == "STOP"]
    assert (
        len(stop) == 1
        and stop[0].get("id") == str(design.stop_id)
        and len(stop[0]) == 0
    )


def test_xml_segment_attributes(design, tmp_path):
    gen = ET.parse(write_refgen_xml(design, tmp_path / "s.xml")).getroot()
    segs = list(gen.iter("SEGMENT"))
    assert [s.get("name") for s in segs] == [s.name for s in design.segments]
    for el, seg in zip(segs[:-1], design.segments[:-1]):
        assert float(el.get("wd_time")) == pytest.approx(seg.duration, abs=1e-12)
        assert el.get("wd_target") == seg.wd_target
        pts = el.findall(".//POINT")
        assert float(pts[0].get("time")) == 0.0
        assert float(pts[-1].get("time")) == pytest.approx(seg.duration, abs=1e-12)
        assert all(float(p.get("value")) >= 0.0 for p in pts)  # positive PCS frame
    params = {p.get("name"): p.get("value") for p in gen.iter("PARAMETER")}
    assert params == {"ImasToPcsIpSign": "-1"}


# --------------------------------------------------------------------------- (b) parser rules
def test_mini_parser_reads_reference():
    parsed = parse_psxml(REF_XML)
    t, v = reconstruct(parsed, "Ipl_ref")
    assert t[0] == 0.0 and t[-1] == pytest.approx(100.0)
    assert v.max() == pytest.approx(4033875.0)


def test_parser_reconstructs_absolute_waveform(design, tmp_path):
    parsed = parse_psxml(write_refgen_xml(design, tmp_path / "s.xml"))
    t, v = reconstruct(parsed, design.waveform.signal_name)
    wf = design.waveform
    assert t[0] == pytest.approx(wf.time[0], abs=1e-9)
    assert t[-1] == pytest.approx(wf.time[-1], abs=1e-9)
    # every original vertex is reproduced
    for tv, iv in zip(wf.time, wf.value):
        k = np.argmin(np.abs(t - tv))
        assert abs(t[k] - tv) <= 1e-9
        assert abs(v[k] - IMAS_TO_PCS_IP_SIGN * iv) <= 1e-9 * max(
            1.0, np.abs(wf.value).max()
        )
    # and the piecewise-linear signal is identical on a fine grid
    grid = np.linspace(wf.time[0], wf.time[-1], 5001)
    order = np.argsort(t, kind="stable")
    rec = np.interp(grid, t[order], v[order])
    err = np.abs(rec - IMAS_TO_PCS_IP_SIGN * wf.sample(grid)).max()
    assert err <= 1e-9 * np.abs(wf.value).max()


# --------------------------------------------------------------------------- (c) JSON sanity
def test_psps_json_sanity(design, tmp_path):
    data = json.loads(write_psps_json(design, tmp_path / "d.json").read_text())
    assert set(data) >= {"pulse_schedule", "_note", "_sign_note"}
    assert "pulseconfig.iter.org" in data["_note"]
    assert data["_sign_note"].startswith("displayed as -Ip")
    ps = data["pulse_schedule"]
    assert set(ps) == {"name", "id", "segments"}
    assert [s["name"] for s in ps["segments"]] == [s.name for s in design.segments]
    ts, vs = [], []
    for js, seg in zip(ps["segments"], design.segments):
        assert set(js) == {"name", "id", "duration", "setpoints"}
        assert js["id"] == seg.id and js["duration"] == pytest.approx(seg.duration)
        if seg.is_stop:
            assert js["setpoints"] == {}
            continue
        sp = js["setpoints"]["ip_reference"]
        x, y = np.array(sp["x"]), np.array(sp["y"])
        assert x.size == y.size >= 2 and x[0] == 0.0 and np.all(np.diff(x) > 0)
        assert x[-1] == pytest.approx(seg.duration)
        assert np.all(y >= 0.0)  # displayed as -Ip: positive for ITER (D11)
        ts += list(seg.start + x)
        vs += list(y)
    rec = np.interp(design.waveform.time, np.array(ts), np.array(vs))
    assert np.allclose(
        rec,
        -design.waveform.value,
        rtol=0,
        atol=1e-9 * np.abs(design.waveform.value).max(),
    )
    assert build_dataset(design) == data


# --------------------------------------------------------------------------- validation rules
def _with(segs, **kw):
    d = synthetic()
    return PulseDesign(
        waveform=d.waveform, segments=segs, globals=d.globals, name="x", **kw
    )


def test_validation_rules():
    base = synthetic().segments
    bad_gap = [*base[:1], Segment("flat-top", 1, 14.0, 33.0, "ramp-down"), *base[2:]]
    bad_dup = [*base[:1], Segment("flat-top", 0, 13.37, 33.0, "ramp-down"), *base[2:]]
    bad_target = [*base[:1], Segment("flat-top", 1, 13.37, 33.0, "STOP"), *base[2:]]
    bad_first = [Segment("ramp-up", 5, 0.0, 13.37, "flat-top"), *base[1:]]
    bad_order = [
        *base[:1],
        Segment("flat-top", 2, 13.37, 33.0, "ramp-down"),
        Segment("ramp-down", 1, 33.0, 40.0, "STOP"),
        base[-1],
    ]
    bad_init = [
        Segment("init", 0, 0.0, 0.7, "ramp-up"),
        Segment("ramp-up", 1, 0.7, 13.37, "flat-top"),
        Segment("flat-top", 2, 13.37, 33.0, "ramp-down"),
        Segment("ramp-down", 3, 33.0, 40.0, "STOP"),
        base[-1],
    ]
    _with(bad_init).validate()  # a leading "init" segment is allowed if ids follow D8
    for segs in (bad_gap, bad_dup, bad_target, bad_first, bad_order):
        with pytest.raises(ValidationError):
            _with(segs).validate()
    with pytest.raises(ValidationError):  # STOP id 99 but 65535 required
        _with(base, stop_id=65535).validate()
    synthetic(stop_id=65535)  # IPP D15 convention accepted when configured
    wf = IpWaveform(time=[0.0, 1.0, 1.0, 40.0], value=[0, -1, -2, -3])
    with pytest.raises(ValidationError):
        PulseDesign(waveform=wf, segments=base, name="x").validate()


def test_stop_id_override_from_cli_value():
    with pytest.raises(ValidationError):
        load_design(EXAMPLE, stop_id=65535)  # example uses id 99


# --------------------------------------------------------------------------- (d) IDS round trip
#: DD versions tested and the Ip node each has (checked with imas-python 2.3.0).
DD_IP_NODE = {"3.42.0": "i_plasma", "4.0.0": "ip", "4.1.1": "ip"}


@pytest.mark.parametrize("dd", sorted(DD_IP_NODE))
def test_ids_roundtrip(design, dd, tmp_path):
    pytest.importorskip("imas")
    from ip_waveform_export.export_pulse_schedule_ids import (
        read_back,
        time_base,
        write_pulse_schedule_ids,
    )

    uri = write_pulse_schedule_ids(design, tmp_path / "ids", dd_version=dd)
    back = read_back(uri)
    t = time_base(design)
    assert back["dd_version"].startswith(dd)
    assert back["ip_node"] == DD_IP_NODE[dd]
    assert np.array_equal(back["time"], t) and np.array_equal(
        back["flux_control_time"], t
    )
    # IMAS sign kept in the IDS (ITER Ip < 0) whatever the YAML convention
    assert np.allclose(back["ip"], design.waveform.sample(t), rtol=0, atol=1e-9)
    assert np.all(back["ip"] <= 0.0)
    assert back["events"] == [
        (f"segment:{s.id}:{s.name}", s.start, s.duration, "pcs_segment")
        for s in design.segments
    ]


def test_ids_default_dd_and_time_offset(tmp_path):
    pytest.importorskip("imas")
    from ip_waveform_export.export_pulse_schedule_ids import (
        read_back,
        time_base,
        write_pulse_schedule_ids,
    )

    d = synthetic()
    d.globals = {}  # no dd_version -> DEFAULT_DD_VERSION 4.0.0
    d.time_offset_s = 12.5
    back = read_back(write_pulse_schedule_ids(d, tmp_path / "ids"))
    assert back["dd_version"].startswith("4.0.0") and back["ip_node"] == "ip"
    assert np.allclose(back["time"], time_base(d) + 12.5, rtol=0, atol=1e-12)
    assert [e[1] for e in back["events"]] == pytest.approx(
        [s.start + 12.5 for s in d.segments]
    )
