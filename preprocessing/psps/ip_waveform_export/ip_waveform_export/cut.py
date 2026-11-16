"""D20 window cut: start the PSC clock at a designer time ``t_cut``.

Decision D20 (user, 2026-11-06): the PDS window of pulse 105073 starts at
84.3176 s (first NICE slice) while the designer's first segment starts earlier
(79.2176 s in the P2c/P2e files). The PSC starts in the segment given by the
interface default of ``current_segment`` and RefGen POINT times are
segment-relative (``LocalTime = 0`` on load, pcssp-nightly@ebf3ee0
``src/psc/+REFGEN/+TRAJ/trajGenClass.m:61-68,99``), so the schedule handed to
the PSC must begin at the window start.

``cut_design`` therefore

* drops every timed segment that ends at or before ``t_cut``;
* truncates the segment that contains ``t_cut`` so that it starts at ``t_cut``:
  its POINTs are shifted by ``-(t_cut - original start)`` (segment-relative
  times are recomputed from the new start by ``segment_points``), an
  interpolated first POINT at the new t = 0 is added, and its duration, hence
  the watchdog ``wd_time`` written to the schedule and the behaviour tree, is
  shortened by the same amount;
* drops the waveform vertices before ``t_cut`` and inserts the interpolated
  vertex at ``t_cut``;
* keeps every segment id (the first kept segment is not renumbered; the PSC
  interface default of ``current_segment`` is set to its id).

The offset is recorded in ``design.cut_at`` / ``design.cut_info`` and written by
the exporters (XML comments, IDS ``ids_properties.comment``, JSON
``_conventions``). Absolute times stay on the designer origin (D10): the PSC
clock is ``t_psc = t_designer - t_cut``.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np

from .model import TIME_TOL, IpWaveform, PulseDesign, Segment, ValidationError


def cut_design(design: PulseDesign, t_cut: float) -> PulseDesign:
    """Return a copy of ``design`` whose schedule starts at ``t_cut`` (designer time)."""
    t_cut = float(t_cut)
    if not math.isfinite(t_cut):
        raise ValidationError(["--cut-at must be finite"])
    timed = design.timed_segments
    if not timed:
        raise ValidationError(["cut: no timed segment"])
    if t_cut < timed[0].start - TIME_TOL:
        raise ValidationError(
            [f"cut at {t_cut} s is before the first segment start {timed[0].start} s"]
        )
    if t_cut >= timed[-1].end - TIME_TOL:
        raise ValidationError(
            [
                f"cut at {t_cut} s leaves no timed segment (last one ends at {timed[-1].end} s)"
            ]
        )
    kept: list[Segment] = []
    dropped: list[str] = []
    first_info = None
    for seg in design.segments:
        if seg.is_stop:
            kept.append(seg)
            continue
        if seg.end <= t_cut + TIME_TOL:
            dropped.append(seg.name)
            continue
        if not kept and seg.start < t_cut - TIME_TOL:
            first_info = {"first_segment": seg.name, "original_start": seg.start}
            seg = dataclasses.replace(seg, start=t_cut)
        elif not kept:
            first_info = {"first_segment": seg.name, "original_start": seg.start}
        kept.append(seg)
    wf = design.waveform
    keep = wf.time > t_cut + TIME_TOL
    t_new = np.concatenate(([t_cut], wf.time[keep]))
    v_new = np.concatenate(([float(wf.sample(t_cut))], wf.value[keep]))
    new_wf = IpWaveform(
        time=t_new,
        value=v_new,
        ids_path=wf.ids_path,
        signal_name=wf.signal_name,
        designer_name=wf.designer_name,
        units=wf.units,
    )
    info = {
        "t_cut": t_cut,
        "dropped_segments": dropped,
        **(first_info or {}),
        "shift_s": t_cut - (first_info or {"original_start": t_cut})["original_start"],
    }
    out = dataclasses.replace(
        design, waveform=new_wf, segments=kept, cut_at=t_cut, cut_info=info
    )
    out.validate()
    return out


def cut_note(design: PulseDesign) -> str:
    """One-line description of the cut for comments and metadata ('' if none)."""
    if design.cut_at is None:
        return ""
    i = design.cut_info or {}
    dropped = ", ".join(i.get("dropped_segments", [])) or "none"
    return (
        f"D20 window cut: PSC clock t = 0 at designer t = {design.cut_at:.6f} s "
        f"(t_psc = t_designer - {design.cut_at:.6f} s); first kept segment "
        f"{i.get('first_segment')!r} originally started at {i.get('original_start', 0.0):.6f} s, "
        f"its POINTs shifted by -{i.get('shift_s', 0.0):.6f} s and its wd_time shortened "
        f"by the same amount; dropped segments: {dropped}"
    )
