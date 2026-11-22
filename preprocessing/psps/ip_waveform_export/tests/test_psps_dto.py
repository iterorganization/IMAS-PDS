"""Tests of export_psps_dto (psps-dto/v1.0/JSON, strict + extended).

The schema oracle is the file saved from the PSPS qualification server on 2026-11-09
("PCS Mock Pulse Schedule"); give its path in $PSPS_DTO_ORACLE, else the default below
is used; the conformity tests are skipped when it is absent.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

import numpy as np
import pytest
from ip_waveform_export import load_design
from ip_waveform_export.export_psps_dto import (
    ARRAY_ELEMENT_TYPES,
    COILS,
    ENCODING,
    IMAS_TO_PCS_CURRENT_SIGN,
    KEY_RE,
    MCLS_MAP,
    MODE_WINDOW_UNITS,
    NODE_TYPES,
    PSPS_GAP_SLOTS,
    _f32,
    _list,
    _str,
    _struct,
    build_dto,
    design_from_pulse_design,
    design_from_two_file,
    strip_extensions,
    type_signature,
    write_psps_dto,
)

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
ORACLE = Path(
    os.environ.get(
        "PSPS_DTO_ORACLE",
        "/home/ITER/schneim/public/git/pds/docs/psps/From_PSPS_GUI_JSON/"
        "PCS Mock Pulse Schedule.json",
    )
)
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
RTOL, ATOL = 1e-6, 1e-3


# --------------------------------------------------------------------------- helpers
def signatures(doc: list) -> dict[str, set[tuple[str, str]]]:
    """{generalised path: {(type, json of the other node attributes)}}; UUID keys -> <uuid>."""
    out: dict[str, set[tuple[str, str]]] = {}

    def walk(n: dict, path: str) -> None:
        extra = {k: v for k, v in n.items() if k not in ("type", "value")}
        out.setdefault(path, set()).add((n["type"], json.dumps(extra, sort_keys=True)))
        if n["type"] == "struct":
            for k, c in n["value"].items():
                walk(c, path + "/" + ("<uuid>" if UUID_RE.fullmatch(k) else k))
        elif n["type"] == "list":
            for c in n["value"]:
                walk(c, path + "[]")

    assert doc[0] == {"encoding": ENCODING}
    assert len(doc) == 2
    walk(doc[1], "")
    return out


def without_mode_window_units(
    sig: dict[str, set[tuple[str, str]]],
) -> dict[str, set[tuple[str, str]]]:
    """Remove the one allowed addition to the mock: display units on the mode windows.

    Asserts that on ``.../modes[]/{t0s,t0f,ip0s,ip0f}`` the only extra attribute is
    exactly ``display: {"units": MODE_WINDOW_UNITS[field]}``, then drops it so the rest
    of the structure is compared strictly with the mock.
    """
    out: dict[str, set[tuple[str, str]]] = {}
    for path, ss in sig.items():
        field = path.rsplit("/", 1)[-1]
        if path.endswith("modes[]/" + field) and field in MODE_WINDOW_UNITS:
            want = json.dumps({"display": {"units": MODE_WINDOW_UNITS[field]}})
            assert {e for _, e in ss} == {want}, (path, ss)
            out[path] = {(t, "{}") for t, _ in ss}
        else:
            out[path] = set(ss)
    return out


def two_file_design() -> dict:
    """Three segments, two modes, every waveform family, an overlay, PF5/PF6."""
    t = [0.0, 10.0, 50.0, 100.0]
    waves: dict = {
        "plasma_current": {
            "pulse_schedule/flux_control/ip/reference": [
                {"time": t, "value": [0.0, -2e6, -15e6, -15e6]}
            ]
        },
        "rzip": {
            "pulse_schedule/position_control/current_centroid/r/reference": [
                {"time": [0.0, 100.0], "value": [6.0, 6.2]}
            ],
            "pulse_schedule/position_control/current_centroid/z/reference": [
                {"time": [0.0, 100.0], "value": [0.3, 0.3]}
            ],
        },
        "isoflux": {},
        "gaps": {  # PDS gap 3 = slot gap01 (PSPS_GAP_SLOTS[0])
            "pulse_schedule/position_control/gap(3)/value/reference": [
                {"time": [10.0, 100.0], "value": [0.2, 0.1]}
            ],
            "pulse_schedule/position_control/gap(3)/name": "outer_midplane",
        },
        "cspf": {},
    }
    for k in (1, 2):
        for c, v in (("r", 7.0 + k), ("z", 0.5 * k)):
            waves["isoflux"][
                f"pulse_schedule/position_control/boundary_outline({k})/{c}/reference"
            ] = [{"time": [0.0, 100.0], "value": [v, v + 0.1]}]
    for c, v in (("r", 5.05), ("z", -3.3)):
        waves["isoflux"][
            f"pulse_schedule/position_control/x_point(1)/{c}/reference"
        ] = [{"time": [10.0, 100.0], "value": [v, v]}]
    for i, _ in enumerate(COILS, 1):
        waves["cspf"][f"pulse_schedule/pf_active/coil({i})/current/reference"] = [
            {"time": [0.0, 100.0], "value": [1000.0 * i, -1000.0 * i]}
        ]
    segs = {
        "pulse": {"number": 1},
        "events": {
            "diverted": {
                "test": "x_point_in_box",
                "box": {"r": 5.05, "z": -3.3, "dr": 0.2, "dz": 0.25},
            },
            "z_excursion": {
                "test": "|Z - Z_ref| >= 2 cm",
                "release": "|Z - Z_ref| < 1 cm",
            },
            "ip_too_high": {"test": "|Ip| >= 15.25 MA", "latch": True},
        },
        "modes": {
            "lim": {
                "shape_ip": "rzip",
                "ip": "rzip",
                "vs": "vs1",
                "snu": True,
                "cla": False,
            },
            "div": {
                "shape_ip": "gaps",
                "ip": "kcurr",
                "vs": "vs1_vs3",
                "snu": False,
                "cla": True,
            },
        },
        "segments": [
            {
                "name": "rampup",
                "id": 0,
                "nominal": [0, 10],
                "modes": {"lim": {"t": [0, 10], "ip": [0, 2]}},
                "transitions": [{"to": "diverted_rampup", "event": "diverted"}],
            },
            {
                "name": "diverted_rampup",
                "id": 1,
                "nominal": [10, 50],
                "modes": {"div": {"t": [10, 55], "ip": [2, 15]}},
                "transitions": [{"to": "flattop", "time_after": 40}],
            },
            {
                "name": "flattop",
                "id": 2,
                "nominal": [50, 100],
                "modes": {"div": {"t": [50, 100], "ip": [14, 15.5]}},
                "transitions": [{"to": "STOP", "time_after": 50}],
                "overlay": {
                    "pulse_schedule/position_control/gap(3)/value/reference": [
                        {"time": [0, 50], "value": [0.15, 0.15]}
                    ]
                },
            },
            {"name": "STOP", "id": 99},
        ],
        "exception_handling": [  # the YAML key 'on' is read as True (YAML 1.1)
            {
                "name": "z_hold",
                "id": 22,
                "kind": "soft",
                True: "z_excursion",
                "timeout_s": 2.0,
                "then": "ip_termination",
                "action": "hold Ip",
            },
            {
                "name": "ip_termination",
                "id": 41,
                "kind": "hard",
                True: "ip_too_high",
                "then": "STOP",
                "action": "Ip to 0",
            },
        ],
    }
    return design_from_two_file(waves, segs, "synthetic")


def segment_values(dto: list, roles=("nominal",)) -> list[tuple[dict, dict]]:
    """(segment properties, setpoint value) of the segments with a setpoint and a role in roles
    (strict file: no role, all segments)."""
    out = []
    for key, s in dto[1]["value"]["segments"]["value"].items():
        role = s["value"]["properties"]["value"].get("role", {}).get("value", "nominal")
        if role not in roles or not s["value"]["setpoints"]["value"]:
            continue
        props = s["value"]["properties"]["value"]
        assert props["id"]["value"] == key
        (pkey, sp) = next(iter(s["value"]["setpoints"]["value"].items()))
        assert sp["value"]["properties"]["value"]["id"]["value"] == pkey
        out.append((props, sp["value"]["properties"]["value"]["value"]["value"]))
    return out


# --------------------------------------------------------------------------- tests
@pytest.mark.skipif(not ORACLE.is_file(), reason=f"schema oracle absent: {ORACLE}")
@pytest.mark.parametrize("route", ["two_file", "pulse_design"])
def test_conformity_with_the_psps_mock(route: str) -> None:
    oracle = signatures(json.loads(ORACLE.read_text()))
    if route == "two_file":
        design = two_file_design()
    else:
        design = design_from_pulse_design(
            load_design(TOOL / "examples" / "ip_105073_psc.yaml")
        )
    ours = without_mode_window_units(signatures(build_dto(design)[0]))
    bad = [
        (p, s) for p, ss in ours.items() for s in ss if s not in oracle.get(p, set())
    ]
    assert not bad, bad[:5]
    if route == "two_file":  # every path of the mock is produced
        assert set(oracle) == set(ours)


def props(doc: list) -> dict:
    """Schedule properties (value dict) of a document."""
    return doc[1]["value"]["properties"]["value"]


def additional(ext: list) -> dict:
    return props(ext)["pds_additional"]["value"]


def without_slot(ext: list) -> dict[str, list[dict]]:
    """{quantity: [{segment, waveform}, ...]} of pds_additional.waveforms_without_slot
    (a struct keyed <segment>__<quantity> since 2026-11-16, PSPS parser rule)."""
    out: dict[str, list[dict]] = {}
    node = additional(ext).get("waveforms_without_slot", _struct({}))
    assert node["type"] == "struct"
    for n in node["value"].values():
        v = n["value"]
        out.setdefault(v["quantity"]["value"], []).append(v)
    return out


def unfilled(ext: list) -> list[dict]:
    return [
        {k: n["value"][k]["value"] for k in n["value"]}
        for n in props(ext)["unfilled"]["value"]
    ]


def by_name(ext: list) -> dict[str, dict]:
    """{segment name: segment value dict} of an extended document."""
    return {
        s["value"]["properties"]["value"]["name"]["value"]: s["value"]
        for s in ext[1]["value"]["segments"]["value"].values()
    }


def setpoint_value(seg: dict) -> dict:
    (sp,) = seg["setpoints"]["value"].values()
    return sp["value"]["properties"]["value"]["value"]["value"]


def walk_nodes(n: dict, path: str = ""):
    yield path, n
    if n["type"] == "struct":
        for k, c in n["value"].items():
            yield from walk_nodes(c, path + "/" + k)
    elif n["type"] == "list":
        for i, c in enumerate(n["value"]):
            yield from walk_nodes(c, f"{path}[{i}]")


def pulse_design_route() -> dict:
    return design_from_pulse_design(
        load_design(TOOL / "examples" / "ip_105073_psc.yaml")
    )


ROUTES = {"two_file": two_file_design, "pulse_design": pulse_design_route}


# --------------------------------------------------------------------------- strict
def test_waveform_round_trip_and_circuit_map() -> None:
    design = two_file_design()
    dto, _ = build_dto(design)
    segs = design["segments"]
    values = segment_values(dto)
    assert [p["name"]["value"] for p, _ in values] == [s["name"] for s in segs]
    for seg, (p, v) in zip(segs, values, strict=True):
        assert p["duration"]["value"] == pytest.approx(seg["end"] - seg["start"])
        for c in ("cs3u", "cs1", "pf4"):
            node = v["waveforms_by_circuit"]["value"][c]["value"]
            x = np.asarray(node["xValues"]["value"])
            assert x[0] == 0.0
            t_abs = x + seg["start"]
            k = COILS.index(c.upper()) + 1
            t, val = design["waveforms"][
                f"pulse_schedule/pf_active/coil({k})/current/reference"
            ]
            np.testing.assert_allclose(  # PCS native frame: -I_IMAS
                node["yValues"]["value"],
                IMAS_TO_PCS_CURRENT_SIGN * np.interp(t_abs, t, val),
                rtol=RTOL,
                atol=ATOL,
            )
        rc = v["shape_control"]["value"]["1"]["value"]["parameters"]["value"][
            "rcentroid"
        ]
        assert rc["value"]["xValues"]["value"][-1] == pytest.approx(
            seg["end"] - seg["start"]
        )
        assert set(v["waveforms_by_circuit"]["value"]) == {
            "cs3u",
            "cs2u",
            "cs1",
            "cs2l",
            "cs3l",
            "pf1",
            "pf2",
            "pf3",
            "pf4",
        }
    # overlay replaces gap01 in the flat-top segment
    gap01 = values[2][1]["shape_control"]["value"]["4"]["value"]["parameters"]["value"][
        "gaps"
    ]
    assert gap01["value"][0]["value"]["waveform"]["value"]["yValues"][
        "value"
    ] == pytest.approx([0.15, 0.15])
    assert "_psps_dto_extended.json" in props(dto)["description"]["value"]


def test_segment_duration_without_binary_noise() -> None:
    """end - start in pulse time carries float64 noise; the written duration does not."""
    design = two_file_design()
    a, b = 79.217598, 94.817598  # D_eof flat-top: b - a = 15.600000000000009
    assert b - a != 15.6
    design["segments"][1]["end"] = design["segments"][2]["start"] = a
    design["segments"][2]["end"] = b
    dto, ext = build_dto(design)
    for doc in (dto, ext):
        p = by_name(doc)["flattop"]["properties"]["value"]
        assert p["duration"]["value"] == 15.6
        assert json.dumps(p["duration"]["value"]) == "15.6"


def test_coil_currents_in_pcs_frame_and_positive_ip_windows() -> None:
    """DTO coil currents = -1 x IMAS (conductor current in A); Ip windows positive."""
    assert IMAS_TO_PCS_CURRENT_SIGN == -1
    design = two_file_design()
    path = "pulse_schedule/pf_active/coil(7)/current/reference"  # PF2
    assert COILS[6] == "PF2"
    design["waveforms"][path] = (np.array([0.0, 100.0]), np.array([-25e3, -25e3]))
    dto, ext = build_dto(design)
    for _, v in segment_values(dto):
        y = np.asarray(
            v["waveforms_by_circuit"]["value"]["pf2"]["value"]["yValues"]["value"]
        )
        assert y.size
        np.testing.assert_allclose(y, 25e3, rtol=1e-6)  # float32 tolerance
        for mode in v["modes"]["value"]:
            m = mode["value"]
            assert m["ip0s"]["value"] >= 0 and m["ip0f"]["value"] > 0
    conv = props(ext)["conventions"]["value"]
    assert "negated" in conv["sign_frame"]["value"]
    assert "not ampere-turns" in conv["circuit_current_unit"]["value"]


def test_modes_windows_and_catalogue_refs() -> None:
    _, v = segment_values(build_dto(two_file_design())[0])[1]
    (mode,) = v["modes"]["value"]
    m = mode["value"]
    assert m["t0s"]["value"] == 0.0 and m["t0f"]["value"] == pytest.approx(45.0)
    assert (m["ip0s"]["value"], m["ip0f"]["value"]) == (2_000_000, 15_000_000)
    assert m["shape_control_ref"]["value"]["name"]["value"] == "Gaps"
    assert m["ip_control_ref"]["value"]["name"]["value"] == "Integrated CS/PF"
    assert m["vs_control_ref"]["value"]["name"]["value"] == "VS1+VS3"
    assert m["current_limit_avoidance"]["value"] is True
    xp = m["transition_conditions"]["value"]["transition_conditions_xp_in_box"]["value"]
    assert xp["enabled"]["value"] is True and xp["r"]["value"] == pytest.approx(5.05)


def test_mode_window_display_units() -> None:
    """t0s/t0f carry display units "s", ip0s/ip0f "A" (setup_MCLS_01.m:20), nothing else added."""
    assert MODE_WINDOW_UNITS == {"t0s": "s", "t0f": "s", "ip0s": "A", "ip0f": "A"}
    n = 0
    for _, v in segment_values(build_dto(two_file_design())[0]):
        for mode in v["modes"]["value"]:
            m = mode["value"]
            for f, u in MODE_WINDOW_UNITS.items():
                assert m[f]["display"] == {"units": u}
                assert set(m[f]) == {"type", "value", "display"}
            assert m["t0s"]["type"] == "float32" and m["ip0s"]["type"] == "int32"
            n += 1
    assert n == 3


def _gap_waveforms(dto: list) -> list[list[dict]]:
    """Per segment, the six gap slot nodes {id, waveform}."""
    return [
        [
            g["value"]
            for g in v["shape_control"]["value"]["4"]["value"]["parameters"]["value"][
                "gaps"
            ]["value"]
        ]
        for _, v in segment_values(dto)
    ]


def _with_gaps(ks) -> dict:
    """Synthetic design with a distinct constant waveform for each PDS gap k in ks."""
    design = two_file_design()
    for path in [p for p in design["waveforms"] if "/gap(" in p]:
        del design["waveforms"][path]
    for seg in design["segments"]:
        seg["overlay"] = {}
    for k in ks:
        design["waveforms"][
            f"pulse_schedule/position_control/gap({k})/value/reference"
        ] = (np.array([0.0, 100.0]), np.array([0.01 * k, 0.01 * k]))
    return design


@pytest.mark.parametrize("override", [None, (1, 2, 3, 4, 5, 6)])
def test_gap_slot_i_takes_pds_gap_of_the_slot_map(override) -> None:
    """Slot gap0{i+1} = PDS gap PSPS_GAP_SLOTS[i] (or the override); others: no slot."""
    assert PSPS_GAP_SLOTS == (3, 8, 15, 21, 25, 48)
    slots = PSPS_GAP_SLOTS if override is None else override
    design = _with_gaps(sorted(set(PSPS_GAP_SLOTS) | {1, 2, 4, 5, 6, 7}))
    dto, ext = (
        build_dto(design) if override is None else build_dto(design, gap_slots=override)
    )
    for seg_gaps in _gap_waveforms(dto):
        assert [g["id"]["value"] for g in seg_gaps] == [
            f"gap{i:02d}" for i in range(1, 7)
        ]
        for i, g in enumerate(seg_gaps):
            y = g["waveform"]["value"]["yValues"]["value"]
            assert y and y == pytest.approx([0.01 * slots[i]] * len(y))
    unused = {k for k in (1, 2, 3, 4, 5, 6, 7, 8, 15, 21, 25, 48) if k not in slots}
    ws = without_slot(ext)
    assert set(ws) >= {f"gap {k} value" for k in unused}
    assert not any(f"gap {k} value" in ws for k in slots)
    for k in unused:  # one entry per nominal segment, metres
        assert len(ws[f"gap {k} value"]) == 3
        w = ws[f"gap {k} value"][0]["waveform"]["value"]
        assert w["yValues"]["display"] == {"units": "m"}
    gap_conv = props(ext)["conventions"]["value"]["gap_slots"]["value"]
    assert gap_conv.startswith("gap01..gap06 = PDS gaps " + ", ".join(map(str, slots)))


def test_gap_slot_without_design_waveform_is_a_zero_placeholder() -> None:
    """An empty slot gets the 2-point zero placeholder over the segment, never []."""
    design = _with_gaps([8])  # only slot gap02 filled
    dto, ext = build_dto(design)
    for seg, seg_gaps in zip(design["segments"], _gap_waveforms(dto), strict=True):
        filled = [any(g["waveform"]["value"]["yValues"]["value"]) for g in seg_gaps]
        assert filled == [False, True, False, False, False, False]
        for i in (0, 2, 3, 4, 5):
            w = seg_gaps[i]["waveform"]["value"]
            assert w["xValues"]["value"] == [0.0, seg["end"] - seg["start"]]
            assert w["yValues"]["value"] == [0.0, 0.0]
    reasons = {
        u["field"]: u["reason"]
        for u in unfilled(ext)
        if u["field"].startswith("shape_control.4.gaps")
    }
    assert set(reasons) == {f"shape_control.4.gaps[{i}]" for i in (0, 2, 3, 4, 5)}
    assert reasons["shape_control.4.gaps[5]"] == (
        "placeholder waveform (zeros), no design waveform 'gap 48 value'"
    )


def _empty_containers(doc: list) -> list[str]:
    """Paths of empty typed arrays and empty 'points' lists (empty overlapping_modes
    arrays are allowed: the mock has them too)."""
    return [
        p
        for p, n in walk_nodes(doc[1])
        if (
            (
                n["type"] == "array"
                and not p.endswith(("overlapping_modes", "_priority"))
            )
            or (n["type"] == "list" and p.endswith("/points"))
        )
        and not n["value"]
    ]


def _sparse_design() -> dict:
    """Two-file design with only the Ip reference (D_eof/105073-like gaps in the input)."""
    design = two_file_design()
    design["waveforms"] = {
        p: w for p, w in design["waveforms"].items() if p.endswith("/ip/reference")
    }
    for seg in design["segments"]:
        seg["overlay"] = {}
    return design


@pytest.mark.parametrize("route", ["sparse", "pulse_design"])
def test_no_empty_array_or_points_list_in_the_strict_file(route: str) -> None:
    """Bisection of 2026-11-13: the PSPS GUI rejects empty xValues/yValues and an empty
    points list; the writer substitutes zero placeholders and records them."""
    design = _sparse_design() if route == "sparse" else pulse_design_route()
    dto, ext = build_dto(design)
    assert _empty_containers(dto) == []
    assert _empty_containers(ext) == []
    assert strip_extensions(ext) == dto
    for props_, v in segment_values(dto):
        dur = props_["duration"]["value"]
        pts = v["shape_control"]["value"]["2"]["value"]["parameters"]["value"][
            "points"
        ]["value"]
        assert len(pts) == 1 and list(pts[0]["value"]) == ["r", "z", "id"]
        assert pts[0]["value"]["id"]["value"] == "point01"
        gap = v["shape_control"]["value"]["4"]["value"]["parameters"]["value"]["gaps"][
            "value"
        ][0]["value"]["waveform"]["value"]
        assert gap["xValues"]["value"] == pytest.approx([0.0, dur])  # float32
        assert gap["yValues"]["value"] == [0.0, 0.0]
        xp = v["shape_control"]["value"]["3"]["value"]["parameters"]["value"]["xp"]
        assert xp["value"]["r"]["value"]["yValues"]["value"] == [0.0, 0.0]
        if route == "sparse":
            cs1 = v["waveforms_by_circuit"]["value"]["cs1"]["value"]
            assert cs1["xValues"]["value"] == pytest.approx([0.0, dur])
            assert cs1["yValues"]["display"] == {"units": "A"}
    u = unfilled(ext)
    fields = {x["field"] for x in u}
    assert {"shape_control.2.points", "shape_control.3.refpoint"} <= fields
    assert "shape_control.3.xp.r" in fields
    if route == "sparse":  # the converter route carries constant CS/PF references
        assert {"waveforms_by_circuit.cs1", "waveforms_by_circuit.pf5"} <= fields
    placeholders = [x for x in u if x["reason"].startswith("placeholder")]
    assert placeholders and all("placeholder" in x["reason"] for x in placeholders)
    assert len({(x["field"], x["reason"]) for x in u}) == len(u)  # no duplicates
    assert "placeholders" in props(ext)["conventions"]["value"]


def _empties(obj, path: str = "") -> list[str]:
    """Paths of every empty list or dict in a raw JSON document."""
    out = []
    if isinstance(obj, dict):
        if not obj:
            out.append(path)
        for k, v in obj.items():
            out += _empties(v, f"{path}/{k}")
    elif isinstance(obj, list):
        if not obj:
            out.append(path)
        for i, v in enumerate(obj):
            out += _empties(v, f"{path}[{i}]")
    return out


ALLOWED_EMPTY = ("/overlapping_modes/value", "/overlapping_modes_priority/value")


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_no_empty_container_in_either_file(route: str) -> None:
    """Bisection of 2026-11-13: the GUI also rejects an empty modes list and an empty
    setpoints object; only the mock's own empty overlapping_modes arrays remain."""
    dto, ext = build_dto(ROUTES[route]())
    for doc in (dto, ext):
        left = [p for p in _empties(doc) if not p.endswith(ALLOWED_EMPTY)]
        assert left == [], left
        for seg in doc[1]["value"]["segments"]["value"].values():
            assert len(seg["value"]["setpoints"]["value"]) == 1
            assert len(setpoint_value(seg["value"])["modes"]["value"]) >= 1


