"""Lossless, human-readable "compact YAML" view of a ``psps-dto/v1.0/JSON`` document.

A READING VIEW, not a PSPS format: the PSPS only reads and writes the JSON. The
compact file has three top-level keys, in this order:

``pulse``
    the content: every typed node ``{type, value, ...}`` replaced by its value
    (structs -> mappings, lists/arrays -> sequences); float32 values written as the
    shortest decimal that reads back to the same float32 (``15.6``, not
    ``15.600000381469727``); catalogues (``shape_control``, ``ip_control``,
    ``vs_control``) identical in every setpoint (two setpoints or more) written once
    under ``pulse.catalogues`` and replaced in each setpoint by the string
    ``shared``; a ``waveforms_by_circuit`` whose circuits all share one ``xValues``
    written as ``{t: [...], <circuit>: [...yValues...], ...}``.
``units``
    informational table, display units per generic path (ignored when reading).
``_schema``
    what was removed, for the round trip: ``header`` (the document's first element,
    ``{"encoding": ...}``), ``patterns`` (per generic path, UUID keys -> ``*`` and list
    indices -> ``[]``: type, element_type, display, constraints and, when the key
    order is not ``type, element_type, value, display, constraints``, ``_order``),
    ``exceptions`` (per concrete path, a node differing from its pattern),
    ``raw`` (concrete paths of nodes that could not be unwrapped; their typed form is
    kept verbatim in ``pulse``), ``float64_values`` (concrete paths of float32 nodes
    holding values that are not exact float32: written and read back unchanged),
    ``shared_catalogues``, ``collapsed_waveforms`` (paths written in the ``t`` form)
    and ``json_layout`` (the detected byte layout of the
    source JSON, so that ``to-json`` can regenerate it byte for byte).

``to_compact``/``from_compact`` are exact inverses (``json.dumps`` and ``==``); the
``to-yaml`` command checks the round trip through the YAML text and refuses to write
when it is not exact.

CLI (run from preprocessing/psps/ip_waveform_export)::

    python -m ip_waveform_export.psps_dto_compact to-yaml IN.json [OUT.yaml]
    python -m ip_waveform_export.psps_dto_compact to-json IN.yaml [OUT.json]
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

import numpy as np
import yaml

from .export_psps_dto import _compact as _one_line_arrays

ROOT = "pulse"
CANON = ("type", "element_type", "value", "display", "constraints")
CATALOGUES = ("shape_control", "ip_control", "vs_control")
SHARED = "shared"
WAVEFORMS = "waveforms_by_circuit"
T_KEY = "t"
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
PLAIN_KEY = re.compile(r"[A-Za-z0-9_\-]+")
SETPOINT_PREFIX = f"{ROOT}.segments.*.setpoints.*.properties.value."


class CompactError(ValueError):
    """The document cannot be represented or the round trip is not exact."""


# --------------------------------------------------------------------------- paths
def _key(k: str) -> str:
    return k if PLAIN_KEY.fullmatch(k) else json.dumps(k, ensure_ascii=False)


def _child(path: str, gpath: str, k: str) -> tuple[str, str]:
    return f"{path}.{_key(k)}", f"{gpath}.{'*' if UUID_RE.fullmatch(k) else _key(k)}"


# --------------------------------------------------------------------------- floats
def _is_f32_field(attrs: dict) -> bool:
    return attrs.get("type") == "float32" or attrs.get("element_type") == "float32"


def _f32_exact(x: float) -> bool:
    return float(np.float32(x)) == x


def _short(x: float) -> float:
    """Shortest decimal of an exact float32 value, as a float that reads back exactly."""
    y = float(str(np.float32(x)))
    return y if float(np.float32(y)) == x else x


def _f32_values(v, f):
    """Apply f to every float of a scalar or a flat list (ints, bools untouched)."""
    if isinstance(v, float):
        return f(v)
    if isinstance(v, list):
        return [f(e) if isinstance(e, float) else e for e in v]
    return v


def _all_f32(v) -> bool:
    if isinstance(v, float):
        return _f32_exact(v)
    if isinstance(v, list):
        return all(_f32_exact(e) for e in v if isinstance(e, float))
    return True


# --------------------------------------------------------------------------- unwrap
def _well_formed(n) -> bool:
    if not (isinstance(n, dict) and "type" in n and "value" in n):
        return False
    if "_order" in n:
        return False
    v = n["value"]
    if n["type"] == "struct":
        return isinstance(v, dict)
    if n["type"] == "list":
        return isinstance(v, list)
    if isinstance(v, dict):
        return False
    if isinstance(v, list):
        return all(not isinstance(e, dict | list) for e in v)
    return True


def _attrs(n: dict) -> dict:
    a = {k: v for k, v in n.items() if k != "value"}
    keys = list(n)
    known = [k for k in keys if k in CANON]
    if any(k not in CANON for k in keys) or known != [k for k in CANON if k in keys]:
        a["_order"] = keys
    return a


def _unwrap(n, path: str, gpath: str, sch: dict, seen: dict):
    if not _well_formed(n):
        sch["raw"].append(path)
        return copy.deepcopy(n)
    a = _attrs(n)
    seen.setdefault(gpath, []).append((path, a))
    v = n["value"]
    if n["type"] == "struct":
        out = {}
        for k, c in v.items():
            p, g = _child(path, gpath, k)
            out[k] = _unwrap(c, p, g, sch, seen)
        return out
    if n["type"] == "list":
        return [
            _unwrap(c, f"{path}[{i}]", f"{gpath}[]", sch, seen) for i, c in enumerate(v)
        ]
    v = copy.deepcopy(v)
    if _is_f32_field(a):
        if _all_f32(v):
            return _f32_values(v, _short)
        sch["float64_values"].append(path)
    return v


def _patterns(seen: dict) -> tuple[dict, dict]:
    patterns, exceptions = {}, {}
    for g, items in seen.items():
        sigs = [json.dumps(a) for _, a in items]
        best = max(dict.fromkeys(sigs), key=sigs.count)  # most common, first on tie
        patterns[g] = json.loads(best)
        for (p, a), s in zip(items, sigs, strict=True):
            if s != best:
                exceptions[p] = a
    return patterns, exceptions


# --------------------------------------------------------------------------- transforms
def _setpoint_values(pulse: dict) -> list[dict]:
    out = []
    segs = pulse.get("segments")
    for seg in segs.values() if isinstance(segs, dict) else []:
        sps = seg.get("setpoints") if isinstance(seg, dict) else None
        for sp in sps.values() if isinstance(sps, dict) else []:
            v = sp.get("properties", {}).get("value") if isinstance(sp, dict) else None
            if isinstance(v, dict):
                out.append(v)
    return out


def _share_catalogues(pulse: dict) -> list[str]:
    sps = _setpoint_values(pulse)
    if len(sps) < 2 or "catalogues" in pulse:
        return []
    shared = {}
    for name in CATALOGUES:
        vals = [sp.get(name) for sp in sps]
        if all(isinstance(x, dict) for x in vals) and all(
            json.dumps(x) == json.dumps(vals[0]) for x in vals
        ):
            shared[name] = vals[0]
    for sp in sps:
        for name in shared:
            sp[name] = SHARED
    if shared:
        pulse["catalogues"] = shared
    return list(shared)


def _unshare_catalogues(pulse: dict, names: list[str]) -> None:
    if not names:
        return
    cat = pulse.pop("catalogues")
    for sp in _setpoint_values(pulse):
        for name in names:
            if sp.get(name) != SHARED:
                raise CompactError(f"setpoint without '{name}: {SHARED}' marker")
            sp[name] = copy.deepcopy(cat[name])


def _collapse_waveforms(obj, path: str, raw: set, done: list) -> None:
    """{c: {xValues: x, yValues: y}} -> {t: x, c: y} when every circuit shares x."""
    if path in raw:
        return
    if isinstance(obj, list):
        for i, e in enumerate(obj):
            _collapse_waveforms(e, f"{path}[{i}]", raw, done)
        return
    if not isinstance(obj, dict):
        return
    for k, v in obj.items():
        p = _child(path, path, k)[0]
        if k == WAVEFORMS and _collapsible(v) and not _has_raw(p, raw):
            x = next(iter(v.values()))["xValues"]
            obj[k] = {T_KEY: x, **{c: w["yValues"] for c, w in v.items()}}
            done.append(p)
        else:
            _collapse_waveforms(v, p, raw, done)


def _has_raw(path: str, raw: set) -> bool:
    return any(r == path or r.startswith((path + ".", path + "[")) for r in raw)


def _collapsible(v) -> bool:
    if not isinstance(v, dict) or not v or T_KEY in v:
        return False
    ws = list(v.values())
    if not all(isinstance(w, dict) and list(w) == ["xValues", "yValues"] for w in ws):
        return False
    x0 = json.dumps(ws[0]["xValues"])
    return isinstance(ws[0]["xValues"], list) and all(
        json.dumps(w["xValues"]) == x0 for w in ws
    )


def _get(obj, path: str):
    """Value at a concrete path (as built by _child / [i]) inside the pulse tree."""
    for tok in re.findall(
        r'\.(?:"(?:[^"\\]|\\.)*"|[^.\[]+)|\[\d+\]', path[len(ROOT) :]
    ):
        if tok.startswith("["):
            obj = obj[int(tok[1:-1])]
        else:
            k = tok[1:]
            obj = obj[json.loads(k) if k.startswith('"') else k]
    return obj


def _expand_waveforms(pulse: dict, paths: list[str]) -> None:
    for p in paths:
        parent, key = p.rsplit(".", 1)
        holder = pulse if parent == ROOT else _get(pulse, parent)
        v = holder[key]
        if not (isinstance(v, dict) and isinstance(v.get(T_KEY), list)):
            raise CompactError(f"{p}: collapsed waveforms expected")
        x = v[T_KEY]
        holder[key] = {
            c: {"xValues": copy.deepcopy(x), "yValues": y}
            for c, y in v.items()
            if c != T_KEY
        }


# --------------------------------------------------------------------------- units
def _units_table(patterns: dict, exceptions: dict) -> dict:
    gp_units: dict[str, list[str]] = {}
    items = list(patterns.items())
    for p, a in exceptions.items():
        g = re.sub(r"\[\d+\]", "[]", p)
        g = ".".join("*" if UUID_RE.fullmatch(s) else s for s in g.split("."))
        items.append((g, a))
    for g, a in items:
        d = a.get("display")
        if isinstance(d, dict) and isinstance(d.get("units"), str):
            short = g.replace(SETPOINT_PREFIX, "setpoint.", 1)
            short = short.removeprefix(ROOT + ".")
            short = re.sub(rf"({WAVEFORMS})\.[^.]+\.", r"\1.*.", short)
            us = gp_units.setdefault(short, [])
            if d["units"] not in us:
                us.append(d["units"])
    return {k: ", ".join(v) for k, v in gp_units.items()}


# --------------------------------------------------------------------------- API
def to_compact(dto: list, json_layout: dict | None = None) -> dict:
    """psps-dto document (``[header, root node]``) -> compact dict (pulse, units, _schema)."""
    if not (isinstance(dto, list) and len(dto) == 2 and isinstance(dto[0], dict)):
        raise CompactError("expected a psps-dto document [header, root node]")
    sch: dict = {"raw": [], "float64_values": []}
    seen: dict = {}
    pulse = _unwrap(dto[1], ROOT, ROOT, sch, seen)
    if ROOT in sch["raw"] or not isinstance(pulse, dict):
        raise CompactError("the root node is not a typed struct")
    patterns, exceptions = _patterns(seen)
    collapsed: list[str] = []
    _collapse_waveforms(pulse, ROOT, set(sch["raw"]), collapsed)
    shared = _share_catalogues(pulse)
    schema = {
        "header": copy.deepcopy(dto[0]),
        "json_layout": json_layout,
        "shared_catalogues": shared,
        "collapsed_waveforms": collapsed,
        "raw": sch["raw"],
        "float64_values": sch["float64_values"],
        "patterns": patterns,
        "exceptions": exceptions,
    }
    return {
        "pulse": pulse,
        "units": _units_table(patterns, exceptions),
        "_schema": schema,
    }


def _wrap(c, path: str, gpath: str, sch: dict, raw: set, f64: set):
    if path in raw:
        return copy.deepcopy(c)
    a = sch["exceptions"].get(path) or sch["patterns"].get(gpath)
    if a is None:
        raise CompactError(f"no schema for {path}")
    t = a["type"]
    if t == "struct":
        if not isinstance(c, dict):
            raise CompactError(f"{path}: struct expected")
        v = {}
        for k, x in c.items():
            p, g = _child(path, gpath, k)
            v[k] = _wrap(x, p, g, sch, raw, f64)
    elif t == "list":
        if not isinstance(c, list):
            raise CompactError(f"{path}: list expected")
        v = [
            _wrap(x, f"{path}[{i}]", f"{gpath}[]", sch, raw, f64)
            for i, x in enumerate(c)
        ]
    else:
        v = copy.deepcopy(c)
        if _is_f32_field(a) and path not in f64:
            v = _f32_values(v, lambda x: float(np.float32(x)))
    order = a.get("_order") or [k for k in CANON if k in a or k == "value"]
    return {k: (v if k == "value" else copy.deepcopy(a[k])) for k in order}


def from_compact(compact: dict) -> list:
    """Compact dict -> the psps-dto document (exact inverse of ``to_compact``)."""
    sch = compact["_schema"]
    pulse = copy.deepcopy(compact["pulse"])
    _unshare_catalogues(pulse, sch.get("shared_catalogues") or [])
    _expand_waveforms(pulse, sch.get("collapsed_waveforms") or [])
    raw, f64 = set(sch.get("raw") or []), set(sch.get("float64_values") or [])
    sch = {"patterns": sch["patterns"], "exceptions": sch.get("exceptions") or {}}
    return [
        copy.deepcopy(compact["_schema"]["header"]),
        _wrap(pulse, ROOT, ROOT, sch, raw, f64),
    ]


# --------------------------------------------------------------------------- YAML
class _Flow(dict):
    """Mapping written in flow style on one line (schema entries)."""


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def _repr_list(d: yaml.SafeDumper, data: list):
    flow = all(not isinstance(e, dict | list) for e in data)
    return d.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=flow)


def _repr_flow(d: yaml.SafeDumper, data: dict):
    return d.represent_mapping("tag:yaml.org,2002:map", data, flow_style=True)


_Dumper.add_representer(list, _repr_list)
_Dumper.add_representer(_Flow, _repr_flow)


def _for_yaml(compact: dict) -> dict:
    out = dict(compact)
    sch = dict(compact["_schema"])
    sch["patterns"] = {k: _Flow(v) for k, v in sch["patterns"].items()}
    sch["exceptions"] = {k: _Flow(v) for k, v in sch["exceptions"].items()}
    if sch["json_layout"] is not None:
        sch["json_layout"] = _Flow(sch["json_layout"])
    out["_schema"] = sch
    return out


def _names(pulse: dict) -> dict[str, str]:
    """UUID key -> name of the segment/setpoint it holds (for YAML comments)."""
    names = {}
    segs = pulse.get("segments")
    for k, seg in segs.items() if isinstance(segs, dict) else []:
        if not isinstance(seg, dict):
            continue
        n = (
            seg.get("properties", {}).get("name")
            if isinstance(seg.get("properties"), dict)
            else None
        )
        if isinstance(n, str):
            names[k] = "segment " + n
        sps = seg.get("setpoints")
        for sk, sp in sps.items() if isinstance(sps, dict) else []:
            pr = sp.get("properties") if isinstance(sp, dict) else None
            if isinstance(pr, dict) and isinstance(pr.get("name"), str):
                names[sk] = "setpoint " + pr["name"]
    return names


def compact_yaml_text(compact: dict, source: str | None = None) -> str:
    body = yaml.dump(
        _for_yaml(compact),
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        width=10**9,
        default_flow_style=False,
    )
    names = _names(compact["pulse"])

    def comment(m: re.Match) -> str:
        name = names.get(m.group(2))
        if name is None:
            return m.group(0)
        return f"{m.group(0)}  # {' '.join(name.split())}"

    body = re.sub(
        rf"^(\s*)'?({UUID_RE.pattern})'?:$", comment, body, flags=re.MULTILINE
    )
    src = source or "a psps-dto/v1.0/JSON document"
    head = (
        f"# Reading view of {src} (psps-dto/v1.0/JSON), generated by psps_dto_compact; "
        "not a PSPS format.\n"
        "# Convert back with: python -m ip_waveform_export.psps_dto_compact to-json "
        "<this file>\n"
    )
    return head + body


def dump_compact_yaml(compact: dict, path, source: str | None = None) -> Path:
    p = Path(path)
    p.write_text(compact_yaml_text(compact, source), encoding="utf-8")
    return p


def load_compact_yaml(path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- JSON layout
def _render(obj, layout: dict) -> str:
    text = json.dumps(obj, indent=layout["indent"], ensure_ascii=layout["ensure_ascii"])
    if layout.get("arrays_one_line"):
        text = _one_line_arrays(text)
    return text + ("\n" if layout["newline"] else "")


def detect_json_layout(text: str, obj) -> dict | None:
    """The json.dumps parameters that reproduce text byte for byte, or None."""
    for indent in (2, 4, None, 1, 3, 0, "\t"):
        for ascii_ in (True, False):
            for one_line in (False, True):
                for nl in (False, True):
                    lay = {
                        "indent": indent,
                        "ensure_ascii": ascii_,
                        "arrays_one_line": one_line,
                        "newline": nl,
                    }
                    if _render(obj, lay) == text:
                        return lay
    return None


DEFAULT_LAYOUT = {
    "indent": 2,
    "ensure_ascii": False,
    "arrays_one_line": False,
    "newline": True,
}


def json_text(dto: list, layout: dict | None) -> str:
    return _render(dto, layout or DEFAULT_LAYOUT)


def check_round_trip(dto: list, compact: dict) -> None:
    """Raise CompactError unless from_compact(compact) reproduces dto exactly."""
    back = from_compact(compact)
    if json.dumps(back) != json.dumps(dto) or back != dto:
        raise CompactError("round trip is not exact")


# --------------------------------------------------------------------------- CLI
def _to_yaml(src: Path, out: Path | None) -> int:
    text = src.read_text(encoding="utf-8")
    dto = json.loads(text)
    layout = detect_json_layout(text, dto)
    compact = to_compact(dto, layout)
    check_round_trip(dto, compact)
    ytext = compact_yaml_text(compact, src.name)
    check_round_trip(dto, yaml.safe_load(ytext))
    if (
        layout is not None
        and json_text(from_compact(yaml.safe_load(ytext)), layout) != text
    ):
        raise CompactError("regenerated JSON is not byte-identical")
    out = out or src.with_name(src.stem + ".compact.yaml")
    out.write_text(ytext, encoding="utf-8")
    print("compact YAML:", out)
    print(
        "round trip  : exact; JSON bytes:",
        "identical" if layout else "layout not detected",
    )
    return 0


def _to_json(src: Path, out: Path | None) -> int:
    compact = load_compact_yaml(src)
    dto = from_compact(compact)
    out = out or src.with_name(src.stem + ".json")
    out.write_text(
        json_text(dto, compact["_schema"].get("json_layout")), encoding="utf-8"
    )
    print("psps-dto JSON:", out)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="psps-dto/v1.0/JSON <-> lossless compact YAML reading view"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser(
        "to-yaml", help="JSON -> <stem>.compact.yaml (round trip checked)"
    )
    a1.add_argument("input", type=Path)
    a1.add_argument("output", type=Path, nargs="?")
    a2 = sub.add_parser("to-json", help="compact YAML -> <stem>.json")
    a2.add_argument("input", type=Path)
    a2.add_argument("output", type=Path, nargs="?")
    a = ap.parse_args(argv)
    try:
        return (_to_yaml if a.cmd == "to-yaml" else _to_json)(a.input, a.output)
    except CompactError as e:
        print(f"psps_dto_compact: {e}; nothing written", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
