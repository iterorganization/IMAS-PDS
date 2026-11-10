"""Data model of the designer-level item "Ip reference waveform with segment structure".

Conventions (plan psps_to_kcurr_data_chain_plan.md section 6):

* time in s, Ip in A, piecewise-linear vertices;
* the IMAS sign is kept in the model (ITER: Ip < 0); the conversion to the
  positive PCS frame happens only in ``export_refgen_xml``;
* segments carry absolute start/end times, are contiguous, cover the waveform
  exactly; identifiers follow pcs@add-AM PS_NominalWaveforms.xml (decision D8,
  2026-11-02): the first segment (e.g. "ramp-up") has id 0, the following
  nominal segments 1, 2, ..., and the chain ends with a zero-duration STOP
  segment whose id is configurable (99 in the pcs add-AM example schedule,
  65535 in the IPP D15 strawman convention); there is no separate Init segment;
* the designer YAML holds -Ip by default (decision D11: convention "minus_ip",
  ITER values positive); ``read_yaml`` converts it to the IMAS sign on input;
* t = 0 is the plasma initiation (decision D10, ``time_origin``); an optional
  ``time_offset_s`` is added to absolute times at export.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

import numpy as np

#: Relative/absolute tolerance used to compare segment boundaries (s).
TIME_TOL = 1e-9

#: Default IDS path of the Ip reference (DD 4) and its PCS signal name.
IP_PATH_DD4 = "pulse_schedule/flux_control/ip/reference"
IP_PATH_DD3 = "pulse_schedule/flux_control/i_plasma/reference"
DEFAULT_SIGNALS = {IP_PATH_DD4: "Ipl_ref"}

#: Default id of the terminal STOP segment (pcs add-AM PS_NominalWaveforms.xml).
DEFAULT_STOP_ID = 99
#: Id of the first nominal segment (pcs add-AM: "ramp-up" id 0, D8).
FIRST_SEGMENT_ID = 0
STOP_NAME = "STOP"

#: Sign conventions of the designer YAML values (decision D11, 2026-11-02).
CONVENTION_MINUS_IP = "minus_ip"  # YAML value = -Ip (ITER: positive); designer default
CONVENTION_IMAS = "imas"  # YAML value = Ip in the IMAS sign (ITER: negative); tools
CONVENTIONS = (CONVENTION_MINUS_IP, CONVENTION_IMAS)
DEFAULT_CONVENTION = CONVENTION_MINUS_IP
#: -Ip = IMAS_TO_MINUS_IP_SIGN x Ip (YAML "minus_ip" and the PSPS JSON display).
IMAS_TO_MINUS_IP_SIGN = -1.0

#: Time origin of the designer file (decision D10, 2026-11-02).
TIME_ORIGIN_PLASMA_INITIATION = "plasma_initiation"
#: Reserved, not implemented: the offset to T0 / to the DINA time base is a
#: decision still to take.
TIME_ORIGINS_RESERVED = ("control_handover_T0", "dina")
#: Segment ids are unsigned 16-bit in the strawman convention (STOP = 65535).
MAX_SEGMENT_ID = 65535


class ValidationError(ValueError):
    """Raised when the pulse design violates a rule; lists every violation."""

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("invalid pulse design:\n  - " + "\n  - ".join(self.problems))


@dataclass(frozen=True)
class Segment:
    """One pulse-schedule segment with absolute times (s)."""

    name: str
    id: int
    start: float
    end: float
    wd_target: str | None = None  # name of the next segment (None for STOP)

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def is_stop(self) -> bool:
        return self.name == STOP_NAME


@dataclass
class IpWaveform:
    """Piecewise-linear Ip reference, IMAS sign (ITER Ip < 0), SI units."""

    time: np.ndarray
    value: np.ndarray
    ids_path: str = IP_PATH_DD4
    signal_name: str = "Ipl_ref"
    designer_name: str = "ip_reference"
    units: str = "A"

    def __post_init__(self) -> None:
        self.time = np.asarray(self.time, dtype=float)
        self.value = np.asarray(self.value, dtype=float)

    def sample(self, t: np.ndarray | float) -> np.ndarray:
        """Linear interpolation (the RefGen EXECUTION_RULE "Linear")."""
        return np.interp(t, self.time, self.value)


@dataclass
class PulseDesign:
    """A designer's pulse: global metadata, one Ip waveform, the segment chain."""

    waveform: IpWaveform
    segments: list[Segment]
    globals: dict = field(default_factory=dict)
    name: str = "pulse"
    stop_id: int = DEFAULT_STOP_ID
    #: sign convention of the YAML values the design was read from (informative)
    convention: str = DEFAULT_CONVENTION
    time_origin: str = TIME_ORIGIN_PLASMA_INITIATION
    #: added to absolute times at export when the target needs another origin
    time_offset_s: float = 0.0
    #: raw PROPOSED ``exceptions:`` block (used by export_refgen_eh_example only)
    exceptions: dict | None = None
    #: raw PROPOSED PSC-3 blocks (used by export_psc_config): ``events:``,
    #: ``exception_handling:`` and ``psc:`` (interface inputs, constant references)
    events: dict | None = None
    exception_handling: dict | None = None
    psc: dict | None = None
    #: D20 window cut (designer time of the PSC clock t = 0), set by cut.cut_design
    cut_at: float | None = None
    #: what the cut did: original start of the first kept segment, shift, dropped names
    cut_info: dict | None = None

    @property
    def timed_segments(self) -> list[Segment]:
        """Segments with a trajectory (all but STOP)."""
        return [s for s in self.segments if not s.is_stop]

    def validate(self) -> None:
        validate(self)