def test_placeholder_default_mode_on_the_converter_route() -> None:
    """The converter YAML has no MCLS modes: every segment gets one mode 'default'."""
    dto, ext = build_dto(pulse_design_route())
    names = []
    for props_, v in segment_values(dto):
        (m,) = [m["value"] for m in v["modes"]["value"]]
        names.append(props_["name"]["value"])
        dur = props_["duration"]["value"]
        assert (m["id"]["value"], m["name"]["value"]) == ("mode-default", "default")
        assert (m["t0s"]["value"], m["t0f"]["value"]) == pytest.approx((0.0, dur))
        assert (m["ip0s"]["value"], m["ip0f"]["value"]) == (0, 0)
        for ref in ("shape_control_ref", "ip_control_ref", "vs_control_ref"):
            assert m[ref]["value"]["id"]["value"] == "0"
    (rec,) = [u for u in unfilled(ext) if u["field"] == "modes"]
    assert rec["reason"] == (
        "one placeholder mode 'default' (no MCLS mode in the design; the GUI "
        "rejects an empty list)"
    )
    assert rec["where"] == "; ".join(names)
    conv = props(ext)["conventions"]["value"]["setpoints_and_modes"]["value"]
    assert "placeholder mode 'default'" in conv and "last nominal segment" in conv


