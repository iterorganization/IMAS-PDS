"""Export a PDS pulse design to the IMPLEMENTED PSPS exchange format ``psps-dto/v1.0/JSON``.

Schema oracle: the file saved from the PSPS qualification server on 2026-11-09
(``pulseconfig-qual.iter.org/pcs``, "PCS Mock Pulse Schedule", ``Save to file``; LMS
``psps-lms`` 2.8.0), kept in the PDS docs as
``docs/psps/From_PSPS_GUI_JSON/PCS Mock Pulse Schedule.json``. Maturity: implemented
format, MOCK content. Every node is ``{type, value[, element_type][, display]
[, constraints]}``; dict keys of segments and setpoints are UUIDs equal to the
``properties.id`` they contain.

Two outputs per design:

``<name>_psps_dto.json`` (STRICT)
    strictly the mock's paths, field names, node types, element types, display
    units and constraints, nothing else; fields PDS cannot fill get neutral values
    (``False``, ``0``, ``"off"``) and are listed in the extended file's
    ``properties.unfilled``. Waveforms the design does not provide are NEVER
    written as empty arrays: the PSPS GUI (qualification server, bisection of
    2026-11-13) answers "Error while parsing data" to an empty ``xValues``/
    ``yValues`` or an empty ``points`` list; they get a 2-point zero placeholder
    over the segment (``_placeholder``) and the ``points`` list one placeholder
    point, each recorded in ``properties.unfilled``. The same GUI rejects an empty
    ``modes`` list and an empty ``setpoints`` object, so every segment carries
    exactly one Magnetics setpoint and every setpoint at least one mode: a segment
    without MCLS mode gets the placeholder mode ``default`` (``DEFAULT_MODE``,
    whole-segment window, Ip window 0, catalogue id "0").
``<name>_psps_dto_extended.json`` (EXTENDED, proposal)
    the same typed psps-dto document plus the PDS information the schema has no
    slot for, placed where it naturally belongs, all in typed nodes: the Ip
    reference under ``ip_control.<id>.parameters.ip``, ``waveforms_by_circuit``
    ``pf5``/``pf6``, per segment ``order``/``role``/``successor``/``exit``/
    ``pcs_segment_id``, the exception and STOP segments as additional segments,
    ``properties.events``, ``properties.conventions``, ``properties.unfilled``,
    ``properties.pds_additional`` and ``properties.extensions`` (the list of every
    added path pattern). Every ``list`` node holds struct nodes only (the GUI
    rejects a list of string or array nodes, series 2 of 2026-11-13): extension
    paths as ``[{path}]``, string lists as ``[{item}]``/``[{field}]``, matrices as
    ``[{row}]``; all elements of a list carry the same keys in the same order (the
    GUI rejects a list whose struct elements differ in their key set, series 8 of
    2026-11-13; ``_list`` raises ``ValueError`` otherwise, and every event carries
    ``release_threshold``, ``= threshold`` when the design gives no hysteresis).
    The CODAC PSPS parser (psps-dto 1.4.0, presentation_value_parser.cpp:381-397,
    checked 2026-11-16) is stricter: every list has at least one element and all
    its elements have ONE type, array lengths and struct member names/types
    included (``type_signature``; ``_list`` raises otherwise). Collections whose
    elements can differ are therefore structs keyed by a stable member name
    (``member_key``): ``pds_additional.waveforms_without_slot`` keyed
    ``<segment>__<quantity>``, ``pds_additional.scalars_without_slot`` keyed
    ``<quantity>``, each member the former list element unchanged; generic lists
    (``_typed``) fall back to ``{item_000: ..., ...}`` / ``{row_000: ...}`` only when
    their elements differ. An empty ``events``/``unfilled`` collection is not
    written.
    Every struct key contains only letters, digits, ``_`` and ``-``
    (the GUI rejects other characters, series 3 V02 / series 4 of 2026-11-13;
    ``_struct`` raises ``ValueError`` on any other key, ``KEY_RE``). Removing the
    paths of ``properties.extensions`` gives the strict document node for node
    (``strip_extensions``).

Decisions (derived from the mock, to be confirmed by the PSPS team):

* time base: ``xValues`` and the mode windows ``t0s``/``t0f`` are written in s
  RELATIVE TO THE SEGMENT START (mock: every x and t0 lies inside the 5 s segment);
* ``ip0s``/``ip0f`` (int32) are written in A, positive |Ip| (PCS frame). Source of the
  unit: pcs@04e9b7f (branch XPT02) assessment/TestCases/IntegratedAssessments/
  XPTL02_105033_mod1/setup_MCLS_01.m:20 ``MCMode(1).Ip0intervals = 1.8*1e6; % ...
  Ipstart [A]`` (setup file; the MCLS block itself was not opened, UNVERIFIED for
  the block). The mock gives these fields no unit; to be confirmed by the PSPS team;
* mode-window units: the ONLY addition to the mock's node structure is a
  ``display: {"units": ...}`` node, same shape as on the mock's waveform arrays, on
  ``t0s``/``t0f`` ("s") and ``ip0s``/``ip0f`` ("A") of every mode
  (``MODE_WINDOW_UNITS``);
* coil currents (``waveforms_by_circuit``): conductor current in A (not
  ampere-turns), PCS sign, i.e. -1 x the IMAS-sign PDS waveforms
  (``IMAS_TO_PCS_CURRENT_SIGN``); the extended file uses the same frame for every
  current (Ip reference, PF5/PF6, exception references). Decision, not a PSPS question: the values are per
  circuit (cs1 = CS1U + CS1L in series, where only the conductor current is
  single-valued) and end at the KCURR input I_CSPF_ref (pcs@04e9b7f
  modules/KCURR/pcssp_KCURR.slx Inport SID 2), which the PCS XPT02 case feeds with
  -1.0 x the IMAS per-conductor currents and a positive Ip (pcs@04e9b7f
  assessment/TestCases/IntegratedAssessments/XPTL02_105033_mod1/
  setup_pulse_data_from_db.m:26,31; limits 45 kA CS / 48-55 kA PF,
  pcs@aa217bc modules/CLA_CCS/CLA_CCS_ext/CLA_CCS_loadtp.m:16); the PSPS side does
  not use IMAS conventions;
* gap slots: the six ``shape_control.4.gaps`` slots (ids gap01..gap06) take the PDS
  gaps ``PSPS_GAP_SLOTS`` = 3, 8, 15, 21, 25, 48 in that order, where "PDS gap k" is
  the 1-based index k of the design waveform ``position_control/gap(k)`` (template
  ``GAP``). User decision of 2026-11-10, an assumption of the pulse-design side that
  may change; ``build_dto``/``write_psps_dto`` take ``gap_slots=`` to override it.
  A slot whose PDS gap has no design waveform stays empty and is listed in
  ``properties.unfilled``; design gaps outside the slots go to the extended file's
  ``properties.pds_additional.waveforms_without_slot`` (per segment, overlays
  applied; one struct member ``<segment>__<quantity>`` each);
* one strict PSPS segment per PDS nominal segment; the mock has no order field;
  the extended file adds the order, the exits and the exception / STOP segments;
* exception and STOP segments (extended file) each carry one Magnetics setpoint
  too: every waveform a placeholder except the exception's own Ip trajectory when
  the design gives one (STOP: zero-length placeholders), and the modes of the LAST
  nominal segment (whole-segment window, Ip window 0; assumption, recorded in
  ``properties.unfilled``); the ``default`` placeholder mode when that segment has
  none;
* UUIDs: ``uuid5`` of fixed names, so a rerun gives the same ids;
* outputs are written for the PSPS team: neither file carries IMAS paths, the IMAS
  sign or a DD version. The IDS paths below are internal lookup keys only; the
  outputs name quantities in plain PDS words (``quantity_name``: "Ip reference",
  "coil CS1 current", "isoflux point 3 R").
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import uuid
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import yaml

ENCODING = "psps-dto/v1.0/JSON"
#: namespace of the deterministic UUIDs (uuid5 of names below it)
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "pds/preprocessing/psps/export_psps_dto")
SOFTWARE = ("pds-export_psps_dto", "0.1.0")
TOL = 1e-9

#: lifecycle constraint copied from the mock (properties.state)
STATE_CHOICE = [
    "Unknown",
    "New",
    "Revised",
    "Submitted",
    "Rework",
    "Cancelled",
    "Approved",
    "Ready",
]
STATE_TRANSITIONS = [
    ("Approved", "Ready"),
    ("Approved", "Submitted"),
    ("New", "Revised"),
    ("Ready", "Approved"),
    ("Revised", "New"),
    ("Revised", "Submitted"),
    ("Rework", "Revised"),
    ("Submitted", "Approved"),
    ("Submitted", "Cancelled"),
    ("Submitted", "Rework"),
    ("Unknown", "Approved"),
    ("Unknown", "Cancelled"),
    ("Unknown", "New"),
    ("Unknown", "Ready"),
    ("Unknown", "Revised"),
    ("Unknown", "Rework"),
    ("Unknown", "Submitted"),
]
DURATION_RANGE = {"min": 0, "max": 100000}
SCALING_CHOICE = ["off", "ip_nominal", "ip_measured"]

#: controller catalogues of the mock setpoint (id, name)
SHAPE_CATALOGUE = {"1": "RZIp", "2": "Isoflux", "3": "Isoflux XP", "4": "Gaps"}
IP_CATALOGUE = {"1": "Integrated CS/PF", "2": "Integrated Shape"}
VS_CATALOGUE = {"1": "Off", "2": "VS1", "3": "VS3", "4": "VS1+VS3"}
#: PDS mode values (105073_segments.yaml) -> catalogue id; None = no slot (derived)
SHAPE_OF = {
    "rzip": "1",
    "limiter_isoflux": "2",
    "isoflux": "2",
    "isoflux_xp": "3",
    "gaps": "4",
}
IP_OF = {"kcurr": "1", "rzip": "2", "shape": "2"}
VS_OF = {"off": "1", "vs1": "2", "vs3": "3", "vs1_vs3": "4"}

#: circuits of waveforms_by_circuit in the mock's order (9; no PF5, PF6)
CIRCUITS = ["cs3u", "cs2u", "cs1", "cs2l", "cs3l", "pf1", "pf2", "pf3", "pf4"]
#: order of pulse_schedule/pf_active/coil(i) in the PDS files (CS1 = CS1U + CS1L)
COILS = [
    "CS3U",
    "CS2U",
    "CS1",
    "CS2L",
    "CS3L",
    "PF1",
    "PF2",
    "PF3",
    "PF4",
    "PF5",
    "PF6",
]
#: PDS gap k (1-based index of position_control/gap(k), see GAP) of the DTO gap slots
#: gap01..gap06, in that order; user decision 2026-11-10, may change (override with
#: build_dto/write_psps_dto(gap_slots=...))
PSPS_GAP_SLOTS = (3, 8, 15, 21, 25, 48)

IP_PATH = "pulse_schedule/flux_control/ip/reference"
CC_R = "pulse_schedule/position_control/current_centroid/r/reference"
CC_Z = "pulse_schedule/position_control/current_centroid/z/reference"
OUTLINE = "pulse_schedule/position_control/boundary_outline({k})/{c}/reference"
XPOINT = "pulse_schedule/position_control/x_point(1)/{c}/reference"
GAP = "pulse_schedule/position_control/gap({k})/value/reference"
COIL = "pulse_schedule/pf_active/coil({k})/current/reference"
#: IMAS -> PCS native frame, applied to every current written (DTO and extras):
#: I_coil,PCS = -I_coil,IMAS (conductor current in A, not ampere-turns) and
#: Ip,PCS = -Ip,IMAS > 0. Reason: per-circuit values (cs1 = CS1U + CS1L in series)
#: feeding KCURR I_CSPF_ref (pcs@04e9b7f modules/KCURR/pcssp_KCURR.slx Inport SID 2).
#: Source: pcs@04e9b7f (branch XPT02) assessment/TestCases/IntegratedAssessments/
#: XPTL02_105033_mod1/setup_pulse_data_from_db.m:26,31 (all 11 CS/PF references
#: = -1.0 x the IMAS-sign currents_ref.txt; ip_ref.txt positive); limits 45 kA CS /
#: 48-55 kA PF: pcs@aa217bc modules/CLA_CCS/CLA_CCS_ext/CLA_CCS_loadtp.m:16.
IMAS_TO_PCS_CURRENT_SIGN = -1


def quantity_name(path: str) -> str:
    """Plain PDS name of an internal IDS lookup key, for the outputs (no IMAS path)."""
    fixed = {
        IP_PATH: "Ip reference",
        CC_R: "current centroid R",
        CC_Z: "current centroid Z",
        XPOINT.format(c="r"): "X-point R",
        XPOINT.format(c="z"): "X-point Z",
    }
    if path in fixed:
        return fixed[path]
    if m := re.fullmatch(
        r"pulse_schedule/pf_active/coil\((\d+)\)/current/reference", path
    ):
        k = int(m.group(1))
        return f"coil {COILS[k - 1] if k <= len(COILS) else k} current"
    if m := re.fullmatch(
        r"pulse_schedule/position_control/boundary_outline\((\d+)\)/([rz])/reference",
        path,
    ):
        return f"isoflux point {m.group(1)} {m.group(2).upper()}"
    if m := re.fullmatch(
        r"pulse_schedule/position_control/gap\((\d+)\)/(value/reference|name|r|z|angle)",
        path,
    ):
        what = {"value/reference": "value", "r": "R", "z": "Z"}.get(
            m.group(2), m.group(2)
        )
        return f"gap {m.group(1)} {what}"
    generic = re.sub(r"^pulse_schedule/|/reference$", "", path)
    return re.sub(r"\((\d+)\)", r" \1", generic).replace("/", " ").replace("_", " ")


def _is_current(path: str) -> bool:
    """Ip reference or a coil current (converted to the PCS frame on output)."""
    return path == IP_PATH or bool(
        re.fullmatch(r"pulse_schedule/pf_active/coil\(\d+\)/current/reference", path)
    )


ALARMS = [
    ("maximum_time", "s"),
    ("ip_less_than_min_ip", "a"),
    ("ip_more_than_min_ip", "a"),
    ("max_ip_ctrl_error", "a"),
    ("max_rpl_ctrl_error", "m"),
    ("max_zpl_ctrl_error", "m"),
    ("max_gap_ctrl_error", "m"),
    ("max_flux_ctrl_error", "wb"),
    ("max_cs_pf_ctrl_error", "a"),
]
TRANSITION_BOXES = ["diverted", "control_in_box", "xp_in_box"]
#: display units added to the mode windows (the only addition to the mock's node
#: structure). "A" for ip0s/ip0f: pcs@04e9b7f (branch XPT02) assessment/TestCases/
#: IntegratedAssessments/XPTL02_105033_mod1/setup_MCLS_01.m:20
#: ``MCMode(1).Ip0intervals = 1.8*1e6; % ... Ipstart [A]`` (setup file; MCLS block
#: not opened). "s" for t0s/t0f: segment-relative seconds (decision above).
MODE_WINDOW_UNITS = {"t0s": "s", "t0f": "s", "ip0s": "A", "ip0f": "A"}

#: our field -> MCLS field (Table B of three_entities_waveforms_segments_mcls.md).
#: Keys must be identifier-like ([A-Za-z0-9_-]): the PSPS GUI rejects a struct key
#: with any other character (verified 2026-11-13, series 3 V02 / series 4), so
#: "a / b" pairs are written as "a_or_b" and wildcards as "_any".
MCLS_MAP = {
    "t0s_or_t0f": "time0intervals / time0intervalf (s, segment-relative here)",
    "ip0s_or_ip0f": "Ip0intervals / Ip0intervalf (A here)",
    "shape_control_ref": "ShapeIpControlMode",
    "ip_control_ref": "IpControlMode",
    "vs_control_ref": "VSControlMode",
    "snu": "SNUControl",
    "current_limit_avoidance": "CurrentLimitAvoidance",
    "ref_smooth": "ReferenceSmoothTransition (RefSmoothTrans)",
    "vs1_mc_allocator_mode": "VS1MCAllocatorMode",
    "scp_ip_scaling_or_vs_ip_scaling": "SCIpScaling / VSIpScaling (0 off, 1 nominal, "
    "2 measured)",
    "transition_conditions_any": "EnablingConditions 1-3 with BoxForCentroid / BoxForXP",
    "control_conditions_any": "BoxForXPUP, dsepmin, VS3Kicks, VS3FailureManagControl",
    "alarms_any": "timemax, Ipmin, Ipmax, Max*ContrError, AlarmsEnabled",
    "overlapping_modes_priority": "NextEnabledModes + priority pick (UNVERIFIED)",
}

#: Allowed struct keys. The PSPS GUI rejects a document whose struct keys contain
#: any other character (verified 2026-11-13: series 3 V02 / series 4 isolated the
#: rejection of the extended file to the former ``mcls_field_map`` keys such as
#: "t0s / t0f"); UUID keys (hyphens) and catalogue ids ("0", "1") pass.
KEY_RE = re.compile(r"[A-Za-z0-9_-]+")


# --------------------------------------------------------------------------- nodes
def _node(kind: str, value, constraints: dict | None = None) -> dict:
    d = {"type": kind, "value": value}
    if constraints:
        d["constraints"] = constraints
    return d


def _clean_time(x: float) -> float:
    """Time computed by float64 arithmetic, without binary noise (15.600000000000009 -> 15.6).

    Design times have at most 6 decimals, so rounding to 9 removes only the noise.
    """
    return round(float(x), 9)


def _str(v: str, constraints: dict | None = None) -> dict:
    return _node("string", str(v), constraints)


def _f32(x: float) -> dict:
    return _node("float32", float(np.float32(x)))


def _bool(b: bool) -> dict:
    return _node("bool", bool(b))


def _struct(d: dict) -> dict:
    """Struct node; every key must be identifier-like (``KEY_RE``, GUI rule)."""
    for k in d:
        if not (isinstance(k, str) and KEY_RE.fullmatch(k)):
            raise ValueError(f"struct key not identifier-like: {k!r}")
    return _node("struct", d)


def type_signature(node: dict):
    """Pure-value type of a typed node, as the CODAC PSPS parser compares it.

    psps-dto 1.4.0 (git.iter.org/coa/psps-dto@35a5846)
    src/lib/psps/dto/parse/presentation_value_parser.cpp:381-397 (``FinishList``)
    turns a list into a sup-dto array and rejects it ("inhomogeneous list not
    supported") unless every element has the same sup-dto type: a scalar's type
    name; an array's element type AND length; a struct's member names, in order,
    and member types; a list's length and element type. ``display`` and
    ``constraints`` are metadata, not type (a list whose elements differ only in
    ``display.units`` parses; the parser keeps the first element's metadata only).
    Verified with ``parse-psps-file -v`` on probe files, 2026-11-16.
    """
    kind = node["type"]
    if kind == "struct":
        return (
            "struct",
            tuple((k, type_signature(v)) for k, v in node["value"].items()),
        )
    if kind == "list":
        items = node["value"]
        return ("list", len(items), type_signature(items[0]) if items else None)
    if kind == "array":
        return ("array", node.get("element_type"), len(node["value"]))
    return kind


def _homogeneous(items: list) -> bool:
    """True when ``items`` is a non-empty list of struct nodes of one type signature."""
    if not items or not all(
        isinstance(e, dict) and e.get("type") == "struct" for e in items
    ):
        return False
    sig = type_signature(items[0])
    return all(type_signature(e) == sig for e in items[1:])


def _check_list(items: list) -> None:
    """GUI and parser rules for list nodes.

    GUI (pulseconfig.iter.org qualification server, 2026-11-13): struct elements
    only (a list of string or array nodes is rejected, series 2) and one key tuple,
    order included (series 8: ``events`` with ``release_threshold`` on one element
    only was rejected). CODAC PSPS parser (psps-dto 1.4.0,
    presentation_value_parser.cpp:381-397, verified 2026-11-16): at least one
    element, and one type signature for all elements (``type_signature``: array
    lengths and struct member names/types included). Collections whose elements can
    differ in shape are written as structs instead (``_keyed_struct``).
    """
    if not items:
        raise ValueError(
            "empty list: the PSPS parser requires at least one list element"
        )
    keys = None
    for i, e in enumerate(items):
        if not (isinstance(e, dict) and e.get("type") == "struct"):
            raise ValueError(f"list element {i} is not a struct node")
        k = tuple(e["value"].keys())
        if keys is None:
            keys = k
        elif k != keys:
            raise ValueError(
                f"list element {i} has keys {k}, element 0 has {keys}: the PSPS "
                "GUI requires every list element to carry the same keys"
            )
    sig = type_signature(items[0])
    for i, e in enumerate(items[1:], 1):
        if type_signature(e) != sig:
            raise ValueError(
                f"list element {i} differs in type from element 0 (array length or "
                "member type): the PSPS parser rejects an inhomogeneous list"
            )


def _list(items: list) -> dict:
    """List node; every ``list`` node is built here (``_check_list``)."""
    _check_list(items)
    return _node("list", items)


def member_key(*parts: str) -> str:
    """Struct member name from free text: runs of characters outside ``KEY_RE``
    become ``_``, parts joined by ``__`` ("flat-top", "gap 12 value" ->
    ``flat-top__gap_12_value``)."""
    out = [re.sub(r"[^A-Za-z0-9_-]+", "_", str(p)).strip("_") or "x" for p in parts]
    return "__".join(out)


def _keyed_struct(entries: list[tuple[str, dict]]) -> dict:
    """Struct of ``(key, node)`` pairs with unique keys, in the given order; a repeated
    key gets ``_2``, ``_3``, ... (deterministic). Used for collections whose elements
    may differ in type, which the PSPS parser rejects as a list."""
    out: dict = {}
    for key, node in entries:
        k, n = key, 2
        while k in out:
            k, n = f"{key}_{n}", n + 1
        out[k] = node
    return _struct(out)


def _list_or_struct(items: list, prefix: str = "item") -> dict:
    """A list when the elements are homogeneous structs (parser rule), else a struct
    ``{<prefix>_000: element, ...}`` with the same elements in the same order."""
    if _homogeneous(items):
        return _list(items)
    return _keyed_struct([(f"{prefix}_{i:03d}", e) for i, e in enumerate(items)])


def _array(values, element_type: str, units: str | None = None) -> dict:
    if element_type == "float32":
        vals = [float(np.float32(v)) for v in values]
    else:
        vals = [int(v) for v in values]
    d = {"type": "array", "element_type": element_type, "value": vals}
    if units is not None:
        d["display"] = {"units": units}
    return d


def _waveform(x, y, units: str) -> dict:
    return _struct(
        {"xValues": _array(x, "float32", "s"), "yValues": _array(y, "float32", units)}
    )


#: unfilled "value" and reason prefix of the waveform placeholders
PLACEHOLDER = "placeholder waveform (zeros)"
#: name of the placeholder mode written when a segment has no MCLS mode (the PSPS
#: GUI rejects an empty ``modes`` list, bisection of 2026-11-13)
DEFAULT_MODE = "default"


def _placeholder(duration: float, units: str) -> dict:
    """Constant-zero waveform over [0, duration] s, written where the design has nothing.

    The PSPS GUI rejects a setpoint with an empty ``xValues``/``yValues`` array
    ("Error while parsing data", bisection step 09 of 2026-11-13), so a missing
    quantity is written as two points (0, 0) and (duration, 0) and listed in
    ``properties.unfilled`` with the reason.
    """
    return _waveform([0.0, _clean_time(max(float(duration), 0.0))], [0.0, 0.0], units)


def _f32_units(x: float, units: str) -> dict:
    d = _f32(x)
    d["display"] = {"units": units}
    return d


def _int32_units(x: int, units: str) -> dict:
    d = _node("int32", int(x))
    d["display"] = {"units": units}
    return d


def uid(*parts: str) -> str:
    """Deterministic UUID (version 5) of the joined names."""
    return str(uuid.uuid5(NAMESPACE, "/".join(parts)))


# --------------------------------------------------------------------------- design input
def _pieces_to_waveform(pieces) -> tuple[np.ndarray, np.ndarray]:
    t: list[float] = []
    v: list[float] = []
    for p in pieces:
        if not (isinstance(p, dict) and "time" in p and "value" in p):
            raise ValueError(f"only time/value tendencies are supported, got {p!r}")
        for a, b in zip(p["time"], p["value"], strict=True):
            if t and abs(float(a) - t[-1]) <= TOL:
                v[-1] = float(b)
                continue
            t.append(float(a))
            v.append(float(b))
    return np.asarray(t), np.asarray(v)


def design_from_two_file(
    waveforms_doc: dict, segments_doc: dict, name: str, sources=None
) -> dict:
    """Intermediate design from the two-file set (``*_waveforms.yaml`` + ``*_segments.yaml``).

    Waveforms: Waveform-Editor YAML, global, pulse time (s), IMAS sign. Segments: the
    PROPOSAL format of ``105073_segments.yaml`` (``nominal`` [start, end] in pulse time,
    MCLS windows ``modes.<m>.t`` in pulse time and ``.ip`` in MA, +|Ip|).
    """
    waves: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    scalars: dict[str, object] = {}
    groups: dict[str, list[str]] = {}
    for group, body in waveforms_doc.items():
        if group == "globals" or not isinstance(body, dict):
            continue
        for path, val in body.items():
            groups.setdefault(group, []).append(path)
            if isinstance(val, list):
                waves[path] = _pieces_to_waveform(val)
            else:
                scalars[path] = val
    segs, stop = [], None
    for s in segments_doc.get("segments", []):
        if "nominal" not in s:
            stop = dict(s)
            continue
        segs.append(
            {
                "name": s["name"],
                "id": s.get("id"),
                "start": float(s["nominal"][0]),
                "end": float(s["nominal"][1]),
                "modes": dict(s.get("modes") or {}),
                "transitions": list(s.get("transitions") or []),
                "overlay": dict(s.get("overlay") or {}),
            }
        )
    return {
        "name": name,
        "pulse": (segments_doc.get("pulse") or {}).get("number"),
        "dd_version": (waveforms_doc.get("globals") or {}).get("dd_version"),
        "waveforms": waves,
        "scalars": scalars,
        "groups": groups,
        "segments": segs,
        "stop": stop,
        "mode_library": dict(segments_doc.get("modes") or {}),
        "events": segments_doc.get("events"),
        "exception_handling": segments_doc.get("exception_handling"),
        "sl_editable": segments_doc.get("sl_editable"),
        "ip_window_unit_A": 1e6,
        "time_origin": "plasma_initiation (pulse time, s)",
        "sources": dict(sources or {}),
    }


def design_from_two_file_paths(
    waveforms_yaml, segments_yaml, name: str | None = None
) -> dict:
    wp, sp = Path(waveforms_yaml), Path(segments_yaml)
    sources = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in (wp, sp)
    }
    if name is None:
        name = re.sub(r"_waveforms$", "", wp.stem)
    return design_from_two_file(
        yaml.safe_load(wp.read_text()), yaml.safe_load(sp.read_text()), name, sources
    )


def design_from_pulse_design(design, sources=None) -> dict:
    """Intermediate design from an ``ip_waveform_export`` PulseDesign (converter YAML).

    Carries the Ip waveform, the segments (watchdog transitions), the PROPOSED
    ``events``/``exception_handling`` blocks and the constant ``psc.references``
    (CSPF_curr_ref, Rpl_ref, Zpl_ref) held over the timed segments, and the ``modes:``
    library and per-segment MCLS windows re-read from the converter YAML (``sources``).
    """
    wf = design.waveform
    waves = {wf.ids_path: (np.asarray(wf.time, float), np.asarray(wf.value, float))}
    timed = design.timed_segments
    win = (timed[0].start, timed[-1].end)
    refs = ((design.psc or {}).get("references")) or {}

    def const(val):
        return np.asarray(win, float), np.asarray([float(val), float(val)])

    if "CSPF_curr_ref" in refs:
        for k, c in enumerate(refs["CSPF_curr_ref"]["value"], 1):
            waves[COIL.format(k=k)] = const(c)
    if "Rpl_ref" in refs:
        waves[CC_R] = const(refs["Rpl_ref"]["value"])
    if "Zpl_ref" in refs:
        waves[CC_Z] = const(refs["Zpl_ref"]["value"])
    lib, seg_modes = _raw_modes(sources)
    segs = [
        {
            "name": s.name,
            "id": s.id,
            "start": s.start,
            "end": s.end,
            "modes": dict(seg_modes.get(s.name) or {}),
            "transitions": [{"to": s.wd_target, "time_after": s.duration}],
            "overlay": {},
        }
        for s in timed
    ]
    stop = next(
        ({"name": s.name, "id": s.id} for s in design.segments if s.is_stop), None
    )
    return {
        "name": design.name,
        "pulse": design.globals.get("pulse"),
        "dd_version": design.globals.get("dd_version"),
        "waveforms": waves,
        "scalars": {},
        "groups": {},
        "segments": segs,
        "stop": stop,
        "mode_library": lib,
        "events": design.events,
        "exception_handling": design.exception_handling,
        # raw exception values of the converter YAML: PCS frame with "minus_ip"
        "exception_ip_sign": -1 if design.convention == "imas" else 1,
        "sl_editable": None,
        "ip_window_unit_A": 1.0,
        "time_origin": f"{design.time_origin} (designer time, s)",
        "psc_clock_offset_s": design.cut_at,
        "sources": dict(sources or {}),
    }


def _raw_modes(sources) -> tuple[dict, dict]:
    """(mode library, {segment name: modes windows}) re-read from the converter YAML in ``sources``.

    The windows are in designer time (s) and A (``ip_window_unit_A`` = 1.0).
    """
    for p in sources or {}:
        try:
            doc = yaml.safe_load(Path(p).read_text())
        except (OSError, yaml.YAMLError, TypeError):
            continue
        if not isinstance(doc, dict):
            continue
        segs = {
            str(s.get("name")): dict(s.get("modes") or {})
            for s in doc.get("segments") or []
            if isinstance(s, dict)
        }
        return dict(doc.get("modes") or {}), segs
    return {}, {}


# --------------------------------------------------------------------------- cutting
def cut(
    t: np.ndarray, v: np.ndarray, a: float, b: float
) -> tuple[list[float], list[float]]:
    """Vertices of (t, v) inside [a, b], interpolated at the clipped ends; x relative to a."""
    if t.size == 0:
        return [], []
    lo, hi = max(a, float(t[0])), min(b, float(t[-1]))
    if hi - lo <= TOL:
        return [], []
    inner = (t > lo + TOL) & (t < hi - TOL)
    ts = np.concatenate(([lo], t[inner], [hi]))
    return [float(x - a) for x in ts], [float(y) for y in np.interp(ts, t, v)]


class _Unfilled:
    """Collect placeholder fields as {(field, reason): [where, ...]}."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str, str], list[str]] = {}

    def add(self, field: str, value, reason: str, where: str) -> None:
        self.items.setdefault((field, json.dumps(value), reason), []).append(where)

    def as_list(self) -> list[dict]:
        return [
            {"field": f, "value": json.loads(v), "reason": r, "where": w}
            for (f, v, r), w in self.items.items()
        ]


# --------------------------------------------------------------------------- builder
def _box(box: dict | None) -> dict:
    b = box or {}
    return _struct(
        {
            "enabled": _bool(bool(box)),
            "r": _f32(b.get("r", 0.0)),
            "z": _f32(b.get("z", 0.0)),
            "dr": _f32(b.get("dr", 0.0)),
            "dz": _f32(b.get("dz", 0.0)),
        }
    )


def _ref(catalogue: dict, cid: str | None, missing_name: str) -> dict:
    if cid is None:
        return _struct({"id": _str("0"), "name": _str(missing_name)})
    return _struct({"id": _str(cid), "name": _str(catalogue[cid])})


def _entry_boxes(design: dict, k: int) -> dict:
    """X-point boxes of the events that lead INTO segment k (derived MCLS xp_in_box)."""
    if k == 0:
        return {}
    prev, seg = design["segments"][k - 1], design["segments"][k]
    out = {}
    events = design.get("events") or {}
    for tr in prev["transitions"]:
        ev = events.get(tr.get("event"), {}) if tr.get("to") == seg["name"] else {}
        if ev.get("test") == "x_point_in_box" and ev.get("box"):
            out["xp_in_box"] = (tr["event"], ev["box"])
    return out


def _mode(
    design: dict, seg: dict, k: int, mname: str, window: dict, unf: _Unfilled
) -> dict:
    where = f"{seg['name']}/{mname}"
    lib = design["mode_library"].get(mname, {})
    dur = seg["end"] - seg["start"]
    if window.get("t"):
        t0s, t0f = (float(x) - seg["start"] for x in window["t"])
    else:
        t0s, t0f = 0.0, dur
        unf.add(
            "modes[].t0s/t0f",
            [0.0, "duration"],
            "no MCLS time window in the design (constant mode): whole segment assumed",
            where,
        )
    if window.get("ip"):
        # PCS frame: Ip,PCS = -Ip,IMAS > 0, so the window bounds are |Ip| (positive)
        ip0s, ip0f = (
            round(abs(float(x)) * design["ip_window_unit_A"]) for x in window["ip"]
        )
    else:
        ip0s, ip0f = 0, 0
        unf.add("modes[].ip0s/ip0f", [0, 0], "no MCLS Ip window in the design", where)
    lib = {
        k: ("off" if v is False else "on" if v is True else v) for k, v in lib.items()
    }
    shape = SHAPE_OF.get(lib.get("shape_ip"))
    ipc = IP_OF.get(lib.get("ip"))
    vsc = VS_OF.get(str(lib.get("vs")).lower()) if "vs" in lib else None
    for field, val, cid in (
        ("shape_control_ref", lib.get("shape_ip"), shape),
        ("ip_control_ref", lib.get("ip"), ipc),
        ("vs_control_ref", lib.get("vs"), vsc),
    ):
        if cid is None:
            unf.add(
                f"modes[].{field}",
                {"id": "0"},
                f"PDS value {val!r} has no entry in the "
                "mock catalogue (id '0' written)",
                where,
            )
    boxes = _entry_boxes(design, k)
    tc = {}
    for b in TRANSITION_BOXES:
        if b in boxes:
            tc[f"transition_conditions_{b}"] = _box(boxes[b][1])
        else:
            tc[f"transition_conditions_{b}"] = _box(None)
            unf.add(
                f"modes[].transition_conditions.transition_conditions_{b}",
                "disabled, 0",
                "no MCLS enabling box in the design",
                where,
            )
    cc = {
        "control_conditions_xp_up_in_box": _box(None),
        "control_conditions_dsep_min": _f32(0.0),
        "control_conditions_vs3_failure_management": _box(None),
        "control_conditions_vs3_kicks": _box(None),
    }
    unf.add(
        "modes[].control_conditions.*",
        "disabled, 0",
        "no MCLS control conditions in the design",
        where,
    )
    alarms = {
        a: _struct({"enabled": _bool(False), "threshold": _f32_units(0.0, u)})
        for a, u in ALARMS
    }
    unf.add(
        "modes[].alarms.*",
        "disabled, 0",
        "no MCLS alarm thresholds in the design; the PSC "
        "global-monitoring events (properties.events) are another mechanism, candidates "
        "ip_too_high -> ip_more_than_min_ip, z_excursion -> max_zpl_ctrl_error",
        where,
    )
    for f, v in (
        ("scp_ip_scaling", "off"),
        ("vs_ip_scaling", "off"),
        ("ref_smooth", False),
        ("vs1_mc_allocator_mode", False),
    ):
        unf.add(f"modes[].{f}", v, "not in the PDS mode library", where)
    unf.add(
        "modes[].overlapping_modes(_priority)",
        [],
        "no overlapping modes in the design",
        where,
    )
    on = {"on", "true", "1"}
    return _struct(
        {
            "id": _str("mode-" + mname.replace("_", "-")),
            "name": _str(mname),
            "t0s": _f32_units(t0s, MODE_WINDOW_UNITS["t0s"]),
            "t0f": _f32_units(t0f, MODE_WINDOW_UNITS["t0f"]),
            "ip0s": _int32_units(
                ip0s, MODE_WINDOW_UNITS["ip0s"]
            ),  # A, setup_MCLS_01.m:20
            "ip0f": _int32_units(ip0f, MODE_WINDOW_UNITS["ip0f"]),
            "overlapping_modes": _array([], "int32"),
            "overlapping_modes_priority": _array([], "int32"),
            "shape_control_ref": _ref(
                SHAPE_CATALOGUE, shape, str(lib.get("shape_ip", "none"))
            ),
            "ip_control_ref": _ref(IP_CATALOGUE, ipc, str(lib.get("ip", "none"))),
            "vs_control_ref": _ref(VS_CATALOGUE, vsc, str(lib.get("vs", "none"))),
            "transition_conditions": _struct(tc),
            "control_conditions": _struct(cc),
            "alarms": _struct(alarms),
            "snu": _bool(str(lib.get("snu", "off")).lower() in on),  # MCLS SNUControl
            "vs1_mc_allocator_mode": _bool(False),
            "scp_ip_scaling": _str("off", {"choice": list(SCALING_CHOICE)}),
            "vs_ip_scaling": _str("off", {"choice": list(SCALING_CHOICE)}),
            "ref_smooth": _bool(False),
            "current_limit_avoidance": _bool(str(lib.get("cla", "off")).lower() in on),
        }
    )


def _setpoint_value(
    design: dict,
    seg: dict,
    k: int,
    unf: _Unfilled,
    used: set,
    gap_slots: Sequence[int] = PSPS_GAP_SLOTS,
) -> dict:
    a, b = seg["start"], seg["end"]
    dur = b - a
    waves = design["waveforms"]

    def wf(path: str, units: str, field: str, scale: float = 1) -> dict:
        if path in seg["overlay"]:
            x, y = _pieces_to_waveform(seg["overlay"][path])
            used.add(path)
            return _waveform(list(x), [scale * v for v in y], units)
        if path in waves:
            used.add(path)
            x, y = cut(*waves[path], a, b)
            if x:
                return _waveform(x, [scale * v for v in y], units)
            unf.add(
                field,
                PLACEHOLDER,
                f"{PLACEHOLDER}, the design waveform '{quantity_name(path)}' does "
                "not overlap this segment",
                seg["name"],
            )
        else:
            unf.add(
                field,
                PLACEHOLDER,
                f"{PLACEHOLDER}, no design waveform '{quantity_name(path)}'",
                seg["name"],
            )
        return _placeholder(dur, units)

    def point(path_r: str, path_z: str, field: str) -> dict:
        return _struct(
            {"r": wf(path_r, "m", field + ".r"), "z": wf(path_z, "m", field + ".z")}
        )

    n_outline = sorted(
        {
            int(m.group(1))
            for p in waves
            if (m := re.search(r"boundary_outline\((\d+)\)", p))
        }
    )

    def points(field: str) -> dict:
        items = []
        for i, kk in enumerate(n_outline, 1):
            pr, pz = OUTLINE.format(k=kk, c="r"), OUTLINE.format(k=kk, c="z")
            p = point(pr, pz, f"{field}.points[{i - 1}]")
            p["value"]["id"] = _str(f"point{i:02d}")
            items.append(p)
        if not items:  # the mock's point shape: r, z, id (never an empty list)
            items.append(
                _struct(
                    {
                        "r": _placeholder(dur, "m"),
                        "z": _placeholder(dur, "m"),
                        "id": _str("point01"),
                    }
                )
            )
            unf.add(
                field + ".points",
                PLACEHOLDER,
                f"one placeholder point point01 ({PLACEHOLDER}), no isoflux "
                "control points in the design",
                seg["name"],
            )
        return _list(items)

    def refpoint(field: str) -> dict:
        unf.add(
            field + ".refpoint",
            PLACEHOLDER,
            f"{PLACEHOLDER}: PDS isoflux uses dPsi_ref = 0 at the control "
            "points; no explicit reference point in the design",
            seg["name"],
        )
        return _struct({"r": _placeholder(dur, "m"), "z": _placeholder(dur, "m")})

    sc1 = _struct(
        {
            "id": _str("1"),
            "name": _str(SHAPE_CATALOGUE["1"]),
            "parameters": _struct(
                {
                    "rcentroid": wf(CC_R, "m", "shape_control.1.rcentroid"),
                    "zcentroid": wf(CC_Z, "m", "shape_control.1.zcentroid"),
                }
            ),
        }
    )
    sc2 = _struct(
        {
            "id": _str("2"),
            "name": _str(SHAPE_CATALOGUE["2"]),
            "parameters": _struct(
                {
                    "refpoint": refpoint("shape_control.2"),
                    "points": points("shape_control.2"),
                }
            ),
        }
    )
    sc3 = _struct(
        {
            "id": _str("3"),
            "name": _str(SHAPE_CATALOGUE["3"]),
            "parameters": _struct(
                {
                    "refpoint": refpoint("shape_control.3"),
                    "points": points("shape_control.3"),
                    "xp": point(
                        XPOINT.format(c="r"), XPOINT.format(c="z"), "shape_control.3.xp"
                    ),
                }
            ),
        }
    )
    gaps = []
    for i, g in enumerate(gap_slots):  # slot gap{i+1:02d} <- PDS gap g
        gaps.append(
            _struct(
                {
                    "id": _str(f"gap{i + 1:02d}"),
                    "waveform": wf(GAP.format(k=g), "m", f"shape_control.4.gaps[{i}]"),
                }
            )
        )
    sc4 = _struct(
        {
            "id": _str("4"),
            "name": _str(SHAPE_CATALOGUE["4"]),
            "parameters": _struct({"gaps": _list(gaps)}),
        }
    )
    circuits = {}
    for c in CIRCUITS:
        circuits[c] = wf(  # PCS native frame: -I_IMAS, conductor current in A
            COIL.format(k=COILS.index(c.upper()) + 1),
            "A",
            f"waveforms_by_circuit.{c}",
            IMAS_TO_PCS_CURRENT_SIGN,
        )

    def catalogue(cat: dict) -> dict:
        return _struct(
            {i: _struct({"id": _str(i), "name": _str(n)}) for i, n in cat.items()}
        )

    modes = [_mode(design, seg, k, m, w or {}, unf) for m, w in seg["modes"].items()]
    if not modes:  # the GUI rejects an empty modes list: one placeholder mode
        modes = [_mode(design, seg, k, DEFAULT_MODE, {}, unf)]
        unf.add(
            "modes",
            DEFAULT_MODE,
            f"one placeholder mode '{DEFAULT_MODE}' (no MCLS mode in the design; "
            "the GUI rejects an empty list)",
            seg["name"],
        )
    return _struct(
        {
            "id": _str("controller-magnetics-1"),
            "name": _str("Magnetics Controller"),
            "type": _str("magnetics"),
            "scheme": _str("current"),
            "shape_control": _struct({"1": sc1, "2": sc2, "3": sc3, "4": sc4}),
            "ip_control": catalogue(IP_CATALOGUE),
            "vs_control": catalogue(VS_CATALOGUE),
            "waveforms_by_circuit": _struct(circuits),
            "modes": _list(modes),
        }
    )


def _gap_slots(gap_slots: Sequence[int]) -> tuple[int, ...]:
    """Check an override of PSPS_GAP_SLOTS: six distinct PDS gap indices >= 1."""
    slots = tuple(int(g) for g in gap_slots)
    if len(slots) != len(PSPS_GAP_SLOTS) or len(set(slots)) != len(slots):
        raise ValueError(
            f"gap_slots needs {len(PSPS_GAP_SLOTS)} distinct PDS gap indices: {slots}"
        )
    if min(slots) < 1:
        raise ValueError(f"PDS gap indices are 1-based: {slots}")
    return slots


def _strict(
    design: dict, unf: _Unfilled, used: set, gap_slots: tuple[int, ...]
) -> list:
    """The strict document: exactly the mock's structure (plus the mode-window units)."""
    name = design["name"]
    ps_id = uid(name, "pulse_schedule")
    seg_nodes = {}
    for k, seg in enumerate(design["segments"]):
        sid = uid(name, "segment", seg["name"])
        pid = uid(name, "segment", seg["name"], "setpoint", "magnetics")
        value = _setpoint_value(design, seg, k, unf, used, gap_slots)
        seg_nodes[sid] = _struct(
            {
                "properties": _struct(
                    {
                        "id": _str(sid, {"id": True}),
                        "name": _str(seg["name"]),
                        "duration": _node(
                            "float64",
                            _clean_time(seg["end"] - seg["start"]),
                            {"range": dict(DURATION_RANGE)},
                        ),
                    }
                ),
                "setpoints": _struct({pid: _setpoint(pid, value)}),
            }
        )
    unf.add(
        "properties.author",
        "",
        "persons are not named by the PDS tools",
        "schedule properties",
    )
    unf.add(
        "setpoint.scheme",
        "current",
        "derived: PDS runs KCURR + RZIp_CCS (current "
        "control scheme, MCLS CCSVCSmodes 0); the mock has 'voltage'; value list unknown",
        "all segments",
    )
    return [
        {"encoding": ENCODING},
        _struct(
            {
                "component_type": _str("pulse_schedule"),
                "properties": _struct(
                    {
                        "id": _str(ps_id, {"id": True}),
                        "name": _str(name),
                        "description": _str(
                            f"PDS export of {name}"
                            + (
                                f" (pulse {design['pulse']})"
                                if design.get("pulse")
                                else ""
                            )
                            + "; see the _psps_dto_extended.json companion"
                        ),
                        "author": _str(""),
                        "state": _str(
                            "New",
                            {
                                "choice": list(STATE_CHOICE),
                                "transition": [
                                    {"from": f, "to": t} for f, t in STATE_TRANSITIONS
                                ],
                            },
                        ),
                        "software_version": _list(
                            [
                                _struct(
                                    {
                                        "software": _str(SOFTWARE[0]),
                                        "version": _str(SOFTWARE[1]),
                                    }
                                )
                            ],
                        ),
                    }
                ),
                "segments": _struct(seg_nodes),
            }
        ),
    ]


def _setpoint(pid: str, value: dict) -> dict:
    return _struct(
        {
            "properties": _struct(
                {
                    "id": _str(pid, {"id": True}),
                    "name": _str("Magnetics Controller Setpoint"),
                    "value": value,
                    "enabled": _bool(True),
                }
            )
        }
    )


# --------------------------------------------------------------------------- extended
#: node types of the mock (the extended file uses no other)
NODE_TYPES = {
    "string",
    "int32",
    "float32",
    "float64",
    "bool",
    "struct",
    "list",
    "array",
}
ARRAY_ELEMENT_TYPES = {"float32", "int32"}
#: circuits added to waveforms_by_circuit in the extended file (11 circuits)
EXTRA_CIRCUITS = ["pf5", "pf6"]
ROLE_NOMINAL, ROLE_EXCEPTION, ROLE_STOP = "nominal", "exception", "stop"
#: units of the PSC monitoring signals of the converter format (psc.inputs descriptions)
SIGNAL_UNITS = {"ip_ip__meas": "A", "cs_margin": "A", "z_meas": "m"}
#: unit written in the design test strings -> (SI unit, factor)
UNIT_SCALE = {
    "MA": ("A", 1e6),
    "kA": ("A", 1e3),
    "A": ("A", 1.0),
    "m": ("m", 1.0),
    "cm": ("m", 1e-2),
    "s": ("s", 1.0),
    "": ("", 1.0),
}
TEST_RE = re.compile(
    r"^\s*(?P<sig>.+?)\s*(?P<op><=|>=|==|<|>)\s*"
    r"(?P<num>[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(?P<unit>[A-Za-z]*)\s*$"
)
#: PCS module settings of the KCURR block written to pds_additional.kcurr: units
KCURR_UNITS = {
    "PosCurSlewRate": "A/s",
    "NegCurSlewRate": "A/s",
    "Vup": "V",
    "Vlow": "V",
    "Ts_GainScheduling": "s",
}


def _seg_wave(design: dict, seg: dict, path: str):
    """(x segment-relative, y) of a design quantity in a segment, overlay first; None if none."""
    if path in seg.get("overlay", {}):
        x, y = _pieces_to_waveform(seg["overlay"][path])
        return [float(a) for a in x], [float(b) for b in y]
    if path in design["waveforms"]:
        x, y = cut(*design["waveforms"][path], seg["start"], seg["end"])
        return (x, y) if x else None
    return None


def _units_of(path: str) -> str:
    if _is_current(path):
        return "A"
    if re.search(r"position_control/", path):
        return "m"
    return ""


def _wave_node(xy, units: str, scale: float = 1.0, duration: float = 0.0) -> dict:
    """Typed waveform of (x, y); the zero placeholder over ``duration`` when xy is None."""
    if xy is None:
        return _placeholder(duration, units)
    x, y = xy
    return _waveform(x, [scale * v + 0.0 for v in y], units)  # + 0.0: no -0.0


def _parse_test(text: str):
    """'cs_margin < 8.30 kA' -> ('cs_margin', '<', 8300.0, 'A'); None if not a comparison."""
    m = TEST_RE.match(str(text))
    if not m or m.group("unit") not in UNIT_SCALE:
        return None
    unit, f = UNIT_SCALE[m.group("unit")]
    return m.group("sig"), m.group("op"), float(m.group("num")) * f, unit


def _events(design: dict) -> list[dict]:
    """Design events, normalised: name, signal, test, threshold, release, latch, box."""
    out = []
    for name, e in (design.get("events") or {}).items():
        e = e or {}
        ev = {"name": name, "latch": bool(e.get("latch", False)), "box": e.get("box")}
        if "op" in e and "signal" in e:  # converter format: numeric threshold
            sig, unit = str(e["signal"]), SIGNAL_UNITS.get(str(e["signal"]), "")
            if e.get("reference") is not None:
                sig = f"|{sig} - {e['reference']}|"
            ev |= {"signal": sig, "test": str(e["op"])}
            ev["threshold"] = (float(e["threshold"]), unit)
            if e.get("release_threshold") is not None:
                ev["release"] = (float(e["release_threshold"]), unit)
        else:  # two-file format: test string with units, or a named predicate
            p = _parse_test(e.get("test", ""))
            if p:
                ev |= {"signal": p[0], "test": p[1], "threshold": (p[2], p[3])}
            else:
                ev |= {"signal": "", "test": str(e.get("test", ""))}
            r = _parse_test(e.get("release", "")) if e.get("release") else None
            if r:
                ev["release"] = (r[2], r[3])
        out.append(ev)
    return out


def _exceptions(design: dict) -> list[dict]:
    """Exception segments, normalised from the two-file list and/or the converter block.

    Two-file list (``<name>_segments.yaml``): name, id, kind, on, timeout_s, then, action
    (text). Converter block (``exception_handling:`` of the converter YAML, also given as
    ``design["exception_handling_detail"]``): soft overlays with ``points`` and hard
    segments with from/to/ramp/hold, values in the PCS frame (``exception_ip_sign``).
    """
    eh = design.get("exception_handling")
    detail = design.get("exception_handling_detail")
    conv = eh if isinstance(eh, dict) else detail if isinstance(detail, dict) else None
    base = None if isinstance(eh, dict) else list(eh or [])
    sign = float(design.get("exception_ip_sign", 1))
    conv_by: dict[str, dict] = {}
    if conv:
        sudden = {
            h.get("target"): h.get("event") for h in conv.get("hard_sudden") or []
        }
        for s in conv.get("soft") or []:
            pts = s.get("points") or {}
            ip = None
            if pts.get("time"):
                ip = (
                    [float(t) for t in pts["time"]],
                    [sign * float(v) for v in pts["value"]],
                )
            conv_by[s["name"]] = {
                "pcs_id": s.get("id"),
                "kind": "soft",
                "on": s.get("event") or "",
                "timeout_s": s.get("wd_time"),
                "then": s.get("wd_target"),
                "ip": ip,
                "recovery": bool(s.get("recovery")),
                "action": s.get("action"),
            }
        for h in conv.get("hard") or []:
            ramp, hold = h.get("ramp_s"), float(h.get("hold_s") or 0.0)
            ip, timeout = None, None
            if ramp is not None and "from_value" in h and "to_value" in h:
                a, b = sign * float(h["from_value"]), sign * float(h["to_value"])
                ip = ([0.0, float(ramp)], [a, b])
                if hold > 0:
                    ip = (ip[0] + [float(ramp) + hold], ip[1] + [b])
                timeout = float(ramp) + hold
            conv_by[h["name"]] = {
                "pcs_id": h.get("id"),
                "kind": "hard",
                "on": sudden.get(h["name"]) or "",
                "timeout_s": timeout,
                "then": h.get("wd_target"),
                "ip": ip,
                "recovery": False,
                "action": h.get("action"),
            }
    if base is None:
        return [{"name": n} | d for n, d in conv_by.items()]
    out = []
    for e in base:
        d = conv_by.get(e["name"], {})
        on = e.get("on", e.get(True))  # YAML 1.1 reads the key 'on' as True
        out.append(
            {
                "name": e["name"],
                "pcs_id": e.get("id", d.get("pcs_id")),
                "kind": e.get("kind", d.get("kind", "")),
                "on": str(on) if on is not None else d.get("on", ""),
                "timeout_s": e.get("timeout_s", d.get("timeout_s")),
                "then": e.get("then", d.get("then")),
                "ip": d.get("ip"),
                "recovery": d.get("recovery", False),
                "action": e.get("action"),
            }
        )
    return out


def _is_num(v) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def _typed(obj, units: dict | None = None, key: str = ""):
    """JSON-like value -> typed node (numbers float32, numeric lists float32 arrays,
    other lists -> lists of structs: {item}, {row} for matrix rows)."""
    u = (units or {}).get(key)
    if isinstance(obj, bool):
        return _bool(obj)
    if isinstance(obj, int | float):
        return _f32_units(obj, u) if u else _f32(obj)
    if isinstance(obj, str):
        return _str(obj)
    if isinstance(obj, dict):
        return _struct({k: _typed(v, units, k) for k, v in obj.items()})
    if isinstance(obj, list):
        if all(_is_num(v) for v in obj):
            return _array(obj, "float32", u)
        # lists of structs; a struct {item_000: ...} when the elements differ in
        # type (array length, member names/types), which the PSPS parser rejects
        if all(isinstance(v, str) for v in obj):
            return _list([_struct({"item": _str(v)}) for v in obj])
        if all(isinstance(v, list) and all(_is_num(x) for x in v) for v in obj):
            rows = [_struct({"row": _array(row, "float32", u)}) for row in obj]
            return _list_or_struct(rows, "row")
        if all(isinstance(v, dict) for v in obj):
            return _list_or_struct([_typed(v, units, key) for v in obj])
        return _list_or_struct([_struct({"item": _typed(v, units, key)}) for v in obj])
    raise TypeError(f"cannot type {obj!r}")


def _kcurr(param: dict | None):
    """KCURR settings of the run (active gain set, limits, scheduling), provenance dropped."""
    if not param or str(param.get("_status", "")).startswith("placeholder"):
        return None
    out: dict = {}
    if param.get("_owner"):
        out["owner"] = _str(param["_owner"])
    coil_order = (param.get("_source") or {}).get("coil_order")
    if coil_order:
        out["coil_order"] = _str(coil_order)
    gains = param.get("KCURR_PFPO1_Gains") or {}
    sel = gains.get("selected")
    if sel and isinstance(gains.get(sel), dict):
        g = gains[sel]
        label = g.get("_label")
        out["active_gain_set"] = _str(f"{sel} ({label})" if label else sel)
        out["gains"] = _typed({k: v for k, v in g.items() if not k.startswith("_")})
    for key, name in (
        ("KCURR_PFPO1_tp", "limits"),
        ("ParameterScheduling_KCURR", "scheduling"),
    ):
        block = param.get(key) or {}
        kept = {k: v for k, v in block.items() if not k.startswith("_") and k != "Tag"}
        if kept:
            out[name] = _typed(kept, KCURR_UNITS)
    return _struct(out) if out else None


#: reason recorded in ``properties.unfilled`` for every event field filled only to
#: keep the key set of ``properties.events`` homogeneous (GUI rule, series 8)
SAME_KEYS = "the GUI requires every list element to carry the same keys"


def _event_nodes(evs: list[dict], targets: dict, seg_uuid, unf: _Unfilled) -> list:
    """Typed event structs with ONE key set: name, signal, test, threshold,
    release_threshold, [box], latch, action, target.

    The PSPS GUI rejects a list whose struct elements differ in their keys
    (series 8 of 2026-11-13), so every event carries ``release_threshold``
    (``= threshold``, no hysteresis, when the design gives none) and, when the
    design gives no numeric threshold (named predicate such as ``x_point_in_box``),
    a zero ``threshold`` without units; ``box`` is written on every event as soon as
    one event has a box (zeros, same keys, for the others). Each filling is listed
    in ``properties.unfilled`` (``SAME_KEYS``).
    """
    box_keys: list[str] = []
    for ev in evs:
        for k in ev.get("box") or {}:
            if k not in box_keys:
                box_keys.append(k)
    where = "properties.events"
    out = []
    for ev in evs:
        name = ev["name"]
        d = {
            "name": _str(name),
            "signal": _str(ev["signal"]),
            "test": _str(ev["test"]),
        }
        if "threshold" in ev:
            d["threshold"] = _f32_units(*ev["threshold"])
        else:
            d["threshold"] = _f32(0.0)
            unf.add(
                f"events.{name}.threshold",
                0,
                f"named predicate '{ev['test']}' without numeric threshold; "
                + SAME_KEYS,
                where,
            )
        if "release" in ev:
            d["release_threshold"] = _f32_units(*ev["release"])
        else:
            d["release_threshold"] = dict(d["threshold"])
            unf.add(
                f"events.{name}.release_threshold",
                "= threshold",
                "no hysteresis in the design; " + SAME_KEYS,
                where,
            )
        if box_keys:
            box = ev.get("box") or {}
            d["box"] = _typed(
                {k: float(box.get(k, 0.0)) for k in box_keys},
                dict.fromkeys(box_keys, "m"),
            )
            if not box:
                unf.add(
                    f"events.{name}.box",
                    dict.fromkeys(box_keys, 0),
                    "no box in the design (not a box predicate); " + SAME_KEYS,
                    where,
                )
        d["latch"] = _bool(ev["latch"])
        d["action"] = _str("enter_segment")
        d["target"] = _str(seg_uuid(targets.get(name)))
        out.append(_struct(d))
    return out


def _conventions(design: dict, gap_slots: tuple[int, ...]) -> dict:
    slots = ", ".join(str(g) for g in gap_slots)
    origin = str(design.get("time_origin") or "")
    if design.get("psc_clock_offset_s") is not None:
        origin += f"; PSC clock 0 = {design['psc_clock_offset_s']} s"
    c = {
        "sign_frame": "PCS frame: Ip > 0; coil currents in the PCS sign, i.e. negated "
        "with respect to the PDS design values",
        "circuit_current_unit": "conductor current in A per circuit, not ampere-turns; "
        "cs1 = CS1U + CS1L in series",
        "time_origin": "xValues, t0s/t0f and watchdog_s in s relative to the start of "
        "their segment",
        "design_time_origin": "design times (pds_additional.design_start_s): " + origin,
        "gap_slots": f"gap01..gap06 = PDS gaps {slots}"
        + (
            " (assumption, may change)"
            if gap_slots == PSPS_GAP_SLOTS
            else " (override)"
        ),
        "catalogue_id_0": 'id "0": the PDS mode value has no catalogue entry (no shape '
        "control, feed-forward Ip); name = the PDS value",
        "catalogue_mapping": "ip_control 1 = KCURR, 2 = Ip by the shape controller; "
        "vs_control 1-4 = Off, VS1, VS3, VS1+VS3; shape_control 1-4 = RZIp, Isoflux, "
        "Isoflux XP, Gaps (PCS mode settings, assumption)",
        "refpoint": "isoflux refpoint assumed to be the limiter contact point R(t), Z(t); "
        "the design has none, placeholder zeros written",
        "placeholders": "a waveform the design does not provide is written as the "
        "2-point zero waveform (0, 0), (segment duration, 0) and a missing isoflux "
        "point list as one zero point point01, never as an empty array (the PSPS "
        "GUI rejects empty arrays); in the zero-length STOP segment the placeholder "
        "is (0, 0), (0, 0); each is listed in properties.unfilled",
        "setpoints_and_modes": "every segment carries exactly one Magnetics setpoint "
        "and every setpoint at least one mode (the PSPS GUI rejects an empty "
        "setpoints object and an empty modes list, verified 2026-11-13); a segment "
        f"without MCLS mode gets the placeholder mode '{DEFAULT_MODE}' (whole-segment "
        "window, Ip window 0, catalogue id 0); exception and STOP segments inherit "
        "the modes of the last nominal segment (assumption)",
        "lists": "list nodes hold struct nodes only (the PSPS GUI rejects a list of "
        "string or array nodes, verified 2026-11-13, series 2 variants V02 and V06): "
        "extension paths as path structs, string lists as item or field structs, "
        "matrices as row structs; all elements of a list carry the same keys in "
        "the same order (verified 2026-11-13, series 8) and, for the PSPS parser "
        "(psps-dto 1.4.0, checked 2026-11-16), the same type including array lengths "
        "and member types, with at least one element; collections whose elements "
        "differ (waveforms and scalars without a slot) are structs keyed "
        "<segment>__<quantity> or <quantity>",
        "keys": "struct keys contain only letters, digits, '_' and '-' (the GUI "
        "rejects other characters; verified 2026-11-13)",
        "mode_windows": "ip0s/ip0f in A (|Ip|), t0s/t0f in s; transition_conditions = "
        "entry conditions of the mode (assumption)",
        "segment_ids": "uuid5 of '<name>/segment/<segment name>', identical on every "
        "rerun; the PSPS may replace them",
        "overlay_of": '"" = the nominal segment active when the event fires',
        "exception_duration": "duration of an exception or STOP segment = its watchdog, "
        "or ramp + hold of its reference; 0 when the design gives neither",
    }
    return _struct({k: _str(v) for k, v in c.items()})


def _exit(transitions: list[dict], seg_uuid) -> dict | None:
    if not transitions:
        return None
    ev = next((t for t in transitions if t.get("event")), None)
    tm = next((t for t in transitions if t.get("time_after") is not None), None)
    d = {
        "type": _str("event" if ev else "time"),
        "event": _str(ev["event"] if ev else ""),
    }
    if ev:
        d["event_target"] = _str(seg_uuid(ev.get("to")))
    if tm:
        d["watchdog_s"] = _f32_units(float(tm["time_after"]), "s")
        d["watchdog_target"] = _str(seg_uuid(tm.get("to")))
    blend = max((float(t.get("blend_s") or 0.0) for t in transitions), default=0.0)
    if blend:
        d["blend_s"] = _f32_units(blend, "s")
    return _struct(d)


def _ip_ids(value: dict) -> list[tuple[str, str]]:
    """(catalogue id, name) of the ip_control refs of a setpoint's modes, in order."""
    out: list[tuple[str, str]] = []
    for m in value["modes"]["value"]:
        ref = m["value"]["ip_control_ref"]["value"]
        item = (ref["id"]["value"], ref["name"]["value"])
        if item not in out:
            out.append(item)
    return out or [("0", "unspecified (no MCLS mode in the design)")]


def _add_ip_and_pf56(
    value: dict, ip_node: dict, ids: list[tuple[str, str]], pf: dict, ext: list[str]
) -> None:
    """Put the Ip reference under every used ip_control id and add pf5/pf6 (in place)."""
    cat = value["ip_control"]["value"]
    for cid, cname in ids:
        if cid not in cat:
            cat[cid] = _struct({"id": _str(cid), "name": _str(cname)})
            _add(ext, f"segments/*/setpoints/*/properties/value/ip_control/{cid}")
        cat[cid]["value"]["parameters"] = _struct({"ip": ip_node})
    circuits = value["waveforms_by_circuit"]["value"]
    for c in EXTRA_CIRCUITS:
        circuits[c] = pf[c]


def _add(ext: list[str], pattern: str) -> None:
    if pattern not in ext:
        ext.append(pattern)


def _extended(
    dto: list,
    design: dict,
    unf: _Unfilled,
    used: set,
    gap_slots: tuple[int, ...],
    additional: dict | None,
) -> list:
    """The strict document plus the PDS additions (typed nodes); see the module docstring."""
    name = design["name"]
    ext_doc = copy.deepcopy(dto)
    root = ext_doc[1]["value"]
    segs_node = root["segments"]["value"]
    nominal = design["segments"]
    excs = _exceptions(design)
    stop = design.get("stop")
    known = {s["name"] for s in nominal} | {e["name"] for e in excs}
    if stop:
        known.add(stop["name"])

    def seg_uuid(n) -> str:
        return uid(name, "segment", n) if n in known else ""

    ext: list[str] = []
    seg_props = "segments/*/properties/"
    sp_value = "segments/*/setpoints/*/properties/value/"
    ext_used = set(used) | {IP_PATH}
    ext_used |= {COIL.format(k=COILS.index(c.upper()) + 1) for c in EXTRA_CIRCUITS}

    def pf56(seg) -> dict:
        out = {}
        for c in EXTRA_CIRCUITS:
            path = COIL.format(k=COILS.index(c.upper()) + 1)
            xy = _seg_wave(design, seg, path)
            if xy is None:
                unf.add(
                    f"waveforms_by_circuit.{c}",
                    PLACEHOLDER,
                    f"{PLACEHOLDER}, no design waveform '{quantity_name(path)}' "
                    "in this segment",
                    seg["name"],
                )
            out[c] = _wave_node(
                xy, "A", IMAS_TO_PCS_CURRENT_SIGN, seg["end"] - seg["start"]
            )
        return out

    # nominal segments: order, role, successor, exit, PSC id; Ip reference; pf5/pf6
    for k, seg in enumerate(nominal):
        sid = uid(name, "segment", seg["name"])
        pid = uid(name, "segment", seg["name"], "setpoint", "magnetics")
        props = segs_node[sid]["value"]["properties"]["value"]
        props["order"] = _node("int32", k + 1)
        props["role"] = _str(ROLE_NOMINAL)
        nxt = nominal[k + 1]["name"] if k + 1 < len(nominal) else None
        props["successor"] = _str(seg_uuid(nxt) if nxt else "")
        for f in ("order", "role", "successor"):
            _add(ext, seg_props + f)
        ex = _exit(seg["transitions"], seg_uuid)
        if ex:
            props["exit"] = ex
            _add(ext, seg_props + "exit")
        if seg.get("id") is not None:
            props["pcs_segment_id"] = _node("int32", int(seg["id"]))
            _add(ext, seg_props + "pcs_segment_id")
        value = segs_node[sid]["value"]["setpoints"]["value"][pid]["value"]
        value = value["properties"]["value"]["value"]["value"]
        ip_xy = _seg_wave(design, seg, IP_PATH)
        if ip_xy is None:
            unf.add(
                "ip_control.*.parameters.ip",
                PLACEHOLDER,
                f"{PLACEHOLDER}, no design waveform '{quantity_name(IP_PATH)}' "
                "in this segment",
                seg["name"],
            )
        ip = _wave_node(ip_xy, "A", IMAS_TO_PCS_CURRENT_SIGN, seg["end"] - seg["start"])
        _add_ip_and_pf56(value, ip, _ip_ids(value), pf56(seg), ext)
    if nominal:
        _add(ext, sp_value + "ip_control/*/parameters")
        for c in EXTRA_CIRCUITS:
            _add(ext, sp_value + f"waveforms_by_circuit/{c}")

    # exception segments (and STOP) as additional segments; each carries one
    # Magnetics setpoint (the GUI rejects an empty setpoints object) whose modes
    # are those of the LAST nominal segment (assumption), every waveform a
    # placeholder except the exception's own Ip trajectory when the design has one
    only = seg_uuid(nominal[0]["name"]) if len(nominal) == 1 else ""
    parent = nominal[-1] if nominal else {"name": "", "modes": {}}
    inherited = ", ".join(parent["modes"]) or DEFAULT_MODE
    inherit_txt = (
        f"modes inherited from nominal segment '{parent['name']}' ({inherited}; "
        "whole-segment window, Ip window 0)"
    )

    def pseudo_setpoint(seg_name: str, dur: float, ip_xy) -> dict:
        pid = uid(name, "segment", seg_name, "setpoint", "magnetics")
        pseudo = {
            "name": seg_name,
            "start": 0.0,
            "end": float(dur),
            "modes": {m: {} for m in parent["modes"]},
            "transitions": [],
            "overlay": {},
        }
        pdesign = dict(design, waveforms={}, segments=[pseudo])
        value = _setpoint_value(pdesign, pseudo, 0, _Unfilled(), set(), gap_slots)
        ip = _waveform(*ip_xy, "A") if ip_xy else _placeholder(dur, "A")
        pf = {c: _placeholder(dur, "A") for c in EXTRA_CIRCUITS}
        _add_ip_and_pf56(value["value"], ip, _ip_ids(value["value"]), pf, [])
        return {pid: _setpoint(pid, value)}

    order = len(nominal)
    for e in excs:
        order += 1
        sid = uid(name, "segment", e["name"])
        dur = e["timeout_s"]
        if dur is None:
            dur = e["ip"][0][-1] if e["ip"] else 0.0
        props = {
            "id": _str(sid, {"id": True}),
            "name": _str(e["name"]),
            "duration": _node(
                "float64", _clean_time(dur), {"range": dict(DURATION_RANGE)}
            ),
            "order": _node("int32", order),
            "role": _str(ROLE_EXCEPTION),
            "successor": _str(""),
        }
        trans = []
        if e["recovery"] and e["on"]:
            trans.append({"event": f"{e['on']} released", "to": None})
        if e["then"] is not None and e["timeout_s"] is not None:
            trans.append({"to": e["then"], "time_after": e["timeout_s"]})
        elif e["then"] is not None:
            trans.append({"to": e["then"]})
        ex = _exit(trans, seg_uuid)
        if ex:
            if "watchdog_target" not in ex["value"] and e["then"] is not None:
                ex["value"]["watchdog_target"] = _str(seg_uuid(e["then"]))
            props["exit"] = ex
        if e["pcs_id"] is not None:
            props["pcs_segment_id"] = _node("int32", int(e["pcs_id"]))
        if e["kind"] in ("soft", "hard"):
            props["kind"] = _str(e["kind"])
        if e["kind"] == "soft":
            props["overlay_of"] = _str(only)
        if e.get("action"):
            props["action"] = _str(e["action"])
        setpoints = pseudo_setpoint(e["name"], dur, e["ip"])
        if e["ip"]:
            unf.add(
                "exception segment setpoint (all but ip_control.*.parameters.ip)",
                PLACEHOLDER,
                f"{PLACEHOLDER} for every waveform and one placeholder point: an "
                f"exception segment carries only its Ip trajectory; {inherit_txt}",
                e["name"],
            )
        else:
            unf.add(
                "exception segment setpoint (incl. ip_control.*.parameters.ip)",
                PLACEHOLDER,
                f"{PLACEHOLDER} for every waveform, the Ip reference included, and "
                "one placeholder point: this exception segment has no Ip trajectory "
                "in the design (the GUI rejects an empty setpoints object); "
                f"{inherit_txt}",
                e["name"],
            )
        segs_node[sid] = _struct(
            {"properties": _struct(props), "setpoints": _struct(setpoints)}
        )
        _add(ext, f"segments/{sid}")
    if stop:
        order += 1
        sid = uid(name, "segment", stop["name"])
        props = {
            "id": _str(sid, {"id": True}),
            "name": _str(stop["name"]),
            "duration": _node("float64", 0.0, {"range": dict(DURATION_RANGE)}),
            "order": _node("int32", order),
            "role": _str(ROLE_STOP),
            "successor": _str(""),
        }
        if stop.get("id") is not None:
            props["pcs_segment_id"] = _node("int32", int(stop["id"]))
        setpoints = pseudo_setpoint(stop["name"], 0.0, None)
        unf.add(
            "STOP segment setpoint",
            PLACEHOLDER,
            "STOP carries a placeholder setpoint: zero-length placeholders (xValues "
            "[0, 0]), one placeholder point, inherited modes; the GUI rejects an "
            f"empty setpoints object; {inherit_txt}",
            stop["name"],
        )
        segs_node[sid] = _struct(
            {"properties": _struct(props), "setpoints": _struct(setpoints)}
        )
        _add(ext, f"segments/{sid}")

    # schedule-level additions
    pp = root["properties"]["value"]
    targets: dict[str, str] = {}
    for s in nominal:
        for t in s["transitions"]:
            if t.get("event"):
                targets.setdefault(t["event"], t.get("to"))
    for e in excs:
        if e["on"]:
            targets.setdefault(e["on"], e["name"])
    # the PSPS parser rejects an empty list: an empty collection is not written
    events = _event_nodes(_events(design), targets, seg_uuid, unf)
    if events:
        pp["events"] = _list(events)
    pp["conventions"] = _conventions(design, gap_slots)
    unfilled = [
        _struct(
            {
                "field": _str(u["field"]),
                "reason": _str(u["reason"]),
                "where": _str("; ".join(u["where"])),
            }
        )
        for u in unf.as_list()
    ]
    if unfilled:
        pp["unfilled"] = _list(unfilled)
    add: dict = {}
    if nominal:
        add["design_start_s"] = _node("float64", float(nominal[0]["start"]))
        add["design_start_s"]["display"] = {"units": "s"}
    # waveforms and scalars without a slot: a struct keyed <segment>__<quantity>
    # (scalars: <quantity>), not a list: their elements differ in array length and
    # value type, which the PSPS parser rejects in a list (2026-11-16)
    no_slot: list[tuple[str, dict]] = []
    for seg in nominal:
        paths = list(design["waveforms"]) + [
            p for p in seg.get("overlay", {}) if p not in design["waveforms"]
        ]
        for path in paths:
            if path in ext_used:
                continue
            xy = _seg_wave(design, seg, path)
            if xy is None:
                continue
            sign = IMAS_TO_PCS_CURRENT_SIGN if _is_current(path) else 1
            no_slot.append(
                (
                    member_key(seg["name"], quantity_name(path)),
                    _struct(
                        {
                            "quantity": _str(quantity_name(path)),
                            "segment": _str(uid(name, "segment", seg["name"])),
                            "waveform": _wave_node(xy, _units_of(path), sign),
                        }
                    ),
                )
            )
    if no_slot:
        add["waveforms_without_slot"] = _keyed_struct(no_slot)
    scalars = []
    for path, v in (design.get("scalars") or {}).items():
        node = (
            _typed(v)
            if isinstance(v, bool | int | float | str)
            else _str(json.dumps(v))
        )
        if node["type"] == "float32" and _units_of(path):
            node["display"] = {"units": _units_of(path)}
        scalars.append(
            (
                member_key(quantity_name(path)),
                _struct({"quantity": _str(quantity_name(path)), "value": node}),
            )
        )
    if scalars:
        add["scalars_without_slot"] = _keyed_struct(scalars)
    kc = _kcurr((additional or {}).get("kcurr"))
    if kc:
        add["kcurr"] = kc
    if design.get("sl_editable"):
        add["editable_by"] = _struct(
            {
                role: _list([_struct({"field": _str(x)}) for x in items])
                for role, items in design["sl_editable"].items()
                if items
            }
        )
    add["mcls_field_map"] = _struct({k: _str(v) for k, v in MCLS_MAP.items()})
    pp["pds_additional"] = _struct(add)
    for f in ("events", "conventions", "unfilled", "pds_additional", "extensions"):
        if f in pp or f == "extensions":
            _add(ext, "properties/" + f)
    pp["extensions"] = _list([_struct({"path": _str(p)}) for p in ext])
    return ext_doc


def _remove(node: dict, parts: list[str]) -> None:
    """Delete the struct members matching a path pattern ('*' = any key) below node."""
    if node.get("type") != "struct":
        return
    kids = node["value"]
    for key in list(kids) if parts[0] == "*" else [parts[0]]:
        if key not in kids:
            continue
        if len(parts) == 1:
            del kids[key]
        else:
            _remove(kids[key], parts[1:])


def strip_extensions(doc: list) -> list:
    """Copy of an extended document without the paths of its properties.extensions."""
    out = copy.deepcopy(doc)
    root = out[1]
    ext = root["value"]["properties"]["value"]["extensions"]["value"]
    for pattern in [p["value"]["path"]["value"] for p in ext]:
        _remove(root, pattern.split("/"))
    return out


def build_dto(
    design: dict,
    additional: dict | None = None,
    gap_slots: Sequence[int] = PSPS_GAP_SLOTS,
) -> tuple[list, list]:
    """Return (strict document, extended document).

    ``additional``: optional run blocks for the extended file; key ``kcurr`` = the
    KCURR PARAM block of make_psc_psps_dataset.py (written to
    ``properties.pds_additional.kcurr`` without provenance). ``gap_slots``: PDS gap
    index k for the DTO gap slots gap01..gap06 (default ``PSPS_GAP_SLOTS``).
    """
    gap_slots = _gap_slots(gap_slots)
    unf = _Unfilled()
    used: set[str] = set()
    dto = _strict(design, unf, used, gap_slots)
    return dto, _extended(dto, design, unf, used, gap_slots, additional)


# --------------------------------------------------------------------------- output
def _compact(text: str) -> str:
    """Numeric arrays on one line (extended file only; the strict file keeps the mock's layout)."""
    return re.sub(
        r"\[\s+([-+0-9.eE,\s]+?)\s+\]",
        lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]",
        text,
    )


def write_psps_dto(
    design: dict,
    out_dir,
    additional: dict | None = None,
    gap_slots: Sequence[int] = PSPS_GAP_SLOTS,
) -> tuple[Path, Path]:
    """Write <name>_psps_dto.json and <name>_psps_dto_extended.json (indent 2 as the mock).

    ``gap_slots``: PDS gap index k for the gap slots gap01..gap06 (see ``build_dto``).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dto, extended = build_dto(design, additional, gap_slots)
    p1 = out / f"{design['name']}_psps_dto.json"
    p2 = out / f"{design['name']}_psps_dto_extended.json"
    p1.write_text(json.dumps(dto, indent=2) + "\n", encoding="utf-8")
    p2.write_text(_compact(json.dumps(extended, indent=2)) + "\n", encoding="utf-8")
    return p1, p2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="two-file set -> psps-dto/v1.0/JSON (strict + extended)"
    )
    ap.add_argument("--waveforms", required=True, help="<name>_waveforms.yaml")
    ap.add_argument("--segments", required=True, help="<name>_segments.yaml")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument(
        "--name", default=None, help="output stem (default from --waveforms)"
    )
    a = ap.parse_args(argv)
    for p in write_psps_dto(
        design_from_two_file_paths(a.waveforms, a.segments, a.name), a.out_dir
    ):
        print("PSPS DTO   :", p)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
