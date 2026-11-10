"""PROPOSAL / ILLUSTRATIVE exception-handling example (--refgen-eh-example, D9)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest
from psxml_rules import parse_psxml, reconstruct

from ip_waveform_export import ValidationError, load_design
from ip_waveform_export.export_refgen_eh_example import write_eh_example
from ip_waveform_export.export_refgen_xml import IMAS_TO_PCS_IP_SIGN

TOOL = Path(__file__).resolve().parent.parent
EH_EXAMPLE = TOOL / "examples" / "ip_105073_like_with_exceptions.yaml"
REF = TOOL / "reference"


@pytest.fixture
def outputs(tmp_path):
    d = load_design(EH_EXAMPLE)
    xml_path, bt_path = write_eh_example(d, tmp_path)
    return d, xml_path, bt_path


def test_reference_fwhl_files_parse():
    parsed = parse_psxml(REF / "PS_FWHLEH.xml")
    seg20 = next(s for s in parsed["segments"] if s["attrib"]["id"] == "20")
    assert seg20["trajectories"]["mag_gapRef"]["code"] == "{fwhl_dGap.value}"
    bt = ET.parse(REF / "BTreeFWHL.xml").getroot()
    assert any(a.get("typeAddition") == "silence,offset" for a in bt.iter("Action"))


def test_eh_schedule_parses_with_psxml_rules(outputs):
    d, xml_path, _ = outputs
    parsed = parse_psxml(xml_path)
    by_id = {s["attrib"]["id"]: s for s in parsed["segments"]}
    assert list(by_id) == ["0", "1", "2", "99", "20", "41"]
    assert len(by_id) == len(parsed["segments"])  # ids unique
    soft = by_id["20"]
    assert soft["attrib"] == {
        "name": "ip_reduce_on_heating_loss",
        "id": "20",
        "wd_time": "30",
        "wd_target": "ip_termination",
    }
    assert soft["trajectories"]["Ipl_ref"]["points"] == [(0.0, 1.0), (10.0, 0.8)]
    hard = by_id["41"]
    assert hard["attrib"]["wd_target"] == "STOP"
    pts = hard["trajectories"]["Ipl_ref"]["points"]
    assert pts[0] == (0.0, pytest.approx(15.0e6)) and pts[-1] == (60.0, 0.0)
    for s in parsed["segments"]:  # every wd_target names an existing segment
        tgt = s["attrib"].get("wd_target")
        assert tgt is None or tgt in {x["attrib"]["name"] for x in parsed["segments"]}
    # the nominal chain still reconstructs the nominal waveform
    t, v = reconstruct(parsed, "Ipl_ref")
    wf = d.waveform
    grid = np.linspace(wf.time[0], wf.time[-1], 2001)
    order = np.argsort(t, kind="stable")
    rec = np.interp(grid, t[order], v[order])
    assert np.abs(rec - IMAS_TO_PCS_IP_SIGN * wf.sample(grid)).max() <= 1e-9 * 15e6
    assert "PROPOSAL / ILLUSTRATIVE" in xml_path.read_text(encoding="iso-8859-1")


def test_eh_btree_well_formed_with_expected_nodes(outputs):
    _, _, bt_path = outputs
    text = bt_path.read_text()
    assert (
        text.startswith('<?xml version="1.0"?>') and "PROPOSAL / ILLUSTRATIVE" in text
    )
    root = ET.parse(bt_path).getroot()  # well-formed
    assert root.tag == "root" and root.get("main_tree_to_execute") == "BehaviorTree"
    trees = {bt.get("ID"): bt for bt in root.findall("BehaviorTree")}
    main = trees.pop("BehaviorTree")
    top = main[0]
    assert top.tag == "Fallback" and top.get("Reactive") == "1"
    assert [c.get("name") for c in top] == [
        "FallHrdEHListSudden",
        "ParSegNom",
        "FallHrdEHList",
    ]

    sudden = top[0].find("Precondition")
    assert sudden.get("condition") == "{glb_ps__ip_too_high} == 1"
    assigns = sudden.findall(".//Action[@ID='AssignValue']")
    assert (
        assigns[-1].get("source") == "41"
        and assigns[-1].get("target") == "{current_segment}"
    )

    nominal = top[1].find("Fallback")
    conds = [p.get("condition") for p in nominal.findall("Precondition")]
    assert conds == [f"{{current_segment}} == {i}" for i in (0, 1, 2, 99)]
    soft_pre = top[1].find("Parallel/Precondition")
    assert soft_pre.get("condition") == "{heating_loss} == 1"

    # every SubTree referenced is defined and listed in TreeNodesModel
    refs = {s.get("ID") for s in main.iter("SubTree")}
    model = {s.get("ID") for s in root.find("TreeNodesModel").findall("SubTree")}
    assert refs == set(trees) == model

    actions = {
        a.get("segmentID"): a for bt in trees.values() for a in bt.iter("Action")
    }
    assert set(actions) == {"0", "1", "2", "99", "20", "41"}
    soft = actions["20"]
    assert {
        k: soft.get(k)
        for k in ("ID", "signal", "typeAddition", "condition", "wd_target")
    } == {
        "ID": "RefGen",
        "signal": "Ipl_ref",
        "typeAddition": "silence,scale",
        "condition": "{heating_loss} == 0",
        "wd_target": "41",
    }
    assert actions["41"].get("typeAddition") == "replace"
    assert actions["41"].get("wd_target") == "99"
    # nominal watchdogs: duration and next id
    assert [
        (actions[i].get("wd_time"), actions[i].get("wd_target")) for i in "012"
    ] == [
        ("70", "1"),
        ("125", "2"),
        ("75", "99"),
    ]
    assert actions["99"].get("wd_target") == "99"  # STOP self-loop as in pcs@add-AM


def test_eh_requires_exceptions_block(tmp_path):
    d = load_design(TOOL / "examples" / "ip_105073_like.yaml")
    with pytest.raises(ValidationError, match="no 'exceptions:' block"):
        write_eh_example(d, tmp_path)