def test_overlay_of_a_gap_outside_the_slots_goes_to_pds_additional() -> None:
    """Default slots: the gap 3 overlay is applied; without gap 3 in the slots it is kept per segment."""
    _, ext = build_dto(two_file_design())
    assert "gap 3 value" not in without_slot(ext)
    _, ext = build_dto(two_file_design(), gap_slots=(1, 2, 4, 5, 6, 7))
    flat_uuid = by_name(ext)["flattop"]["properties"]["value"]["id"]["value"]
    (flat,) = [
        w
        for w in without_slot(ext)["gap 3 value"]
        if w["segment"]["value"] == flat_uuid
    ]
    wave = flat["waveform"]["value"]
    assert wave["xValues"]["value"] == [0.0, 50.0]
    assert wave["yValues"]["value"] == pytest.approx([0.15, 0.15])


def test_gap_slots_override_is_checked() -> None:
    with pytest.raises(ValueError):
        build_dto(two_file_design(), gap_slots=(1, 2, 3))
    with pytest.raises(ValueError):
        build_dto(two_file_design(), gap_slots=(1, 1, 2, 3, 4, 5))


def test_deterministic_uuids(tmp_path: Path) -> None:
    a = write_psps_dto(two_file_design(), tmp_path / "a")
    b = write_psps_dto(two_file_design(), tmp_path / "b")
    for pa, pb in zip(a, b, strict=True):
        assert pa.read_bytes() == pb.read_bytes()
    dto = json.loads(a[0].read_text())
    keys = list(dto[1]["value"]["segments"]["value"])
    assert len(set(keys)) == 3
    assert all(uuid.UUID(k).version == 5 for k in keys)
    assert dto[1]["value"]["properties"]["value"]["state"]["value"] == "New"
    assert [p.name for p in a] == [
        "synthetic_psps_dto.json",
        "synthetic_psps_dto_extended.json",
    ]