def segment_points(wf: IpWaveform, seg: Segment) -> tuple[np.ndarray, np.ndarray]:
    """Vertices of ``wf`` restricted to ``seg``, cut at both boundaries.

    Returns the segment-relative times (first one exactly 0.0) and the values
    (IMAS sign). Vertices closer than TIME_TOL to a boundary are merged into it.
    """
    inner = (wf.time > seg.start + TIME_TOL) & (wf.time < seg.end - TIME_TOL)
    t_abs = np.concatenate(([seg.start], wf.time[inner], [seg.end]))
    vals = wf.sample(t_abs)
    t_rel = t_abs - seg.start
    t_rel[0] = 0.0
    return t_rel, vals


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=TIME_TOL, abs_tol=TIME_TOL)


def validate(design: PulseDesign) -> None:
    """Check every rule; raise ValidationError listing all violations."""
    p: list[str] = []
    wf = design.waveform
    t, v = wf.time, wf.value
    if t.ndim != 1 or v.ndim != 1 or t.size != v.size:
        p.append(
            f"time and value must be 1-D of equal length (got {t.shape}, {v.shape})"
        )
    elif t.size < 2:
        p.append("the waveform needs at least two vertices")
    else:
        if not (np.all(np.isfinite(t)) and np.all(np.isfinite(v))):
            p.append("time and value must be finite")
        if np.any(np.diff(t) <= 0):
            p.append("time must be strictly increasing")
        if np.any(v > 0):
            warnings.warn(
                f"{wf.ids_path}: some Ip values are > 0; ITER Ip is negative in the IMAS "
                "convention (COCOS 11/17), check the sign",
                stacklevel=2,
            )

    if design.time_origin != TIME_ORIGIN_PLASMA_INITIATION:
        p.append(
            f"time_origin {design.time_origin!r}: only "
            f"{TIME_ORIGIN_PLASMA_INITIATION!r} is implemented"
        )
    if not math.isfinite(design.time_offset_s):
        p.append("time_offset_s must be finite")

    segs = design.segments
    if len(segs) < 2:
        p.append("at least one timed segment and a STOP segment are required")
        raise ValidationError(p)

    ids = [s.id for s in segs]
    names = [s.name for s in segs]
    if len(set(ids)) != len(ids):
        p.append(f"segment ids are not unique: {ids}")
    if len(set(names)) != len(names):
        p.append(f"segment names are not unique: {names}")
    for s in segs:
        if not (0 <= s.id <= MAX_SEGMENT_ID):
            p.append(f"segment {s.name!r}: id {s.id} outside 0..{MAX_SEGMENT_ID}")

    first, last = segs[0], segs[-1]
    # after a D20 window cut the first kept segment keeps its own id (the PSC starts
    # in it through the interface default of current_segment, export_psc_config)
    first_id = first.id if design.cut_at is not None else FIRST_SEGMENT_ID
    if first.id != first_id:
        p.append(
            f"first segment must have id {FIRST_SEGMENT_ID} (got {first.name!r}, id {first.id}); "
            "convention of pcs@add-AM PS_NominalWaveforms.xml: ramp-up 0, then 1, 2, ..."
        )
    nominal_ids = [s.id for s in segs[:-1]]
    if nominal_ids != list(range(first_id, first_id + len(nominal_ids))):
        p.append(
            f"nominal segment ids must be successive {first_id}, "
            f"{first_id + 1}, ... (got {nominal_ids})"
        )
    if last.name != STOP_NAME or last.id != design.stop_id:
        p.append(
            f"last segment must be '{STOP_NAME}' with id {design.stop_id} (got {last.name!r}, id {last.id})"
        )
    if not _close(last.duration, 0.0):
        p.append("the STOP segment must have zero duration")
    for s in segs[:-1]:
        if s.is_stop:
            p.append("STOP may only be the last segment")
        elif not s.duration > TIME_TOL:
            p.append(f"segment {s.name!r}: duration must be > 0 (got {s.duration})")

    for a, b in zip(segs[:-1], segs[1:]):
        if not _close(a.end, b.start):
            p.append(
                f"segments {a.name!r} and {b.name!r} are not contiguous ({a.end} != {b.start})"
            )
        if a.wd_target != b.name:
            p.append(
                f"segment {a.name!r}: wd_target {a.wd_target!r} must be the next segment {b.name!r} "
                "(only a linear chain is supported by this prototype)"
            )
    if last.wd_target is not None:
        p.append("the STOP segment has no wd_target")

    if t.ndim == 1 and t.size >= 2:
        if not _close(first.start, float(t[0])):
            p.append(
                f"first segment starts at {first.start} s but the waveform at {t[0]} s"
            )
        if not _close(last.start, float(t[-1])):
            p.append(f"segments end at {last.start} s but the waveform at {t[-1]} s")

    if p:
        raise ValidationError(p)
