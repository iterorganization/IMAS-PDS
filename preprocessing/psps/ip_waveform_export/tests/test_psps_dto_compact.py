"""Tests of psps_dto_compact: the compact YAML view must round-trip psps-dto exactly.

External inputs (the PSPS qualification-server mock and the PDS exports in the pds docs
repository) are skipped when absent; the in-test DTOs (build_dto on the example design,
and a hand-written fixture with unusual constructs) always run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest
import yaml
from ip_waveform_export import load_design
from ip_waveform_export import psps_dto_compact as pc
from ip_waveform_export.export_psps_dto import build_dto, design_from_pulse_design

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
DOCS = Path(
    os.environ.get("PSPS_DOCS_DIR", "/home/ITER/schneim/public/git/pds/docs/psps")
)
ORACLE = Path(
    os.environ.get(
        "PSPS_DTO_ORACLE",
        str(DOCS / "From_PSPS_GUI_JSON" / "PCS Mock Pulse Schedule.json"),
    )
)
EXTERNAL = [
    ORACLE,
    DOCS / "work_notes/psc5_run_inputs/D_eof/D_eof_psps_dto.json",
    DOCS / "work_notes/psc5_run_inputs/D_eof/D_eof_psps_dto_extended.json",
    DOCS / "presentation_dataset/105073_psps_dto.json",
    DOCS / "presentation_dataset/105073_psps_dto_extended.json",
]


def assert_exact(a, b) -> None:
    assert json.dumps(a) == json.dumps(b)
    assert a == b


def via_yaml(compact: dict, tmp_path: Path) -> list:
    p = pc.dump_compact_yaml(compact, tmp_path / "x.compact.yaml", "x.json")
    return pc.from_compact(pc.load_compact_yaml(p))


def f32(x: float) -> float:
    return float(np.float32(x))


def node(t: str, v, **kw) -> dict:
    return {"type": t, "value": v, **kw}


def wave(x, y) -> dict:
    return node(
        "struct",
        {
            "xValues": node("array", x, element_type="float32", display={"units": "s"}),
            "yValues": node("array", y, element_type="float32", display={"units": "A"}),
        },
    )


def setpoint(sid: str, wbc: dict) -> dict:
    cat = node(
        "struct",
        {
            "1": node(
                "struct", {"id": node("string", "1"), "name": node("string", "Off")}
            )
        },
    )
    value = {
        "id": node("string", "controller-magnetics-1"),
        "shape_control": cat,
        "ip_control": cat,
        "vs_control": cat,
        "waveforms_by_circuit": node("struct", wbc),
    }
    props = {
        "id": node("string", sid, constraints={"id": True}),
        "name": node("string", "Magnetics Controller Setpoint"),
        "value": node("struct", value),
    }
    return node("struct", {"properties": node("struct", props)})


def fixture_dto() -> list:
    """Hand-written DTO with the constructs the generator never writes."""
    seg1, seg2 = (
        "b2222222-2222-4222-8222-222222222222",
        "d4444444-4444-4444-8444-444444444444",
    )
    sp1, sp2 = (
        "c3333333-3333-4333-8333-333333333333",
        "e5555555-5555-4555-8555-555555555555",
    )
    x = [0, f32(0.05), f32(0.1), 2.0]
    shared_t = {
        "cs1": wave(x, [0, f32(15.6), f32(22641.9), 1e6]),
        "pf1": wave(x, [1, 2, 3, f32(-0.3)]),
    }
    with_t_circuit = {"t": wave([0, 1], [1, 2]), "pf2": wave([0, 1], [3, 4])}
    seg = {
        seg1: node(
            "struct",
            {
                "properties": node(
                    "struct",
                    {
                        "id": node("string", seg1, constraints={"id": True}),
                        "name": node("string", "Ramp-up é → 1"),
                        "duration": node(
                            "float64", 5, constraints={"range": {"min": 0, "max": 1e5}}
                        ),
                    },
                ),
                "setpoints": node("struct", {sp1: setpoint(sp1, shared_t)}),
            },
        ),
        seg2: node(
            "struct",
            {
                "properties": node(
                    "struct",
                    {
                        "id": node("string", seg2, constraints={"id": True}),
                        "name": node("string", "1"),
                        "duration": node("float64", 0.1 + 0.2),
                    },
                ),
                "setpoints": node("struct", {sp2: setpoint(sp2, with_t_circuit)}),
            },
        ),
    }
    misc = {
        # float32 field holding a value that is not an exact float32
        "not_f32": node("float32", 0.1),
        "f32_list_not_exact": node("array", [0.1, f32(0.2)], element_type="float32"),
        "int_in_f32": node("float32", 20000),
        "tiny": node("float32", f32(1e-30)),
        "big": node("float32", f32(3e38)),
        # unusual key order and an unknown attribute
        "reordered": {"value": True, "type": "bool"},
        "extra_attr": {"type": "int32", "value": 3, "note": {"why": "test"}},
        # malformed nodes: must stay typed (raw)
        "struct_with_list": {"type": "struct", "value": [1, 2]},
        "not_a_node": {"just": "a dict"},
        "nested_array": node("array", [[1, 2], [3]], element_type="int32"),
        "empty": node("struct", {}),
        "strings": node("list", [node("string", "yes"), node("string", "null")]),
        "dotted.key": node("string", "x"),
    }
    root = node(
        "struct",
        {
            "component_type": node("string", "pulse_schedule"),
            "segments": node("struct", seg),
            "misc": node("struct", misc),
        },
    )
    return [{"encoding": "psps-dto/v1.0/JSON"}, root]


def example_dtos() -> tuple[list, list]:
    return build_dto(
        design_from_pulse_design(load_design(TOOL / "examples" / "ip_105073_psc.yaml"))
    )


# --------------------------------------------------------------------------- self-contained
@pytest.mark.parametrize("which", ["strict", "extended"])
def test_round_trip_of_build_dto(which: str, tmp_path: Path) -> None:
    dto = example_dtos()[0 if which == "strict" else 1]
    compact = pc.to_compact(dto)
    assert list(compact) == ["pulse", "units", "_schema"]
    assert_exact(pc.from_compact(compact), dto)
    assert_exact(via_yaml(compact, tmp_path), dto)
    assert not compact["_schema"]["raw"]


def test_round_trip_of_the_fixture(tmp_path: Path) -> None:
    dto = fixture_dto()
    compact = pc.to_compact(dto)
    assert_exact(pc.from_compact(compact), dto)
    assert_exact(via_yaml(compact, tmp_path), dto)
    sch = compact["_schema"]
    assert sorted(sch["raw"]) == [
        "pulse.misc.nested_array",
        "pulse.misc.not_a_node",
        "pulse.misc.struct_with_list",
    ]
    assert sorted(sch["float64_values"]) == [
        "pulse.misc.f32_list_not_exact",
        "pulse.misc.not_f32",
    ]
    assert sch["shared_catalogues"] == ["shape_control", "ip_control", "vs_control"]


def test_compact_rules_on_the_fixture() -> None:
    compact = pc.to_compact(fixture_dto())
    pulse = compact["pulse"]
    segs = list(pulse["segments"].values())
    v1 = segs[0]["setpoints"]["c3333333-3333-4333-8333-333333333333"]["properties"][
        "value"
    ]
    v2 = segs[1]["setpoints"]["e5555555-5555-4555-8555-555555555555"]["properties"][
        "value"
    ]
    # catalogues shared, markers in place, key order kept
    assert list(v1) == [
        "id",
        "shape_control",
        "ip_control",
        "vs_control",
        "waveforms_by_circuit",
    ]
    assert v1["shape_control"] == pc.SHARED
    assert pulse["catalogues"]["vs_control"]["1"]["name"] == "Off"
    # one time base -> t + circuits; a circuit named t keeps the original form
    assert list(v1["waveforms_by_circuit"]) == ["t", "cs1", "pf1"]
    assert v1["waveforms_by_circuit"]["cs1"] == [0, 15.6, 22641.9, 1e6]
    assert v1["waveforms_by_circuit"]["t"] == [0, 0.05, 0.1, 2.0]
    assert v2["waveforms_by_circuit"]["t"] == {"xValues": [0, 1], "yValues": [1, 2]}
    # malformed node kept typed, non-float32 value kept as is, ints stay ints
    assert pulse["misc"]["struct_with_list"] == {"type": "struct", "value": [1, 2]}
    assert pulse["misc"]["not_f32"] == 0.1
    assert pulse["misc"]["int_in_f32"] == 20000
    assert isinstance(pulse["misc"]["int_in_f32"], int)


def test_yaml_text_style(tmp_path: Path) -> None:
    compact = pc.to_compact(fixture_dto())
    text = pc.compact_yaml_text(compact, "fixture.json")
    lines = text.splitlines()
    assert lines[0].startswith("# Reading view of fixture.json")
    assert "to-json" in lines[1]
    assert [ln for ln in lines if not ln.startswith((" ", "#"))] == [
        "pulse:",
        "units:",
        "_schema:",
    ]
    assert "      t: [0, 0.05, 0.1, 2.0]" in text
    assert "b2222222-2222-4222-8222-222222222222:  # segment Ramp-up é → 1" in text
    assert "1.0e-30" in text  # float32 1e-30, readable back as a YAML float
    loaded = yaml.safe_load(text)
    assert isinstance(loaded["pulse"]["misc"]["tiny"], float)
    assert loaded["units"]["setpoint.waveforms_by_circuit.*.yValues"] == "A"


def test_layout_detection_and_bytes() -> None:
    dto = fixture_dto()
    for lay in (
        {"indent": 2, "ensure_ascii": True, "arrays_one_line": False, "newline": False},
        {"indent": 4, "ensure_ascii": False, "arrays_one_line": False, "newline": True},
        {"indent": 2, "ensure_ascii": True, "arrays_one_line": True, "newline": True},
    ):
        text = pc.json_text(dto, lay)
        found = pc.detect_json_layout(text, dto)
        assert found is not None
        assert pc.json_text(dto, found) == text
    assert pc.detect_json_layout(json.dumps(dto, indent=2) + "  ", dto) is None


def test_cli_both_ways(tmp_path: Path) -> None:
    src = tmp_path / "fixture.json"
    raw = json.dumps(fixture_dto(), indent=2) + "\n"
    src.write_text(raw, encoding="utf-8")
    assert pc.main(["to-yaml", str(src)]) == 0
    out = tmp_path / "fixture.compact.yaml"
    assert out.exists()
    assert pc.main(["to-json", str(out)]) == 0
    assert (tmp_path / "fixture.compact.json").read_text(encoding="utf-8") == raw


def test_cli_refuses_inexact_round_trip(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "fixture.json"
    src.write_text(json.dumps(fixture_dto(), indent=2), encoding="utf-8")
    real = pc.from_compact

    def lossy(c):
        doc = real(c)
        doc[0]["encoding"] = "other"
        return doc

    monkeypatch.setattr(pc, "from_compact", lossy)
    assert pc.main(["to-yaml", str(src)]) == 1
    assert not (tmp_path / "fixture.compact.yaml").exists()


# --------------------------------------------------------------------------- external files
@pytest.mark.parametrize("path", EXTERNAL, ids=lambda p: p.name)
def test_round_trip_of_external_files(path: Path, tmp_path: Path) -> None:
    if not path.exists():
        pytest.skip(f"absent: {path}")
    text = path.read_text(encoding="utf-8")
    dto = json.loads(text)
    layout = pc.detect_json_layout(text, dto)
    compact = pc.to_compact(dto, layout)
    assert_exact(pc.from_compact(compact), dto)
    back = via_yaml(compact, tmp_path)
    assert_exact(back, dto)
    assert layout is not None, "JSON layout not detected"
    assert pc.json_text(back, layout) == text
    assert not compact["_schema"]["raw"]