def test_cli_flag(tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("cli", TOOL / "ip_waveform_export.py")
    assert spec is not None and spec.loader is not None
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    rc = cli.main(
        [
            "--yaml",
            str(TOOL / "examples" / "ip_105073_psc.yaml"),
            "--out-dir",
            str(tmp_path),
            "--psps-dto",
        ]
    )
    assert rc == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "ip_105073_psc_psps_dto.json",
        "ip_105073_psc_psps_dto_extended.json",
    ]


# --------------------------------------------------------------------------- extended
@pytest.mark.parametrize("route", sorted(ROUTES))
def test_extended_minus_extensions_is_the_strict_file(
    route: str, tmp_path: Path
) -> None:
    """(i) removing properties.extensions from the extended file gives the strict file."""
    dto, ext = build_dto(ROUTES[route]())
    assert strip_extensions(ext) == dto
    assert ext != dto
    p1, p2 = write_psps_dto(ROUTES[route](), tmp_path)
    assert strip_extensions(json.loads(p2.read_text())) == json.loads(p1.read_text())
    patterns = [p["value"]["path"]["value"] for p in props(ext)["extensions"]["value"]]
    assert len(patterns) == len(set(patterns))
    for p in ("events", "conventions", "unfilled", "pds_additional", "extensions"):
        assert "properties/" + p in patterns
        assert p not in props(dto)


