"""PSC-3: events/exception_handling/psc blocks -> four PSC mask files; D20 window cut."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest
import yaml
from psxml_rules import parse_psxml, reconstruct

from ip_waveform_export import ValidationError, load_design
from ip_waveform_export.cut import cut_design, cut_note
from ip_waveform_export.export_psc_config import (
    FILES,
    TYPE_ADDITIONS,
    parse_psc,
    write_psc_config,
)
from ip_waveform_export.export_refgen_xml import IMAS_TO_PCS_IP_SIGN, write_refgen_xml

TOOL = Path(__file__).resolve().parent.parent
PSC_EXAMPLE = TOOL / "examples" / "ip_105073_psc.yaml"
LIKE_EXAMPLE = TOOL / "examples" / "ip_105073_like.yaml"
T_CUT = 84.317598
GLOBMON_NS = "{http://www.ipp.mpg.de/2004/Schema/Exceptions_Desc}"


@pytest.fixture
def cut():
    return cut_design(load_design(PSC_EXAMPLE), T_CUT)


@pytest.fixture
def files(cut, tmp_path):
    d = write_psc_config(cut, tmp_path)
    return cut, {k: d / v for k, v in FILES.items()}


def _strip(tag: str) -> str:
    return tag.split("}")[-1]


# ----------------------------------------------------------------------------- D20 cut
def test_cut_shifts_first_segment_and_keeps_values():
    d = load_design(PSC_EXAMPLE)
    c = cut_design(d, T_CUT)
    first = c.segments[0]
    assert first.start == pytest.approx(T_CUT) and first.id == 0
    assert first.duration == pytest.approx(94.817598 - T_CUT)
    assert c.cut_info["shift_s"] == pytest.approx(5.1)
    assert c.waveform.time[0] == pytest.approx(T_CUT)
    grid = np.linspace(T_CUT, 94.817598, 501)
    assert np.allclose(
        c.waveform.sample(grid), d.waveform.sample(grid), rtol=0, atol=1e-6
    )
    assert "84.317598" in cut_note(c) and "-5.100000" in cut_note(c)


def test_cut_drops_earlier_segments_and_keeps_ids(tmp_path):
    d = load_design(LIKE_EXAMPLE)
    c = cut_design(d, 80.0)
    assert [s.name for s in c.segments] == ["flat-top", "ramp-down", "STOP"]
    assert [s.id for s in c.segments] == [1, 2, 99]
    assert c.cut_info["dropped_segments"] == ["ramp-up"]
    parsed = parse_psxml(write_refgen_xml(c, tmp_path / "c.xml"))
    first = parsed["segments"][0]
    assert first["attrib"]["wd_time"] == str(int(195 - 80))
    t0, v0 = first["trajectories"]["Ipl_ref"]["points"][0]
    assert t0 == 0.0
    assert v0 == pytest.approx(IMAS_TO_PCS_IP_SIGN * float(d.waveform.sample(80.0)))
    root = ET.parse(tmp_path / "c.xml").getroot()
    assert "PSC clock t = 0 at designer t = 80.000000 s" in root.get("comment")
    t, v = reconstruct(parsed, "Ipl_ref")
    assert np.allclose(
        np.interp(t, t, v), IMAS_TO_PCS_IP_SIGN * d.waveform.sample(t + 80.0)
    )


@pytest.mark.parametrize("t_cut", [-1.0, 270.0, 400.0])
def test_cut_outside_raises(t_cut):
    with pytest.raises(ValidationError):
        cut_design(load_design(LIKE_EXAMPLE), t_cut)


# ----------------------------------------------------------------------------- the four files
def test_schedule_parses_with_psxml_rules(files):
    c, f = files
    parsed = parse_psxml(f["refgen"])
    assert set(parsed["outputs"]) == {"Ipl_ref", "CSPF_curr_ref", "Rpl_ref", "Zpl_ref"}
    assert parsed["outputs"]["CSPF_curr_ref"]["dimension"] == "11"
    by_id = {s["attrib"]["id"]: s for s in parsed["segments"]}
    assert list(by_id) == ["0", "99", "21", "22", "41", "42"]
    flat = by_id["0"]["trajectories"]
    assert len(flat["CSPF_curr_ref"]["points"][0][1]) == 11
    assert flat["Zpl_ref"]["points"] == [
        (0.0, 0.24869786),
        (pytest.approx(10.5), 0.24869786),
    ]
    assert by_id["22"]["trajectories"] == {}  # hold: no trajectory -> last value held
    term = by_id["41"]["trajectories"]["Ipl_ref"]["points"]
    assert term[0] == (0.0, 15.25e6) and term[1] == (2.0, 0.0)
    t, v = reconstruct(parsed, "Ipl_ref")
    assert np.allclose(v, IMAS_TO_PCS_IP_SIGN * c.waveform.sample(t + T_CUT), atol=1e-6)


def test_globmon_format_and_events(files):
    c, f = files
    root = ET.parse(f["glob"]).getroot()
    assert _strip(root.tag) == "EXCEPTIONS"
    assert [_strip(ch.tag) for ch in root] == [
        "SCENARIOS",
        "SIGNAL_VALIDS",
        "MONITORINGS",
        "GOALS",
    ]
    # parserGlobMonConf.m: a section with child nodes (even only a comment) but no element
    # yields one nameless entry and fails; parse WITH comments to check it
    tb = ET.TreeBuilder(insert_comments=True)
    full = ET.parse(f["glob"], parser=ET.XMLParser(target=tb)).getroot()
    for sec in full:
        if not isinstance(sec.tag, str):
            continue
        elements = [
            ch for ch in sec if isinstance(ch.tag, str) and ch.tag is not ET.Comment
        ]
        assert elements or (len(sec) == 0 and not (sec.text or "").strip()), sec.tag
    mons = {
        m.get("output"): m.find(f"{GLOBMON_NS}SCRIPT").get("code")
        for m in root.iter(f"{GLOBMON_NS}MONITORING")
    }
    assert mons["glb_ps__ip_too_high"] == "{ip_ip__meas.value} > 15250000.0"
    assert mons["glb_ps__end_of_flux"].endswith(
        "or {glb_ps__end_of_flux} == 1"
    )  # latch
    z = mons["glb_ps__z_excursion"]
    assert (
        z.startswith("abs({z_meas.value} - 0.261) > 0.02") and "> 0.01" in z
    )  # hysteresis
    goal = next(root.iter(f"{GLOBMON_NS}GOAL")).find(f"{GLOBMON_NS}SCRIPT").get("code")
    assert goal == "{simTime} > 10.5"


def _keys(intf_root):
    keys = {}
    for u in intf_root.iter("USAGE"):
        name = u.get("name")
        keys[name[2:] if ":" in name else name] = (
            u.get("class"),
            u.find("SIGNAL").attrib,
        )
    return keys


def test_interface_declares_every_referenced_name(files):
    c, f = files
    keys = _keys(ET.parse(f["intf"]).getroot())
    assert keys["current_segment"][1]["value"] == "0"
    assert [k for k, v in keys.items() if v[0] == "Input"] == [
        "ip_ip__meas",
        "plasma_exist",
        "z_meas",
        "cs_margin",
    ]
    assert [k for k, v in keys.items() if v[0] == "Output"] == [
        "Ipl_ref",
        "CSPF_curr_ref",
        "Rpl_ref",
        "Zpl_ref",
    ]
    assert keys["CSPF_curr_ref"][1]["dimension"] == "11"
    assert keys["plasma_exist"][1]["name"] == "plasma_state__exist_diag"
    texts = [
        m.get("code") for m in ET.parse(f["glob"]).getroot().iter() if m.get("code")
    ]
    bt = ET.parse(f["bt"]).getroot()
    texts += [
        e.get(a)
        for e in bt.iter()
        for a in ("condition", "source", "target")
        if e.get(a)
    ]
    refs = {m.split(".")[0] for t in texts for m in re.findall(r"{([^}]+)}", t)}
    assert refs <= set(keys), refs - set(keys)
    for name in refs:  # Pcssignal inputs are read through .value, the others directly
        is_input = keys[name][0] == "Input"
        for t in texts:
            if f"{{{name}" in t:
                assert (f"{{{name}.value}}" in t) == is_input, (name, t)


def test_cut_sets_current_segment_default(tmp_path):
    def two_segments(doc):
        doc["segments"] = [
            {"name": "late-ramp", "id": 0, "start": 79.217598, "end": 80.0},
            {"name": "flat-top", "id": 1, "end": 94.817598},
            {"name": "STOP", "id": 99},
        ]

    c = cut_design(_variant(tmp_path, two_segments), T_CUT)
    assert [s.id for s in c.segments] == [1, 99]
    d = write_psc_config(c, tmp_path)
    assert (
        _keys(ET.parse(d / FILES["intf"]).getroot())["current_segment"][1]["value"]
        == "1"
    )


def test_btree_priorities_and_watchdogs_match_schedule(files):
    c, f = files
    bt = ET.parse(f["bt"]).getroot()
    top = bt.find("BehaviorTree/Fallback")
    assert top.get("name") == "FallbackNomEH" and top.get("Reactive") == "1"
    assert [ch.get("name") for ch in top] == [
        "FallHrdEHListSudden",
        "ParSegNom",
        "FallHrdEHList",
    ]
    sudden = top[0].find("Precondition")
    assert sudden.get("condition").startswith("{glb_ps__ip_too_high} == 1")
    assigns = sudden.findall("ForceFailure/Sequence/Action")
    assert (
        assigns[-1].get("source") == "41"
        and assigns[-1].get("target") == "{current_segment}"
    )
    par = top[1]
    assert par.get("mainTask") == "1" and par[1].get("mainTask") == "-1"
    soft_conds = [p.get("condition") for p in par[1]]
    assert soft_conds[0].startswith("{glb_ps__end_of_flux} == 1") and soft_conds[
        1
    ].startswith("{glb_ps__z_excursion} == 1")
    subtrees = {b.get("ID") for b in bt.findall("BehaviorTree")}
    assert {s.get("ID") for s in bt.iter("SubTree") if s.get("ID")} <= subtrees
    parsed = parse_psxml(f["refgen"])
    by_id = {s["attrib"]["id"]: s["attrib"] for s in parsed["segments"]}
    id_of = {a["name"]: a["id"] for a in by_id.values()}
    actions = [a for a in bt.iter("Action") if a.get("ID") == "RefGen"]
    assert actions
    for a in actions:
        assert a.get("typeAddition") in ("replace", *TYPE_ADDITIONS)
        seg = by_id[a.get("segmentID")]
        if (
            "wd_time" in seg
        ):  # schedule and BT carry identical watchdogs (BT values are the ones read)
            assert a.get("wd_time") == seg["wd_time"]
            assert a.get("wd_target") == id_of[seg["wd_target"]]
    z = next(a for a in actions if a.get("name") == "PathZHold")
    assert (
        z.get("condition") == "{glb_ps__z_excursion} == 0"
        and z.get("typeAddition") == "silence,replace"
    )
    eof = next(a for a in actions if a.get("name") == "PathEofRampdown")
    assert eof.get("condition") is None and eof.get("wd_target") == "42"
    term = next(a for a in actions if a.get("name") == "PathIpTermination")
    assert (
        term.get("signal") == "all"
        and term.get("entryRule") == "Linear"
        and term.get("wd_target") == "99"
    )


# ----------------------------------------------------------------------------- validation
def _variant(tmp_path, mutate):
    doc = yaml.safe_load(PSC_EXAMPLE.read_text())
    mutate(doc)
    p = tmp_path / "v.yaml"
    p.write_text(yaml.safe_dump(doc))
    return load_design(p)


@pytest.mark.parametrize(
    "mutate, msg",
    [
        (
            lambda d: d["exception_handling"]["hard_sudden"][0].update(event="nope"),
            "not defined",
        ),
        (
            lambda d: d["exception_handling"]["soft"][0].update(type_addition="add"),
            "type_addition",
        ),
        (lambda d: d["events"]["ip_too_high"].update(signal="ip_x"), "not declared"),
        (lambda d: d["psc"]["references"]["Rpl_ref"].pop("source"), "source"),
        (
            lambda d: d["exception_handling"]["soft"][1].update(wd_target="flat-top"),
            "wd_target",
        ),
        (
            lambda d: d["events"]["z_excursion"].update(release_threshold=0.03),
            "release_threshold",
        ),
        (lambda d: d["exception_handling"]["soft"][0].update(id=0), "ids"),
    ],
)
def test_invalid_blocks_raise(tmp_path, mutate, msg):
    d = _variant(tmp_path, mutate)
    with pytest.raises(ValidationError, match=msg):
        parse_psc(d)


def test_debounce_warns(tmp_path):
    d = _variant(
        tmp_path, lambda doc: doc["events"]["ip_too_high"].update(debounce=0.02)
    )
    with pytest.warns(UserWarning, match="debounce"):
        parse_psc(d)


def test_cli_psc_config_with_cut(tmp_path, capsys):
    import ip_waveform_export as pkg  # noqa: F401  (package importable)
    import importlib.util

    spec = importlib.util.spec_from_file_location("cli", TOOL / "ip_waveform_export.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    rc = cli.main(
        [
            "--yaml",
            str(PSC_EXAMPLE),
            "--out-dir",
            str(tmp_path),
            "--psc-config",
            "--cut-at",
            str(T_CUT),
        ]
    )
    assert rc == 0
    d = tmp_path / "psc_config_ip_105073_psc"
    assert sorted(p.name for p in d.iterdir()) == sorted(FILES.values())
    assert "D20 window cut" in capsys.readouterr().out


def test_ids_records_psc_clock_offset(cut, tmp_path):
    pytest.importorskip("imas")
    from ip_waveform_export.export_pulse_schedule_ids import (
        read_back,
        write_pulse_schedule_ids,
    )

    uri = write_pulse_schedule_ids(cut, tmp_path / "ids", "4.0.0")
    back = read_back(uri)
    assert back["time"][0] == pytest.approx(T_CUT)
    import imas

    with imas.DBEntry(uri, "r") as e:
        comment = str(e.get("pulse_schedule").ids_properties.comment)
    assert "psc_clock_offset_s = 84.317598" in comment
