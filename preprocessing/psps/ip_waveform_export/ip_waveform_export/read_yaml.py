"""Read the Waveform-Editor-style YAML input (format 0).

Layout (see README, the ``segments:`` and ``signals:`` blocks are a PROPOSAL)::

    globals: {dd_version: 4.0.0, pulse: ..., comment: ..., name: ...,
              convention: minus_ip,             # optional, default minus_ip (D11)
              time_origin: plasma_initiation,   # optional, the only value implemented (D10)
              time_offset_s: 0.0}               # optional, added at export
    <any section>:
      pulse_schedule/flux_control/ip/reference:
        - {convention: minus_ip, time: [...], value: [...]}   # convention optional
    segments:
      - {name: ramp-up, id: 0, start: 0.0, end: 70.0, wd_target: flat-top}
      - ...
      - {name: STOP, id: 99}
    signals:            # optional, IDS path -> PCS signal name
      pulse_schedule/flux_control/ip/reference: Ipl_ref
    exceptions: {...}   # optional, PROPOSAL, see export_refgen_eh_example
    events: {...}               # optional, PROPOSAL (PSC-3), see export_psc_config
    exception_handling: {...}   # optional, PROPOSAL (PSC-3), see export_psc_config
    psc: {...}                  # optional, PROPOSAL (PSC-3), see export_psc_config

Sign convention (decision D11): with ``convention: minus_ip`` (default for the
designer file) the YAML values are -Ip, i.e. positive for ITER, and must be
>= 0; with ``convention: imas`` they are already in the IMAS sign (ITER < 0).
The model always holds the IMAS sign.
"""

from __future__ import annotations

import math
from pathlib import Path

import yaml

from .model import (
    CONVENTION_MINUS_IP,
    CONVENTIONS,
    DEFAULT_CONVENTION,
    DEFAULT_SIGNALS,
    DEFAULT_STOP_ID,
    IMAS_TO_MINUS_IP_SIGN,
    IP_PATH_DD3,
    IP_PATH_DD4,
    STOP_NAME,
    TIME_ORIGIN_PLASMA_INITIATION,
    TIME_ORIGINS_RESERVED,
    IpWaveform,
    PulseDesign,
    Segment,
    ValidationError,
)

RESERVED_KEYS = {
    "globals",
    "segments",
    "signals",
    "exceptions",
    "events",
    "exception_handling",
    "psc",
}
TENDENCY_KEYS = {"time", "value", "convention"}
IP_PATHS = (IP_PATH_DD4, IP_PATH_DD3)


def _find_entry(doc: dict, path: str):
    hits = []
    for section, content in doc.items():
        if section in RESERVED_KEYS or not isinstance(content, dict):
            continue
        if path in content:
            hits.append((section, content[path]))
    if len(hits) > 1:
        raise ValidationError(
            [f"{path} defined in several sections: {[h[0] for h in hits]}"]
        )
    return hits[0][1] if hits else None


def _parse_tendency(path: str, entry) -> tuple[list[float], list[float], str | None]:
    if not isinstance(entry, list) or len(entry) != 1 or not isinstance(entry[0], dict):
        raise ValidationError(
            [
                f"{path}: expected a list with ONE piecewise-linear tendency {{time: [...], value: [...]}}"
            ]
        )
    tend = entry[0]
    if "time" not in tend or "value" not in tend or set(tend) - TENDENCY_KEYS:
        raise ValidationError(
            [
                (
                    f"{path}: only the {{time, value}} tendency (plus an optional 'convention') "
                    f"is supported (got keys {sorted(tend)})"
                )
            ]
        )
    conv = tend.get("convention")
    return (
        [float(x) for x in tend["time"]],
        [float(x) for x in tend["value"]],
        None if conv is None else str(conv),
    )


def _resolve_convention(path: str, entry_conv: str | None, glob_conv) -> str:
    glob_conv = None if glob_conv is None else str(glob_conv)
    if entry_conv and glob_conv and entry_conv != glob_conv:
        raise ValidationError(
            [
                (
                    f"{path}: convention {entry_conv!r} on the entry disagrees with "
                    f"globals.convention {glob_conv!r}"
                )
            ]
        )
    conv = entry_conv or glob_conv or DEFAULT_CONVENTION
    if conv not in CONVENTIONS:
        raise ValidationError(
            [
                f"{path}: convention {conv!r} unknown, expected one of {list(CONVENTIONS)}"
            ]
        )
    return conv


def _to_imas(path: str, t: list[float], v: list[float], conv: str) -> list[float]:
    """Convert the YAML values to the IMAS sign; check the minus_ip sign rule."""
    if conv != CONVENTION_MINUS_IP:
        return v
    bad = [(ti, vi) for ti, vi in zip(t, v) if vi < 0]
    if bad:
        shown = ", ".join(f"t={ti:g} s: {vi:g}" for ti, vi in bad[:5])
        more = f" (+{len(bad) - 5} more)" if len(bad) > 5 else ""
        raise ValidationError(
            [
                (
                    f"{path}: convention 'minus_ip' expects -Ip, i.e. values >= 0 for ITER "
                    f"(the Session Leader edits -Ip); negative values found at {shown}{more}. "
                    "If the file holds IMAS-sign values (ITER Ip < 0), set 'convention: imas'."
                )
            ]
        )
    return [IMAS_TO_MINUS_IP_SIGN * x + 0.0 for x in v]