def assert_lists_hold_structs(doc) -> None:
    """Every ``list`` node of a raw psps-dto document holds struct nodes only."""

    def walk(obj, path: str) -> None:
        if isinstance(obj, dict):
            if obj.get("type") == "list":
                assert isinstance(obj["value"], list), path
                for i, e in enumerate(obj["value"]):
                    assert isinstance(e, dict) and e.get("type") == "struct", (
                        f"{path}[{i}]"
                    )
            for k, v in obj.items():
                walk(v, f"{path}/{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(doc, "")


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_every_list_node_holds_structs_only(route: str) -> None:
    """The PSPS GUI rejects a list of string or array nodes (2026-11-13)."""
    dto, ext = build_dto(ROUTES[route]())
    assert_lists_hold_structs(dto)
    assert_lists_hold_structs(ext)
    _, ext = build_dto(
        {**two_file_design(), "sl_editable": {"session_leader": ["ip", "gaps"]}}
    )
    assert_lists_hold_structs(ext)
    assert additional(ext)["editable_by"]["value"]["session_leader"]["value"] == [
        {"type": "struct", "value": {"field": {"type": "string", "value": "ip"}}},
        {"type": "struct", "value": {"field": {"type": "string", "value": "gaps"}}},
    ]


def assert_lists_homogeneous(doc) -> int:
    """Every ``list`` node holds struct nodes with ONE key tuple (order included);
    returns the number of list nodes checked."""
    n = 0

    def walk(obj, path: str) -> None:
        nonlocal n
        if isinstance(obj, dict):
            if obj.get("type") == "list":
                n += 1
                assert isinstance(obj["value"], list), path
                keys = [tuple(e["value"].keys()) for e in obj["value"]]
                assert all(e.get("type") == "struct" for e in obj["value"]), path
                assert len(set(keys)) <= 1, f"{path}: {keys}"
            for k, v in obj.items():
                walk(v, f"{path}/{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(doc, "")
    return n


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_every_list_holds_structs_with_one_key_set(route: str) -> None:
    """The PSPS GUI rejects a list whose struct elements differ in their keys
    (2026-11-13, series 8: events with release_threshold on one element only)."""
    dto, ext = build_dto(ROUTES[route]())
    assert assert_lists_homogeneous(dto) >= 1
    assert assert_lists_homogeneous(ext) > assert_lists_homogeneous(dto)
    evs = props(ext)["events"]["value"]
    assert len({tuple(e["value"].keys()) for e in evs}) == 1


def test_list_builder_rejects_mixed_key_sets() -> None:
    a, b = _struct({"x": _f32(1), "y": _f32(2)}), _struct({"x": _f32(3)})
    with pytest.raises(ValueError, match="same keys"):
        _list([a, b])
    with pytest.raises(ValueError, match="same keys"):
        _list([a, _struct({"y": _f32(2), "x": _f32(1)})])  # order differs
    with pytest.raises(ValueError, match="not a struct node"):
        _list([a, _f32(1)])
    ok = _list([a, _struct({"x": _f32(5), "y": _f32(6)})])
    assert ok["type"] == "list" and len(ok["value"]) == 2
    with pytest.raises(ValueError, match="at least one list element"):
        _list([])


def assert_keys_identifier_like(doc) -> None:
    """Every struct key of a raw psps-dto document matches ``[A-Za-z0-9_-]+``."""

    def walk(obj, path: str) -> None:
        if isinstance(obj, dict):
            if obj.get("type") == "struct":
                assert isinstance(obj["value"], dict), path
                for k in obj["value"]:
                    assert isinstance(k, str) and KEY_RE.fullmatch(k), f"{path}/{k!r}"
            for k, v in obj.items():
                walk(v, f"{path}/{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(doc, "")


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_every_struct_key_is_identifier_like(route: str) -> None:
    """The PSPS GUI rejects a struct key with characters outside [A-Za-z0-9_-]
    (2026-11-13, series 3 V02 / series 4: the former mcls_field_map keys)."""
    dto, ext = build_dto(ROUTES[route]())
    assert_keys_identifier_like(dto)
    assert_keys_identifier_like(ext)
    assert all(KEY_RE.fullmatch(k) for k in MCLS_MAP)
    fm = additional(ext)["mcls_field_map"]["value"]
    assert set(fm) == set(MCLS_MAP)
    for k in ("t0s_or_t0f", "ip0s_or_ip0f", "scp_ip_scaling_or_vs_ip_scaling"):
        assert fm[k]["type"] == "string" and " / " in fm[k]["value"], k
    assert {"transition_conditions_any", "control_conditions_any", "alarms_any"} <= set(
        fm
    )
    assert "overlapping_modes_priority" in fm


def test_struct_rejects_a_key_that_is_not_identifier_like() -> None:
    for bad in ("a b", "t0s / t0f", "alarms.*", "x(y)", ""):
        with pytest.raises(ValueError, match="struct key not identifier-like"):
            _struct({bad: _str("x")})
    sid = str(uuid.uuid5(uuid.NAMESPACE_URL, "x"))
    ok = _struct(
        {sid: _str("x"), "0": _str("y"), "gap01": _str("z"), "a-b_C": _str("w")}
    )
    assert ok["type"] == "struct" and set(ok["value"]) == {sid, "0", "gap01", "a-b_C"}


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_extended_nodes_are_typed(route: str) -> None:
    """(ii) every node of the extended file has a mock node type and a matching value."""
    _, ext = build_dto(ROUTES[route]())
    assert ext[0] == {"encoding": ENCODING} and len(ext) == 2
    pytypes = {
        "string": str,
        "bool": bool,
        "int32": int,
        "float32": float,
        "float64": float,
        "struct": dict,
        "list": list,
        "array": list,
    }
    assert set(pytypes) == NODE_TYPES
    for path, n in walk_nodes(ext[1]):
        assert n["type"] in NODE_TYPES, path
        assert set(n) <= {"type", "value", "element_type", "display", "constraints"}, (
            path
        )
        assert isinstance(n["value"], pytypes[n["type"]]), path
        if n["type"] == "int32":
            assert not isinstance(n["value"], bool), path
        if n["type"] == "array":
            assert n["element_type"] in ARRAY_ELEMENT_TYPES, path
        if "display" in n:
            assert set(n["display"]) == {"units"}, path


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_extended_has_no_imas_wording(route: str) -> None:
    """(iii) the files go to the PSPS team: no IDS path, IMAS word, DD version or COCOS."""
    dto, ext = build_dto(ROUTES[route]())
    for doc in (dto, ext):
        text = json.dumps(doc)
        for bad in (
            "pulse_schedule/",
            "IMAS",
            "imas",
            "DD ",
            "dd_version",
            "COCOS",
            "cocos",
        ):
            assert bad not in text, bad
        assert not re.search(r"\bIDS\b", text)


def test_extended_segments_order_roles_exits() -> None:
    design = two_file_design()
    _, ext = build_dto(design)
    segs = by_name(ext)
    uuid_of = {n: s["properties"]["value"]["id"]["value"] for n, s in segs.items()}
    rows = {
        n: {k: v["value"] for k, v in s["properties"]["value"].items() if k != "exit"}
        for n, s in segs.items()
    }
    assert [(n, r["order"], r["role"]) for n, r in rows.items()] == [
        ("rampup", 1, "nominal"),
        ("diverted_rampup", 2, "nominal"),
        ("flattop", 3, "nominal"),
        ("z_hold", 4, "exception"),
        ("ip_termination", 5, "exception"),
        ("STOP", 6, "stop"),
    ]
    assert rows["rampup"]["successor"] == uuid_of["diverted_rampup"]
    assert rows["flattop"]["successor"] == ""
    assert [rows[n]["pcs_segment_id"] for n in rows] == [0, 1, 2, 22, 41, 99]
    ex = {
        k: v["value"]
        for k, v in segs["rampup"]["properties"]["value"]["exit"]["value"].items()
    }
    assert ex == {
        "type": "event",
        "event": "diverted",
        "event_target": uuid_of["diverted_rampup"],
    }
    ex = segs["flattop"]["properties"]["value"]["exit"]["value"]
    assert ex["type"]["value"] == "time" and ex["watchdog_s"]["value"] == 50.0
    assert ex["watchdog_s"]["display"] == {"units": "s"}
    assert ex["watchdog_target"]["value"] == uuid_of["STOP"]
    assert rows["z_hold"]["kind"] == "soft" and rows["z_hold"]["overlay_of"] == ""
    assert (
        rows["ip_termination"]["kind"] == "hard"
        and "overlay_of" not in rows["ip_termination"]
    )
    assert rows["z_hold"]["action"] == "hold Ip"
    zx = segs["z_hold"]["properties"]["value"]["exit"]["value"]
    assert zx["watchdog_target"]["value"] == uuid_of["ip_termination"]
    # no references for the two-file exceptions: placeholder setpoints with the
    # modes of the last nominal segment (flattop: div)
    _check_pseudo_setpoint(segs["z_hold"], ["div"], 2.0)
    _check_pseudo_setpoint(segs["ip_termination"], ["div"], 0.0)
    _check_pseudo_setpoint(segs["STOP"], ["div"], 0.0)
    where = {
        u["field"]: u["where"]
        for u in unfilled(ext)
        if u["field"].endswith("segment setpoint (incl. ip_control.*.parameters.ip)")
        or u["field"] == "STOP segment setpoint"
    }
    assert where == {
        "exception segment setpoint (incl. ip_control.*.parameters.ip)": (
            "z_hold; ip_termination"
        ),
        "STOP segment setpoint": "STOP",
    }
    reasons = {u["field"]: u["reason"] for u in unfilled(ext)}
    assert reasons["STOP segment setpoint"].endswith(
        "modes inherited from nominal segment 'flattop' (div; whole-segment "
        "window, Ip window 0)"
    )


def _check_pseudo_setpoint(seg: dict, parent_modes: list[str], dur: float) -> dict:
    """Exactly one setpoint; modes = the parent's names over the whole segment with
    Ip window 0; every waveform the placeholder over [0, dur]; one isoflux point."""
    assert seg["properties"]["value"]["duration"]["value"] == pytest.approx(dur)
    assert len(seg["setpoints"]["value"]) == 1
    v = setpoint_value(seg)
    modes = [m["value"] for m in v["modes"]["value"]]
    assert [m["name"]["value"] for m in modes] == parent_modes
    for m in modes:
        assert (m["t0s"]["value"], m["t0f"]["value"]) == pytest.approx((0.0, dur))
        assert (m["ip0s"]["value"], m["ip0f"]["value"]) == (0, 0)
    n_wave = 0
    for path, n in walk_nodes({"type": "struct", "value": v}):
        if n["type"] == "struct" and set(n["value"]) == {"xValues", "yValues"}:
            assert n["value"]["xValues"]["value"] == pytest.approx([0.0, dur]), path
            assert n["value"]["yValues"]["value"] == [0.0, 0.0], path
            n_wave += 1
        if path.endswith("/points"):
            assert len(n["value"]) == 1, path
    assert n_wave >= 9 + 2 + 1  # circuits, pf5/pf6, the Ip reference, ...
    return v


def test_extended_ip_reference_and_pf5_pf6() -> None:
    design = two_file_design()
    _, ext = build_dto(design)
    segs = by_name(ext)
    t, v = design["waveforms"]["pulse_schedule/flux_control/ip/reference"]
    for seg in design["segments"]:
        val = setpoint_value(segs[seg["name"]])
        cat = val["ip_control"]["value"]
        used = {
            m["value"]["ip_control_ref"]["value"]["id"]["value"]
            for m in val["modes"]["value"]
        }
        with_ip = {cid for cid, c in cat.items() if "parameters" in c["value"]}
        assert with_ip == used
        for cid in used:
            ip = cat[cid]["value"]["parameters"]["value"]["ip"]["value"]
            x = np.asarray(ip["xValues"]["value"])
            assert ip["yValues"]["display"] == {"units": "A"}
            np.testing.assert_allclose(  # PCS frame, Ip > 0
                ip["yValues"]["value"],
                IMAS_TO_PCS_CURRENT_SIGN * np.interp(x + seg["start"], t, v),
                rtol=RTOL,
            )
        circ = val["waveforms_by_circuit"]["value"]
        assert list(circ)[-2:] == ["pf5", "pf6"] and len(circ) == 11
        pf5 = circ["pf5"]["value"]["yValues"]["value"]
        tc, vc = design["waveforms"][
            "pulse_schedule/pf_active/coil(10)/current/reference"
        ]
        x = np.asarray(circ["pf5"]["value"]["xValues"]["value"])
        np.testing.assert_allclose(
            pf5,
            IMAS_TO_PCS_CURRENT_SIGN * np.interp(x + seg["start"], tc, vc),
            rtol=RTOL,
        )
    # the rampup mode uses ip "rzip" -> catalogue id 2
    assert (
        "parameters"
        in setpoint_value(segs["rampup"])["ip_control"]["value"]["2"]["value"]
    )


def test_extended_events() -> None:
    _, ext = build_dto(two_file_design())
    segs = by_name(ext)
    uuid_of = {n: s["properties"]["value"]["id"]["value"] for n, s in segs.items()}
    evs = {
        e["value"]["name"]["value"]: e["value"] for e in props(ext)["events"]["value"]
    }
    assert set(evs) == {"diverted", "z_excursion", "ip_too_high"}
    keys = ("name", "signal", "test", "threshold", "release_threshold", "box")
    keys += ("latch", "action", "target")
    assert all(tuple(e) == keys for e in evs.values())  # one key set (series 8)
    d = evs["diverted"]
    assert d["test"]["value"] == "x_point_in_box"
    assert d["threshold"] == {"type": "float32", "value": 0.0}  # named predicate
    assert d["release_threshold"] == d["threshold"]
    assert d["box"]["value"]["dz"]["value"] == pytest.approx(0.25)
    assert d["target"]["value"] == uuid_of["diverted_rampup"]
    z = evs["z_excursion"]
    assert (z["signal"]["value"], z["test"]["value"]) == ("|Z - Z_ref|", ">=")
    assert z["threshold"]["value"] == pytest.approx(0.02)
    assert z["threshold"]["display"] == {"units": "m"}
    assert z["release_threshold"]["value"] == pytest.approx(0.01)
    assert z["release_threshold"]["display"] == {"units": "m"}
    assert z["target"]["value"] == uuid_of["z_hold"]
    ip = evs["ip_too_high"]
    assert ip["threshold"]["value"] == pytest.approx(15.25e6)
    assert ip["threshold"]["display"] == {"units": "A"}
    assert ip["release_threshold"] == ip["threshold"]  # no hysteresis: = threshold
    assert ip["box"]["value"] == {
        k: {"type": "float32", "value": 0.0, "display": {"units": "m"}}
        for k in ("r", "z", "dr", "dz")
    }
    assert ip["latch"]["value"] is True
    assert ip["action"]["value"] == "enter_segment"
    assert ip["target"]["value"] == uuid_of["ip_termination"]
    u = {(x["field"], x["reason"]) for x in unfilled(ext)}
    same = "the GUI requires every list element to carry the same keys"
    for name in ("ip_too_high", "diverted"):
        assert (
            f"events.{name}.release_threshold",
            "no hysteresis in the design; " + same,
        ) in u
    assert not any(f == "events.z_excursion.release_threshold" for f, _ in u)
    assert any(f == "events.diverted.threshold" and r.endswith(same) for f, r in u)
    assert any(f == "events.z_excursion.box" and r.endswith(same) for f, r in u)
    assert all(
        x["where"] == "properties.events"
        for x in unfilled(ext)
        if x["field"].startswith("events.")
    )


def test_extended_exceptions_with_references_from_the_converter_block() -> None:
    """Converter route: soft overlay points and hard ramps become exception setpoints."""
    _, ext = build_dto(pulse_design_route())
    segs = by_name(ext)
    uuid_of = {n: s["properties"]["value"]["id"]["value"] for n, s in segs.items()}
    eof = segs["eof_rampdown"]
    p = {k: v["value"] for k, v in eof["properties"]["value"].items() if k != "exit"}
    assert (p["role"], p["kind"], p["pcs_segment_id"]) == ("exception", "soft", 21)
    assert p["overlay_of"] == uuid_of[next(iter(segs))]  # the only nominal segment
    ip = setpoint_value(eof)["ip_control"]["value"]
    (cid,) = [c for c, n in ip.items() if "parameters" in n["value"]]
    w = ip[cid]["value"]["parameters"]["value"]["ip"]["value"]
    assert w["xValues"]["value"] == [0.0, 2.0]
    assert w["yValues"]["value"] == pytest.approx([15.06e6, 14.06e6])  # PCS frame
    hard = segs["ip_termination"]
    ip = setpoint_value(hard)["ip_control"]["value"][cid]["value"]["parameters"][
        "value"
    ]
    assert ip["ip"]["value"]["yValues"]["value"] == pytest.approx([15.25e6, 0.0, 0.0])
    assert hard["properties"]["value"]["duration"]["value"] == pytest.approx(2.5)
    zx = segs["z_hold"]["properties"]["value"]["exit"]["value"]
    assert (
        zx["type"]["value"] == "event"
        and zx["event"]["value"] == "z_excursion released"
    )
    # hold: no trajectory -> placeholder setpoint, the only nominal segment has no
    # MCLS mode, so the inherited mode is the placeholder 'default'
    z_dur = segs["z_hold"]["properties"]["value"]["duration"]["value"]
    zv = _check_pseudo_setpoint(segs["z_hold"], ["default"], z_dur)
    zip_ = zv["ip_control"]["value"][cid]["value"]["parameters"]["value"]["ip"]
    assert zip_["value"]["xValues"]["value"] == pytest.approx([0.0, z_dur])
    _check_pseudo_setpoint(segs["STOP"], ["default"], 0.0)
    evs = {
        e["value"]["name"]["value"]: e["value"] for e in props(ext)["events"]["value"]
    }
    assert evs["end_of_flux"]["target"]["value"] == uuid_of["eof_rampdown"]
    # z reference = current centre z of the inverse slice since the student's branch (2026-11-13)
    assert evs["z_excursion"]["signal"]["value"] == "|z_meas - 0.5934|"
    assert evs["z_excursion"]["release_threshold"]["display"] == {"units": "m"}


def test_extended_unfilled_conventions_additional() -> None:
    _, ext = build_dto(two_file_design())
    u = unfilled(ext)
    fields = {x["field"] for x in u}
    assert "shape_control.4.gaps[5]" in fields
    assert "modes[].alarms.*" in fields
    assert "properties.author" in fields
    assert all(x["reason"] and x["where"] for x in u)
    conv = props(ext)["conventions"]["value"]
    for k in (
        "sign_frame",
        "circuit_current_unit",
        "time_origin",
        "gap_slots",
        "catalogue_id_0",
        "catalogue_mapping",
        "refpoint",
        "lists",
        "keys",
    ):
        assert conv[k]["type"] == "string" and conv[k]["value"], k
    assert list(conv).index("keys") == list(conv).index("lists") + 1
    assert conv["keys"]["value"].startswith("struct keys contain only letters, digits")
    assert conv["gap_slots"]["value"] == (
        "gap01..gap06 = PDS gaps 3, 8, 15, 21, 25, 48 (assumption, may change)"
    )
    add = additional(ext)
    scalars = {
        s["value"]["quantity"]["value"]: s["value"]["value"]["value"]
        for s in add["scalars_without_slot"]["value"].values()
    }
    assert list(add["scalars_without_slot"]["value"]) == ["gap_3_name"]
    assert scalars == {"gap 3 name": "outer_midplane"}
    assert add["design_start_s"]["value"] == 0.0


def test_extended_kcurr_block_without_provenance() -> None:
    param = {
        "_status": "real (gain file)",
        "_owner": "PCS expert",
        "_source": {
            "gains_file": "/somewhere/KCURR_PFPO1_load_gains_tp.m",
            "coil_order": "CS3U ... P6",
        },
        "KCURR_PFPO1_Gains": {
            "selected": "Ip",
            "Ip": {
                "_label": "plasma current",
                "P": [1.0, 1.0],
                "Ke": [[1.0, 2.0], [3.0, 4.0]],
            },
            "_not_selected": {"noIp": {}},
        },
        "KCURR_PFPO1_tp": {"_file": "/x.m", "Vup": [2100.0, 2100.0]},
        "ParameterScheduling_KCURR": {
            "_file": "/y.m",
            "Tag": "t",
            "levels": [0.0, 1e6],
        },
    }
    _, ext = build_dto(two_file_design(), {"kcurr": param})
    kc = additional(ext)["kcurr"]["value"]
    assert set(kc) == {
        "owner",
        "coil_order",
        "active_gain_set",
        "gains",
        "limits",
        "scheduling",
    }
    assert kc["active_gain_set"]["value"] == "Ip (plasma current)"
    ke = kc["gains"]["value"]["Ke"]
    assert ke["type"] == "list"
    assert all(r["type"] == "struct" for r in ke["value"])
    assert [r["value"]["row"]["value"] for r in ke["value"]] == [[1.0, 2.0], [3.0, 4.0]]
    assert kc["gains"]["value"]["P"]["type"] == "array"
    assert kc["gains"]["value"]["P"]["element_type"] == "float32"
    assert_lists_hold_structs(ext)
    assert kc["limits"]["value"]["Vup"]["display"] == {"units": "V"}
    assert "/" not in json.dumps(kc).replace("A/s", "")
    _, ext = build_dto(
        two_file_design(), {"kcurr": {"_status": "placeholder, not traced"}}
    )
    assert "kcurr" not in additional(ext)


def test_converter_yaml_modes_reach_the_strict_dto(tmp_path: Path) -> None:
    """A converter YAML with a ``modes:`` library and per-segment MCLS windows (designer
    time, A) yields the MCM windows and catalogue refs in the strict DTO."""
    import yaml

    doc = yaml.safe_load((TOOL / "examples" / "ip_105073_psc.yaml").read_text())
    seg = doc["segments"][0]
    t = [seg["start"], seg["end"]]
    seg["modes"] = {
        "flattop_gaps": {"t": t, "ip": [13.5e6, 20e6]},
        "rampdown_position": {"t": t, "ip": [0.0, 13.5e6]},
    }
    doc["modes"] = {
        "flattop_gaps": {"mcm": 1, "shape_ip": "gaps", "ip": "kcurr", "vs": "vs1_vs3"},
        "rampdown_position": {
            "mcm": 2,
            "shape_ip": "none",
            "ip": "kcurr",
            "vs": "vs1_vs3",
        },
    }
    path = tmp_path / "with_modes.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    design = design_from_pulse_design(load_design(path), {str(path): "converter YAML"})
    assert set(design["mode_library"]) == {"flattop_gaps", "rampdown_position"}
    strict, ext = build_dto(design)
    (_, v), *_ = segment_values(strict)
    (_, ve), *_ = segment_values(ext)
    assert len(ve["modes"]["value"]) == 2
    modes = [mode["value"] for mode in v["modes"]["value"]]
    assert len(modes) == 2
    ft, rd = modes
    dur = t[1] - t[0]
    assert (ft["t0s"]["value"], ft["t0f"]["value"]) == (0.0, pytest.approx(dur))
    assert (ft["ip0s"]["value"], ft["ip0f"]["value"]) == (13_500_000, 20_000_000)
    assert (rd["ip0s"]["value"], rd["ip0f"]["value"]) == (0, 13_500_000)
    assert ft["shape_control_ref"]["value"]["name"]["value"] == "Gaps"
    assert ft["ip_control_ref"]["value"]["name"]["value"] == "Integrated CS/PF"
    assert ft["vs_control_ref"]["value"]["name"]["value"] == "VS1+VS3"
    # without the YAML in sources the converter path stays mode-less (as before)
    assert design_from_pulse_design(load_design(path))["mode_library"] == {}


# --------------------------------------------------------------- PSPS parser rule
#: CODAC PSPS parser (psps-dto 1.4.0, git.iter.org/coa/psps-dto@35a5846); the tests
#: that run it are skipped when it is not installed
PARSER = Path(
    os.environ.get(
        "PSPS_PARSER", "/home/ITER/schneim/public/git/psps/_install/bin/parse-psps-file"
    )
)


def list_rule_violations(doc) -> list[str]:
    """Paths of the ``list`` nodes that break the CODAC PSPS parser rule
    (presentation_value_parser.cpp:381-397, ``FinishList``): at least one element,
    and every element of the same pure-value type, i.e. same node type, same array
    element type AND length, same struct member names (in order) and member types.
    Written independently of the exporter's ``type_signature``."""
    bad: list[str] = []

    def sig(n: dict):
        t = n["type"]
        if t == "struct":
            return (t, tuple((k, sig(v)) for k, v in n["value"].items()))
        if t == "list":
            return (t, len(n["value"]), sig(n["value"][0]) if n["value"] else None)
        if t == "array":
            return (t, n["element_type"], len(n["value"]))
        return t

    def walk(obj, path: str) -> None:
        if isinstance(obj, dict):
            if obj.get("type") == "list":
                items = obj["value"]
                if not items:
                    bad.append(f"{path}: empty list")
                elif len({sig(e) for e in items}) != 1:
                    bad.append(f"{path}: inhomogeneous list")
            for k, v in obj.items():
                walk(v, f"{path}/{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(doc, "")
    return bad


def _uneven_without_slot_design() -> dict:
    """Waveforms without a slot of 2 and 4 points, a string and a float scalar: the
    shapes that made the 105073 extended file fail the parser (2026-11-16)."""
    design = _with_gaps((1, 2))
    design["waveforms"]["pulse_schedule/position_control/gap(2)/value/reference"] = (
        np.array([0.0, 30.0, 60.0, 100.0]),
        np.array([0.02, 0.03, 0.04, 0.05]),
    )
    design["scalars"] = {
        "pulse_schedule/position_control/gap(1)/name": "inner",
        "pulse_schedule/position_control/gap(1)/r": 4.1,
    }
    return design


PARSER_CASES = {
    **ROUTES,
    "uneven_without_slot": _uneven_without_slot_design,
    "sl_editable": lambda: {
        **two_file_design(),
        "sl_editable": {"session_leader": ["ip", "gaps"], "pcs_expert": []},
    },
}


@pytest.mark.parametrize("case", sorted(PARSER_CASES))
def test_every_list_satisfies_the_psps_parser_rule(case: str) -> None:
    """Strict and extended documents: every list non-empty and homogeneous in type."""
    dto, ext = build_dto(PARSER_CASES[case]())
    for doc in (dto, ext, strip_extensions(ext)):
        assert list_rule_violations(doc) == []


def test_without_slot_collections_are_structs_keyed_by_segment_and_quantity() -> None:
    _, ext = build_dto(_uneven_without_slot_design())
    add = additional(ext)
    ws = add["waveforms_without_slot"]
    assert ws["type"] == "struct"
    assert all(KEY_RE.fullmatch(k) for k in ws["value"])
    names = {s["segment"]["value"]: n for n, s in by_name_uuid(ext).items()}
    lengths = set()
    for key, node in ws["value"].items():
        v = node["value"]
        seg = names[v["segment"]["value"]]
        assert key.startswith(seg.replace(" ", "_") + "__")
        assert key.endswith(v["quantity"]["value"].replace(" ", "_"))
        lengths.add(len(v["waveform"]["value"]["xValues"]["value"]))
    assert len(lengths) > 1  # would be an inhomogeneous list
    sc = add["scalars_without_slot"]["value"]
    assert sc["gap_1_name"]["value"]["value"] == {"type": "string", "value": "inner"}
    assert sc["gap_1_R"]["value"]["value"]["type"] == "float32"


def by_name_uuid(ext: list) -> dict[str, dict]:
    """{segment name: {"segment": uuid node}} of an extended document."""
    return {
        name: {"segment": seg["properties"]["value"]["id"]}
        for name, seg in by_name(ext).items()
    }


def test_type_signature_and_list_builder_follow_the_parser() -> None:
    def wave(n: int) -> dict:
        return _struct(
            {"w": {"type": "array", "element_type": "float32", "value": [0.0] * n}}
        )

    assert type_signature(wave(2)) != type_signature(wave(4))
    with pytest.raises(ValueError, match="inhomogeneous"):
        _list([wave(2), wave(4)])
    with pytest.raises(ValueError, match="inhomogeneous"):
        _list([_struct({"v": _str("a")}), _struct({"v": _f32(1.0)})])
    u1, u2 = _f32(1.0), _f32(2.0)
    u1["display"], u2["display"] = {"units": "A"}, {"units": "m"}
    assert _list([_struct({"v": u1}), _struct({"v": u2})])["type"] == "list"


@pytest.mark.skipif(
    not os.access(PARSER, os.X_OK), reason="parse-psps-file not installed"
)
@pytest.mark.parametrize("case", sorted(PARSER_CASES))
def test_written_files_pass_parse_psps_file(case: str, tmp_path: Path) -> None:
    """The CODAC parser exits 0 even on failure: judge by its 'Succes:' line."""
    import subprocess

    lib = PARSER.parent.parent
    env = {
        **os.environ,
        "LD_LIBRARY_PATH": f"{lib / 'lib64'}:{lib / 'lib'}:"
        + os.environ.get("LD_LIBRARY_PATH", ""),
    }
    for path in write_psps_dto(PARSER_CASES[case](), tmp_path):
        out = subprocess.run(
            [str(PARSER), "-v", "-f", str(path)],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
            check=False,
        )
        text = out.stdout + out.stderr
        assert "Succes:" in text and "FAILED" not in text, (path.name, text[:300])
