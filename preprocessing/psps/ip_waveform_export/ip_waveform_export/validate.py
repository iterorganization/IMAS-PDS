"""P5 seed: validation of the designer-level Ip data item before export.

Two families of checks, reported together as a list of ``Violation``:

* structure: monotonic time, segments contiguous / covering the waveform / ids
  unique / STOP last, ... -- the rules of ``model.validate`` (reused, not
  re-implemented);
* physics / operations limits read from a YAML limits file
  (``limits/ip_limits_example.yaml``): |Ip| maximum, |dIp/dt| maximum per linear
  piece, minimum flat-top duration. The example values are PLACEHOLDERS: the
  real limits must come from Operations (OLC).

This function is the seed of P5 of the PSPS-to-KCURR data-chain plan (the study notes, kept outside this repository),
intended to become a function registered in the PSPS CVVF (Configuration
Verification & Validation Framework; IDM 4F2JYS, and IDM 2PVHKE p.4).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from .model import PulseDesign, Segment, ValidationError, validate

TOOL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LIMITS = TOOL_DIR / "limits" / "ip_limits_example.yaml"
MA = 1.0e6


@dataclass(frozen=True)
class Limits:
    ip_abs_max: float | None = None  # A
    dip_dt_abs_max: float | None = None  # A/s
    flat_top_min_duration: float | None = None  # s
    flat_top_segment_names: tuple[str, ...] = ("flat-top",)
    status: str = "PLACEHOLDER"
    source: str = ""


@dataclass(frozen=True)
class Violation:
    rule: str
    message: str
    segment: str | None = None
    time: float | None = None  # s, designer time origin
    value: float | None = None
    limit: float | None = None

    def __str__(self) -> str:
        where = []
        if self.segment is not None:
            where.append(f"segment {self.segment!r}")
        if self.time is not None:
            where.append(f"t = {self.time:g} s")
        loc = f" [{', '.join(where)}]" if where else ""
        return f"{self.rule}{loc}: {self.message}"


def _limit_value(raw: dict, key: str) -> float | None:
    if key not in raw:
        return None
    entry = raw[key]
    val = entry.get("value") if isinstance(entry, dict) else entry
    return None if val is None else float(val)


def load_limits(path: str | Path = DEFAULT_LIMITS) -> Limits:
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    raw = doc.get("limits") or {}
    ip = _limit_value(raw, "ip_abs_max_MA")
    rate = _limit_value(raw, "dip_dt_abs_max_MA_per_s")
    names = raw.get("flat_top_segment_names", ["flat-top"])
    return Limits(
        ip_abs_max=None if ip is None else ip * MA,
        dip_dt_abs_max=None if rate is None else rate * MA,
        flat_top_min_duration=_limit_value(raw, "flat_top_min_duration_s"),
        flat_top_segment_names=tuple(str(n) for n in names),
        status=str(doc.get("status", "")),
        source=str(path),
    )


def segment_at(design: PulseDesign, t: float) -> Segment | None:
    """Timed segment containing ``t`` (start <= t < end; the last one includes its end)."""
    timed = design.timed_segments
    for s in timed:
        if s.start <= t < s.end:
            return s
    if timed and math.isclose(t, timed[-1].end):
        return timed[-1]
    return None


def _seg_name(design: PulseDesign, t: float) -> str | None:
    s = segment_at(design, t)
    return None if s is None else s.name


def check(design: PulseDesign, limits: Limits | None = None) -> list[Violation]:
    """Return every violation (empty list = valid). Never raises on a rule."""
    out: list[Violation] = []
    try:
        validate(design)
    except ValidationError as e:
        out += [Violation("structure", p) for p in e.problems]
    if limits is None:
        return out

    t, v = design.waveform.time, design.waveform.value
    if t.ndim != 1 or t.size != v.size or t.size < 2:
        return out
    if limits.ip_abs_max is not None:
        for ti, vi in zip(t, v):
            if abs(vi) > limits.ip_abs_max:
                out.append(
                    Violation(
                        "ip_abs_max",
                        f"|Ip| = {abs(vi) / MA:.4g} MA > {limits.ip_abs_max / MA:.4g} MA",
                        _seg_name(design, float(ti)),
                        float(ti),
                        float(abs(vi)),
                        limits.ip_abs_max,
                    )
                )
    if limits.dip_dt_abs_max is not None:
        dt = np.diff(t)
        with np.errstate(divide="ignore", invalid="ignore"):
            rate = np.diff(v) / dt
        for i in np.nonzero(np.abs(rate) > limits.dip_dt_abs_max)[0]:
            t0, t1 = float(t[i]), float(t[i + 1])
            out.append(
                Violation(
                    "dip_dt_abs_max",
                    f"|dIp/dt| = {abs(rate[i]) / MA:.4g} MA/s on [{t0:g}, {t1:g}] s "
                    f"> {limits.dip_dt_abs_max / MA:.4g} MA/s",
                    _seg_name(design, t0),
                    t0,
                    float(abs(rate[i])),
                    limits.dip_dt_abs_max,
                )
            )
    if limits.flat_top_min_duration is not None:
        for s in design.timed_segments:
            if (
                s.name in limits.flat_top_segment_names
                and s.duration < limits.flat_top_min_duration
            ):
                out.append(
                    Violation(
                        "flat_top_min_duration",
                        f"duration {s.duration:g} s < {limits.flat_top_min_duration:g} s",
                        s.name,
                        s.start,
                        s.duration,
                        limits.flat_top_min_duration,
                    )
                )
    return out


def report(violations: list[Violation], limits: Limits | None = None) -> str:
    head = ""
    if limits is not None and limits.status.upper() == "PLACEHOLDER":
        head = (
            f"NOTE: limits from {limits.source} are PLACEHOLDERS (illustrative); "
            "the real limits must come from Operations (OLC).\n"
        )
    if not violations:
        return head + "OK: no violation"
    lines = [f"{len(violations)} violation(s):"] + [f"  - {v}" for v in violations]
    return head + "\n".join(lines)