def _time_origin(glob: dict) -> tuple[str, float]:
    origin = str(glob.get("time_origin", TIME_ORIGIN_PLASMA_INITIATION))
    if origin in TIME_ORIGINS_RESERVED:
        raise ValidationError(
            [
                (
                    f"globals.time_origin {origin!r} is a reserved value, not implemented: "
                    "the offset between plasma initiation and this origin is a decision to "
                    f"take; use {TIME_ORIGIN_PLASMA_INITIATION!r} and globals.time_offset_s"
                )
            ]
        )
    if origin != TIME_ORIGIN_PLASMA_INITIATION:
        raise ValidationError(
            [
                (
                    f"globals.time_origin {origin!r} unknown; implemented: "
                    f"{TIME_ORIGIN_PLASMA_INITIATION!r}, reserved: {list(TIME_ORIGINS_RESERVED)}"
                )
            ]
        )
    offset = float(glob.get("time_offset_s", 0.0))
    if not math.isfinite(offset):
        raise ValidationError(["globals.time_offset_s must be finite"])
    return origin, offset


def _parse_segments(raw, stop_id: int) -> list[Segment]:
    if not isinstance(raw, list) or not raw:
        raise ValidationError(["'segments:' must be a non-empty list"])
    out: list[Segment] = []
    prev_end: float | None = None
    for i, s in enumerate(raw):
        if not isinstance(s, dict) or "name" not in s:
            raise ValidationError([f"segments[{i}]: needs at least a 'name'"])
        name = str(s["name"])
        if "id" in s:
            sid = int(s["id"])
        elif name == STOP_NAME:
            sid = stop_id
        else:
            raise ValidationError([f"segment {name!r}: missing 'id'"])
        start = float(s["start"]) if "start" in s else prev_end
        if start is None:
            raise ValidationError(
                [f"segment {name!r}: the first segment needs 'start'"]
            )
        if "end" in s and "duration" in s:
            end = float(s["end"])
            if abs(end - start - float(s["duration"])) > 1e-9:
                raise ValidationError([f"segment {name!r}: end and duration disagree"])
        elif "end" in s:
            end = float(s["end"])
        elif "duration" in s:
            end = start + float(s["duration"])
        elif name == STOP_NAME:
            end = start
        else:
            raise ValidationError([f"segment {name!r}: give 'end' or 'duration'"])
        wd = s.get("wd_target")
        out.append(Segment(name, sid, start, end, None if wd is None else str(wd)))
        prev_end = end
    # default wd_target = next segment name (STOP keeps None)
    filled = []
    for a, b in zip(out, [*out[1:], None]):
        if a.wd_target is None and b is not None:
            a = Segment(a.name, a.id, a.start, a.end, b.name)
        filled.append(a)
    return filled


def load_design(
    path: str | Path, stop_id: int | None = None, validate: bool = True
) -> PulseDesign:
    """Parse and (by default) validate the YAML file.

    ``stop_id`` overrides globals.stop_id; ``validate=False`` skips the structural
    rules of ``model.validate`` (used by ``validate.check``, which reports them as
    a list instead of raising).
    """
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict):
        raise ValidationError([f"{path}: top level must be a mapping"])
    glob = dict(doc.get("globals") or {})
    if "dd_version" in glob:
        glob["dd_version"] = str(glob["dd_version"])
    sid = stop_id if stop_id is not None else int(glob.get("stop_id", DEFAULT_STOP_ID))

    signals = dict(doc.get("signals") or DEFAULT_SIGNALS)
    unsupported = [k for k in signals if k not in IP_PATHS]
    if unsupported:
        raise ValidationError(
            [
                f"signals: only the Ip reference is supported by this prototype (got {unsupported})"
            ]
        )
    if len(signals) != 1:
        raise ValidationError(["signals: exactly one Ip reference path expected"])
    ids_path, signal_name = next(iter(signals.items()))

    entry = _find_entry(doc, ids_path)
    if entry is None:
        raise ValidationError([f"{path}: no entry {ids_path}"])
    t, v, entry_conv = _parse_tendency(ids_path, entry)
    conv = _resolve_convention(ids_path, entry_conv, glob.get("convention"))
    v = _to_imas(ids_path, t, v, conv)
    wf = IpWaveform(time=t, value=v, ids_path=ids_path, signal_name=str(signal_name))
    origin, offset = _time_origin(glob)
    exceptions = doc.get("exceptions")
    if exceptions is not None and not isinstance(exceptions, dict):
        raise ValidationError(["'exceptions:' must be a mapping (PROPOSAL block)"])
    psc_blocks = {}
    for key in ("events", "exception_handling", "psc"):
        val = doc.get(key)
        if val is not None and not isinstance(val, dict):
            raise ValidationError([f"'{key}:' must be a mapping (PROPOSAL block)"])
        psc_blocks[key] = val

    design = PulseDesign(
        waveform=wf,
        segments=_parse_segments(doc.get("segments"), sid),
        globals=glob,
        name=str(glob.get("name", path.stem)),
        stop_id=sid,
        convention=conv,
        time_origin=origin,
        time_offset_s=offset,
        exceptions=exceptions,
        **psc_blocks,
    )
    if validate:
        design.validate()
    return design
