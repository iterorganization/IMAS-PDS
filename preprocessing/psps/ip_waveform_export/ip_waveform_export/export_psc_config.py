"""PROPOSAL (phase PSC-3): the four PSC mask configuration files from one designer YAML.

The Pulse Supervision Controller (PSC) on the reference line (pcssp-nightly
merge_IGZ_PSC ebf3ee0, ``src/psc/``; unmerged) reads four XML files named in its
mask (``PSCInterConfFileName``, ``GlobMonFileName``, ``DecisionFileName``,
``RefGenFileName``, relative to ``ConfFolderPath``). ``write_psc_config`` writes,
into ``<out-dir>/psc_config_<name>/``:

==========================  =====================================================
``PSCIntConfig.xml``        interface (blackboard + In/Out/Int buses); format of
                            pcs@bb29ad6 (add-AM) ``top-models/magnetic-control/
                            CREATE_TC_01/PSC_config/PSCIntConfig.xml``; parser
                            ``+PSC/+MODEL/parserPSCInterface.m``
``PSCGlobalMonConfig.xml``  global monitoring: one MONITORING per ``events:``
                            entry (flag ``glb_ps__<event>``); format of TC01
                            ``PSCGlobalMonConfig.xml``; parser
                            ``+GLOBALMON/+MODEL/parserGlobMonConf.m``
``BTree.xml``               behaviour tree (Groot XML): nominal segments and the
                            exception branches in the priority order of
                            pcssp@2233365 (PSC-FWHL) ``BTreeFWHL.xml``; parser
                            ``+BT/+MODEL/parseXML.m``
``PS.xml``                  RefGen schedule: nominal ``Ipl_ref`` (as
                            ``export_refgen_xml``), constant ``CSPF_curr_ref[11]``,
                            ``Rpl_ref``, ``Zpl_ref`` in every nominal segment, and
                            the exception segments; parser
                            ``+REFGEN/+MODEL/parsePSXML.m``
==========================  =====================================================

Behaviour-tree structure (reactive Fallback ``FallbackNomEH``, priority = child
order, re-evaluated every tick):

[1] ``FallHrdEHListSudden``: per ``exception_handling.hard_sudden`` entry a
    Precondition ``{glb_ps__<event>} == 1`` (guarded so that it fires once, not
    while the target or STOP is active) -> ForceFailure(Sequence(AssignValue
    current -> old, AssignValue <hard id> -> current_segment)), as FWHL
    ``FwhlHrdEH3``.
[2] ``ParSegNom`` (Parallel, mainTask 1): ``FallNomSegList`` (Precondition
    ``{current_segment} == id`` -> RefGen ``signal='all'``
    ``typeAddition='replace'`` with ``wd_time`` = segment duration and
    ``wd_target`` = next id; STOP self-loop ``wd_time 5`` as add-AM) in Parallel
    with ``ParSftEHList`` (Parallel, mainTask -1): per soft overlay a
    Precondition ``{glb_ps__<event>} == 1 and <a nominal segment is active>``
    -> RefGen on one signal with ``typeAddition`` ``silence,replace`` (or another
    value accepted by ``RefGenerator.validateTransitionType``), optional recovery
    ``condition='{glb_ps__<event>} == 0'`` (path status 2 -> overlay removed,
    ``PathHandler.m:126-136``) and watchdog ``wd_target`` = a hard segment.
[3] ``FallHrdEHList``: per hard segment a Precondition ``{current_segment} == id``
    -> RefGen ``signal='all'`` ``entryRule='Linear'`` ``typeAddition='replace'``
    (FWHL ``PathEHTerm1``), ``wd_target`` = STOP.

Only the behaviour-tree ``wd_time`` / ``wd_target`` are read by the PSC
(``parsePSXML.m:249-250`` stores only name and id of a SEGMENT); the schedule
carries identical values (names instead of ids) for the reader.

Global monitoring has no debounce: ``parserGlobMonConf.m`` / ``EHGlobalMon.m``
know SCRIPT, PRECONDITION and VALIDATION nodes only (``EHGlobalMon.m:115-165``);
a ``debounce`` > 0 is recorded as a comment and a warning. Latching and
hysteresis are written into the MONITORING script itself (the flag reads its own
previous value). No SIGNAL_VALID is generated: its timers use the wall clock
(``datetime()``), its RUNNING test is inverted and it calls an undefined
``PcsQuality`` (``+GLOBALMON/+BASICNodes/SignalValClass.m:98-160``, ebf3ee0).

SIGNS AND UNITS: every value in ``events:``, ``exception_handling:`` and
``psc.references`` is in the frame of the PSC signal it applies to: Ip values in
the positive PCS frame (= -Ip_IMAS, the value the Session Leader edits, D11),
independent of ``globals.convention``; coil currents in the frame the fork glue
passes to the wrapper (pf_active per-turn current, IMAS sign); SI units.
"""

from __future__ import annotations

import math
import warnings
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .cut import cut_note
from .export_refgen_eh_example import camel
from .export_refgen_xml import IMAS_TO_PCS_IP_SIGN, build_tree, fmt_attr, fmt_float
from .model import MAX_SEGMENT_ID, STOP_NAME, PulseDesign, ValidationError

PROPOSAL = "PROPOSAL (PSC-3)"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
#: Namespaces of TC01 PSCGlobalMonConfig.xml (copied verbatim).
GLOBMON_NS = "http://www.ipp.mpg.de/2004/Schema/Exceptions_Desc"
GLOBMON_SCHEMA = "http://www.ipp.mpg.de/2016/Schema/Exceptions.xsd"
#: STOP self-loop watchdog of pcs@add-AM BTreeNominalWaveforms.xml (SubTreeNominalStop).
STOP_WD_TIME = 5.0
#: Rule set of the FWHL exception trajectories (PS_FWHLEH.xml).
EH_RULES = (("ENTRY_RULE", "None"), ("EXIT_RULE", "Last"), ("EXECUTION_RULE", "Linear"))
NOMINAL_RULES = (
    ("EXECUTION_RULE", "Linear"),
    ("ENTRY_RULE", "Step"),
    ("EXIT_RULE", "last"),
)
#: Accepted by RefGenerator.validateTransitionType (RefGenerator.m:186-226).
TYPE_ADDITIONS = (
    "silence,replace",
    "freeze,replace",
    "silence,offset",
    "freeze,offset",
    "silence,scale",
    "freeze,scale",
)
OPS = (">", ">=", "<", "<=")
#: Internal blackboard variables of TC01 PSCIntConfig.xml:60-80 (order kept).
TC01_INTERNALS = (
    (
        "old_mod_segment",
        "psc_OldModSegment",
        "double",
        "Previous modification segment id",
    ),
    ("current_segment", "psc_ref__current_segment", "double", "Current segment id"),
    (
        "last_mod_segment",
        "psc_ref_lastModSegment",
        "double",
        "Last modificator segment id",
    ),
    (
        "old_current_segment",
        "psc_OldCurrentSegment",
        "double",
        "Previous current segment id",
    ),
    ("lastTimeDiff", "psc_lastTimeDiff", "double", "Duration of the last sample time"),
    ("SegmentTime", "psc_segmentTime", "double", "Duration of the segment time"),
    ("simTime", "psc_simTime", "double", "Duration of the simulation time"),
    ("glb_ps__run_plasma", "glb_ps__run_plasma", "boolean", "in plasma state"),
    ("glb__PulseDone", "glb__PulseDone", "boolean", "Pulse passed without alarms"),
)
DEFAULT_INPUTS = (
    {
        "name": "ip_ip__meas",
        "description": "measured plasma current, PCS frame (= -Ip_IMAS)",
    },
    {
        "name": "plasma_exist",
        "signal": "plasma_state__exist_diag",
        "description": "There is plasma",
    },
)


@dataclass(frozen=True)
class PscInput:
    name: str  # blackboard key (usage name without "i:")
    signal: str  # bus element name
    description: str
    type: str = "Pcssignal"


@dataclass(frozen=True)
class ConstRef:
    name: str
    value: tuple[float, ...]
    source: str
    description: str

    @property
    def dimension(self) -> int:
        return len(self.value)


@dataclass(frozen=True)
class Event:
    name: str
    description: str
    code: str
    signals: tuple[str, ...]
    debounce: float

    @property
    def output(self) -> str:
        return f"glb_ps__{self.name}"


@dataclass(frozen=True)
class SuddenHard:
    event: str
    target: str


@dataclass(frozen=True)
class SoftOverlay:
    name: str
    id: int
    event: str
    signal: str
    type_addition: str
    entry_rule: str
    points: tuple[tuple[float, float], ...] | None  # None = hold the last value
    recovery: bool
    wd_time: float
    wd_target: str


@dataclass(frozen=True)
class HardSegment:
    name: str
    id: int
    from_value: float
    to_value: float
    ramp_s: float
    hold_s: float
    wd_target: str = STOP_NAME

    @property
    def wd_time(self) -> float:
        return self.ramp_s + self.hold_s


@dataclass(frozen=True)
class PscSpec:
    supervisor: str
    inputs: tuple[PscInput, ...]
    refs: tuple[ConstRef, ...]
    events: tuple[Event, ...]
    sudden: tuple[SuddenHard, ...]
    soft: tuple[SoftOverlay, ...]
    hard: tuple[HardSegment, ...]
    run_plasma_ip_min: float
    pulse_done_after_s: float


def _num(x, what: str, p: list[str]) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        p.append(f"{what}: not a number ({x!r})")
        return math.nan
    if not math.isfinite(v):
        p.append(f"{what}: must be finite")
    return v


def _ref(name: str, inputs: set[str]) -> str:
    """Blackboard reference in PSC script syntax: inputs are Pcssignal (.value)."""
    return f"{{{name}.value}}" if name in inputs else f"{{{name}}}"


def _event_code(name: str, e: dict, inputs: set[str], known: set[str], p: list[str]):
    out = f"glb_ps__{name}"
    if "expr" in e:
        code = str(e["expr"])
        sigs = tuple(str(s) for s in e.get("signals") or [])
        for s in sigs:
            if s not in known:
                p.append(f"event {name}: signal {s!r} not declared in the interface")
        return code, sigs
    sig = str(e.get("signal", ""))
    if sig not in known:
        p.append(f"event {name}: signal {sig!r} not declared in the interface")
    op = str(e.get("op", ""))
    thr = _num(e.get("threshold"), f"event {name}: threshold", p)
    s = _ref(sig, inputs)
    sigs = [sig]
    if "reference" in e:
        r = e["reference"]
        if isinstance(r, str):
            if r not in known:
                p.append(f"event {name}: reference {r!r} not declared in the interface")
            rs = _ref(r, inputs)
            sigs.append(r)
        else:
            rs = fmt_float(_num(r, f"event {name}: reference", p))
        s = f"abs({s} - {rs})"
        if op not in (">", ">="):
            p.append(
                f"event {name}: with a reference only '>' / '>=' (excursion) is supported"
            )
    if op not in OPS:
        p.append(f"event {name}: op {op!r} not in {OPS}")
        return "", tuple(sigs)
    code = f"{s} {op} {fmt_float(thr)}"
    if (
        "release_threshold" in e
    ):  # hysteresis: stays set until the release threshold is crossed
        rel = _num(e["release_threshold"], f"event {name}: release_threshold", p)
        if (op.startswith(">") and not rel < thr) or (
            op.startswith("<") and not rel > thr
        ):
            p.append(f"event {name}: release_threshold must lie inside the threshold")
        code = f"{code} or ({{{out}}} == 1 and {s} {op} {fmt_float(rel)})"
    if bool(e.get("latch", False)):
        code = f"{code} or {{{out}}} == 1"
    return code, tuple(sigs)


def parse_psc(design: PulseDesign) -> PscSpec:
    """Read and check the PROPOSED ``psc:``, ``events:`` and ``exception_handling:`` blocks."""
    p: list[str] = []
    psc = dict(design.psc or {})
    if not design.events or not design.exception_handling:
        raise ValidationError(
            [
                "--psc-config needs 'events:' and 'exception_handling:' blocks (see examples/ip_105073_psc.yaml)"
            ]
        )
    inputs = []
    for i in psc.get("inputs") or DEFAULT_INPUTS:
        if not isinstance(i, dict) or "name" not in i:
            p.append(f"psc.inputs: entry {i!r} needs a 'name'")
            continue
        inputs.append(
            PscInput(
                name=str(i["name"]),
                signal=str(i.get("signal", i["name"])),
                description=str(i.get("description", "")),
                type=str(i.get("type", "Pcssignal")),
            )
        )
    in_names = {i.name for i in inputs}
    if "ip_ip__meas" not in in_names or "plasma_exist" not in in_names:
        p.append(
            "psc.inputs: 'ip_ip__meas' and 'plasma_exist' are required (SCENARIO run_plasma)"
        )
    refs = []
    for name, r in (psc.get("references") or {}).items():
        val = r.get("value") if isinstance(r, dict) else None
        vals = val if isinstance(val, list) else [val]
        vals = tuple(_num(v, f"psc.references.{name}", p) for v in vals)
        dim = int(r.get("dimension", len(vals))) if isinstance(r, dict) else 1
        if dim != len(vals):
            p.append(f"psc.references.{name}: dimension {dim} but {len(vals)} values")
        if not isinstance(r, dict) or not r.get("source"):
            p.append(
                f"psc.references.{name}: 'source' (where the value comes from) is required"
            )
        refs.append(
            ConstRef(
                str(name),
                vals,
                str(r.get("source", "")) if isinstance(r, dict) else "",
                str(r.get("description", f"Reference {name}"))
                if isinstance(r, dict)
                else "",
            )
        )
    sig = design.waveform.signal_name
    if any(r.name == sig for r in refs):
        p.append(f"psc.references: {sig} comes from the waveform, not from references")
    outputs = {sig} | {r.name for r in refs}
    known = in_names | outputs | {n for n, *_ in TC01_INTERNALS}
    known |= {f"glb_ps__{n}" for n in design.events}

    events = []
    for name, e in design.events.items():
        if not isinstance(e, dict):
            p.append(f"events.{name}: must be a mapping")
            continue
        code, sigs = _event_code(str(name), e, in_names, known, p)
        deb = _num(e.get("debounce", 0.0), f"event {name}: debounce", p)
        if deb > 0:
            warnings.warn(
                f"event {name}: debounce {deb:g} s is not representable in the PSC global "
                "monitoring (no debounce node, EHGlobalMon.m:115-165); written as a comment only",
                stacklevel=2,
            )
        events.append(Event(str(name), str(e.get("description", "")), code, sigs, deb))
    ev_names = {e.name for e in events}

    eh = design.exception_handling
    hard = []
    for h in eh.get("hard") or []:
        try:
            hard.append(
                HardSegment(
                    name=str(h["name"]),
                    id=int(h["id"]),
                    from_value=_num(h["from_value"], f"{h['name']}: from_value", p),
                    to_value=_num(h.get("to_value", 0.0), f"{h['name']}: to_value", p),
                    ramp_s=_num(h["ramp_s"], f"{h['name']}: ramp_s", p),
                    hold_s=_num(h.get("hold_s", 0.0), f"{h['name']}: hold_s", p),
                    wd_target=str(h.get("wd_target", STOP_NAME)),
                )
            )
        except (KeyError, TypeError) as err:
            p.append(f"exception_handling.hard: malformed entry ({err!r})")
    hard_names = {h.name for h in hard}
    sudden = []
    for s in eh.get("hard_sudden") or []:
        try:
            sudden.append(SuddenHard(event=str(s["event"]), target=str(s["target"])))
        except (KeyError, TypeError) as err:
            p.append(f"exception_handling.hard_sudden: malformed entry ({err!r})")
    soft = []
    for s in eh.get("soft") or []:
        try:
            pts = s.get("points")
            points = None
            if pts is not None:
                points = tuple(
                    (
                        _num(t, f"{s['name']}: points.time", p),
                        _num(v, f"{s['name']}: points.value", p),
                    )
                    for t, v in zip(pts["time"], pts["value"], strict=True)
                )
            elif not s.get("hold", False):
                p.append(f"{s['name']}: give 'points' or 'hold: true'")
            soft.append(
                SoftOverlay(
                    name=str(s["name"]),
                    id=int(s["id"]),
                    event=str(s["event"]),
                    signal=str(s.get("signal", sig)),
                    type_addition=str(s.get("type_addition", "silence,replace")),
                    entry_rule=str(s.get("entry_rule", "Linear")),
                    points=points,
                    recovery=bool(s.get("recovery", False)),
                    wd_time=_num(s["wd_time"], f"{s['name']}: wd_time", p),
                    wd_target=str(s["wd_target"]),
                )
            )
        except (KeyError, TypeError, ValueError) as err:
            p.append(f"exception_handling.soft: malformed entry ({err!r})")

    nominal_ids = {s.id for s in design.segments}
    eh_ids = [x.id for x in (*soft, *hard)]
    if len(set(eh_ids)) != len(eh_ids) or nominal_ids & set(eh_ids):
        p.append(
            f"exception_handling: ids {eh_ids} must be unique and differ from the nominal ids"
        )
    if any(not 0 <= i <= MAX_SEGMENT_ID for i in eh_ids):
        p.append(f"exception_handling: ids outside 0..{MAX_SEGMENT_ID}")
    names = [s.name for s in design.segments] + [x.name for x in (*soft, *hard)]
    if len(set(names)) != len(names):
        p.append(f"exception_handling: segment names not unique: {names}")
    for s in sudden:
        if s.event not in ev_names:
            p.append(f"hard_sudden: event {s.event!r} not defined in 'events:'")
        if s.target not in hard_names:
            p.append(f"hard_sudden: target {s.target!r} must name a 'hard' segment")
    for s in soft:
        if s.event not in ev_names:
            p.append(f"{s.name}: event {s.event!r} not defined in 'events:'")
        if s.type_addition not in TYPE_ADDITIONS:
            p.append(f"{s.name}: type_addition must be one of {TYPE_ADDITIONS}")
        if s.entry_rule not in ("Step", "Linear"):
            p.append(f"{s.name}: entry_rule must be Step or Linear")
        if s.signal not in outputs:
            p.append(f"{s.name}: signal {s.signal!r} is not a schedule output")
        if not s.wd_time > 0:
            p.append(f"{s.name}: wd_time must be > 0")
        if s.wd_target not in hard_names | {STOP_NAME}:
            p.append(
                f"{s.name}: wd_target {s.wd_target!r} must name a hard segment or STOP"
            )
        if s.points and (
            s.points[0][0] != 0.0
            or any(b[0] <= a[0] for a, b in zip(s.points, s.points[1:]))
        ):
            p.append(f"{s.name}: points.time must start at 0 and increase")
    for h in hard:
        if not h.ramp_s > 0 or h.hold_s < 0:
            p.append(f"{h.name}: need ramp_s > 0 and hold_s >= 0")
        if h.wd_target != STOP_NAME:
            p.append(f"{h.name}: wd_target must be {STOP_NAME!r}")
    if not hard:
        p.append(
            "exception_handling: at least one 'hard' segment (termination) expected"
        )
    if p:
        raise ValidationError(p)
    timed = design.timed_segments
    t_end = timed[-1].end - timed[0].start  # schedule length on the PSC clock
    return PscSpec(
        supervisor=str(psc.get("supervisor_name", "PSC")),
        inputs=tuple(inputs),
        refs=tuple(refs),
        events=tuple(events),
        sudden=tuple(sudden),
        soft=tuple(soft),
        hard=tuple(hard),
        run_plasma_ip_min=float(psc.get("run_plasma_ip_min", 1.0e5)),
        pulse_done_after_s=float(psc.get("pulse_done_after_s", t_end)),
    )


# --------------------------------------------------------------------------- interface
def build_interface(design: PulseDesign, spec: PscSpec) -> ET.Element:
    root = ET.Element("AP_CONF", {"name": spec.supervisor})
    root.append(
        ET.Comment(
            f" {PROPOSAL}: generated by ip_waveform_export from {design.name}; format of pcs@bb29ad6 TC01 PSCIntConfig.xml "
        )
    )

    def usage(name, cls, signal, typ, dim, value, desc):
        u = ET.SubElement(root, "USAGE", {"name": name, "class": cls})
        ET.SubElement(
            u,
            "SIGNAL",
            {
                "name": signal,
                "type": typ,
                "dimension": str(dim),
                "value": value,
                "description": desc,
            },
        )

    for i in spec.inputs:
        usage(f"i:{i.name}", "Input", i.signal, i.type, 1, "0", i.description)
    sig = design.waveform.signal_name
    usage(
        f"o:{sig}",
        "Output",
        f"psc_ref__{sig}",
        "double",
        1,
        "0",
        "Reference for plasma current (PCS frame)",
    )
    for r in spec.refs:
        usage(
            f"o:{r.name}",
            "Output",
            f"psc_ref__{r.name}",
            "double",
            r.dimension,
            "0",
            r.description,
        )
    first_id = design.segments[0].id
    for name, signal, typ, desc in TC01_INTERNALS:
        value = str(first_id) if name == "current_segment" else "0"
        usage(name, "Internal", signal, typ, 1, value, desc)
    for e in spec.events:
        usage(
            e.output, "Internal", e.output, "boolean", 1, "0", e.description or e.name
        )
    ET.indent(root, space="\t")
    return root


# --------------------------------------------------------------------------- monitoring
def build_globmon(design: PulseDesign, spec: PscSpec) -> ET.Element:
    ET.register_namespace("xsi", XSI_NS)
    root = ET.Element(
        "EXCEPTIONS",
        {"xmlns": GLOBMON_NS, f"{{{XSI_NS}}}schemaLocation": GLOBMON_SCHEMA},
    )
    root.append(
        ET.Comment(
            f" {PROPOSAL}: generated by ip_waveform_export from {design.name}; format of pcs@bb29ad6 TC01 PSCGlobalMonConfig.xml "
        )
    )
    sc = ET.SubElement(root, "SCENARIOS")
    s = ET.SubElement(
        sc,
        "SCENARIO",
        {"name": "psc_glb_ps__run_plasma", "output": "glb_ps__run_plasma"},
    )
    ET.SubElement(
        s,
        "SCRIPT",
        {
            "code": f"{{plasma_exist.value}} and {{ip_ip__meas.value}} > {fmt_float(spec.run_plasma_ip_min)}"
        },
    )
    # The comment sits BEFORE the empty section: a section whose only child is a comment
    # makes parserGlobMonConf.m parse one nameless entry and fail ("Invalid field name: ''",
    # parse_validations l.139, MATLAB check 2026-11-06), so the element must stay childless.
    root.append(
        ET.Comment(
            " SIGNAL_VALIDS: none generated: SignalValClass (ebf3ee0) uses wall-clock timers, an inverted "
            "RUNNING test and an undefined PcsQuality (SignalValClass.m:98-160) "
        )
    )
    ET.SubElement(root, "SIGNAL_VALIDS")
    mo = ET.SubElement(root, "MONITORINGS")
    for e in spec.events:
        mo.append(
            ET.Comment(
                f" {e.name}: {e.description} "
                + (
                    f"(debounce {e.debounce:g} s NOT applied: no debounce in the global monitoring) "
                    if e.debounce > 0
                    else ""
                )
            )
        )
        m = ET.SubElement(
            mo, "MONITORING", {"name": f"psc_glb_{e.name}", "output": e.output}
        )
        ET.SubElement(m, "SCRIPT", {"code": e.code})
    go = ET.SubElement(root, "GOALS")
    go.append(
        ET.Comment(
            " simTime = the Simulink clock seen by the PSC block (PSCClass.execute) "
        )
    )
    g = ET.SubElement(
        go, "GOAL", {"name": "psc_glb_NoAlarm", "output": "glb__PulseDone"}
    )
    ET.SubElement(
        g, "SCRIPT", {"code": f"{{simTime}} > {fmt_float(spec.pulse_done_after_s)}"}
    )
    ET.indent(root, space="\t")
    return root


# --------------------------------------------------------------------------- schedule
def _trajectory(parent: ET.Element, signal: str, points, rules) -> None:
    traj = ET.SubElement(parent, "SIGNAL_TRAJECTORY", {"name": signal})
    for tag, rule in rules:
        ET.SubElement(traj, tag, {"is": rule})
    ref = ET.SubElement(traj, "REFERENCE")
    for t, v in points:
        ET.SubElement(
            ref,
            "POINT",
            {"time": fmt_float(t), "value": v if isinstance(v, str) else fmt_float(v)},
        )


def _vec(values) -> str:
    return "[" + ", ".join(fmt_float(v) for v in values) + "]"


def build_schedule(design: PulseDesign, spec: PscSpec) -> ET.ElementTree:
    tree = build_tree(design)
    root = tree.getroot()
    root.set(
        "comment",
        f"{PROPOSAL}: {root.get('comment')}; plus constant references and exception segments",
    )
    outputs = root.find("DECLARATIONS/OUTPUTS")
    for r in spec.refs:
        dflt = "0" if r.dimension == 1 else "(" + ",".join(["0"] * r.dimension) + ")"
        outputs.append(ET.Comment(f" {r.name}: constant, source: {r.source} "))
        ET.SubElement(
            outputs,
            "SIGNAL",
            {
                "name": r.name,
                "signal_type": "Amplitude",
                "type": "double",
                "dimension": str(r.dimension),
                "comment": f"Constant {r.name} (PSC-3 converter)",
                "value": dflt,
            },
        )
    segs = root.find("SEGMENTS")
    by_name = {s.name: s for s in design.segments}
    for seg_el in segs.findall("SEGMENT"):
        seg = by_name[seg_el.get("name")]
        if seg.is_stop:
            continue
        trajs = seg_el.find("SIGNAL_TRAJECTORIES")
        for r in spec.refs:
            v = fmt_float(r.value[0]) if r.dimension == 1 else _vec(r.value)
            _trajectory(trajs, r.name, [(0.0, v), (seg.duration, v)], NOMINAL_RULES)
    sig = design.waveform.signal_name
    for s in spec.soft:
        what = (
            "HOLD: no trajectory for the signal in this segment -> the last value is held "
            "(SignalGenClass.m:164-169)"
            if s.points is None
            else f"{s.signal} trajectory, PCS frame"
        )
        segs.append(
            ET.Comment(
                f" {PROPOSAL} SOFT overlay on {s.signal} for event {s.event}, typeAddition '{s.type_addition}'; {what} "
            )
        )
        el = ET.SubElement(
            segs,
            "SEGMENT",
            {
                "name": s.name,
                "id": str(s.id),
                "wd_time": fmt_attr(s.wd_time),
                "wd_target": s.wd_target,
            },
        )
        if s.points is not None:
            _trajectory(
                ET.SubElement(el, "SIGNAL_TRAJECTORIES"), s.signal, s.points, EH_RULES
            )
    for h in spec.hard:
        segs.append(
            ET.Comment(
                f" {PROPOSAL} HARD exception {h.name}: {sig} {h.from_value:g} -> {h.to_value:g} (PCS frame) over "
                f"{h.ramp_s:g} s, held {h.hold_s:g} s, then {h.wd_target}; other outputs hold their last value; "
                "the BT entry rule Linear blends from the frozen last output over 0.5 s (SignalGenClass.m:51) "
            )
        )
        el = ET.SubElement(
            segs,
            "SEGMENT",
            {
                "name": h.name,
                "id": str(h.id),
                "wd_time": fmt_attr(h.wd_time),
                "wd_target": h.wd_target,
            },
        )
        pts = [(0.0, h.from_value), (h.ramp_s, h.to_value)]
        if h.hold_s > 0:
            pts.append((h.wd_time, h.to_value))
        _trajectory(ET.SubElement(el, "SIGNAL_TRAJECTORIES"), sig, pts, EH_RULES)
    ET.indent(root, space="  ")
    return tree


# --------------------------------------------------------------------------- behaviour tree
def _action(
    parent,
    name,
    signal,
    seg_id,
    type_addition,
    wd_time,
    wd_target,
    entry=None,
    condition=None,
):
    attrs = {"ID": "RefGen", "name": name, "signal": signal, "segmentID": str(seg_id)}
    if entry:
        attrs["entryRule"] = entry
    attrs["typeAddition"] = type_addition
    if condition:
        attrs["condition"] = condition
    attrs["wd_time"] = fmt_attr(wd_time)
    attrs["wd_target"] = str(wd_target)
    return ET.SubElement(parent, "Action", attrs)


def build_btree(design: PulseDesign, spec: PscSpec) -> ET.Element:
    ids = {s.name: s.id for s in design.segments} | {h.name: h.id for h in spec.hard}
    ev = {e.name: e for e in spec.events}
    stop_id = design.stop_id
    nominal_active = " or ".join(
        f"{{current_segment}} == {s.id}" for s in design.timed_segments
    )

    root = ET.Element("root", {"main_tree_to_execute": "BehaviorTree"})
    for line in (
        f"{PROPOSAL}: generated by ip_waveform_export from {design.name}",
        "modelled on pcs@bb29ad6 BTreeNominalWaveforms.xml + pcssp@2233365 BTreeFWHL.xml",
        "[1] sudden hard EH  [2] nominal segments || soft-EH overlays  [3] hard-EH list",
        "only these wd_time / wd_target are read by the PSC (parsePSXML.m:249-250)",
        *([cut_note(design)] if design.cut_at is not None else []),
    ):
        root.append(ET.Comment(f" {line} ".replace("--", "- -")))
    main = ET.SubElement(root, "BehaviorTree", {"ID": "BehaviorTree"})
    top = ET.SubElement(main, "Fallback", {"name": "FallbackNomEH", "Reactive": "1"})

    sudden = ET.SubElement(
        top, "Fallback", {"name": "FallHrdEHListSudden", "Reactive": "1"}
    )
    for s in spec.sudden:
        tid = ids[s.target]
        cond = (
            f"{{{ev[s.event].output}}} == 1 and {{current_segment}} != {tid} "
            f"and {{current_segment}} != {stop_id}"
        )
        pre = ET.SubElement(
            sudden,
            "Precondition",
            {"name": f"{camel(s.event)}HrdEHSudden", "condition": cond},
        )
        seq = ET.SubElement(ET.SubElement(pre, "ForceFailure"), "Sequence")
        ET.SubElement(
            seq,
            "Action",
            {
                "ID": "AssignValue",
                "source": "{current_segment}",
                "target": "{old_current_segment}",
            },
        )
        ET.SubElement(
            seq,
            "Action",
            {
                "ID": "AssignValue",
                "name": f"Assign{camel(s.target)}",
                "source": str(tid),
                "target": "{current_segment}",
            },
        )

    par = ET.SubElement(
        top, "Parallel", {"name": "ParSegNom", "threshold": "1", "mainTask": "1"}
    )
    nom = ET.SubElement(par, "Fallback", {"name": "FallNomSegList", "Reactive": "1"})
    for s in design.segments:
        pre = ET.SubElement(
            nom,
            "Precondition",
            {
                "name": f"Precond{camel(s.name)}",
                "condition": f"{{current_segment}} == {s.id}",
            },
        )
        ET.SubElement(pre, "SubTree", {"ID": f"SubTreeSeg{camel(s.name)}"})
    sft = ET.SubElement(
        par, "Parallel", {"name": "ParSftEHList", "threshold": "1", "mainTask": "-1"}
    )
    for s in spec.soft:
        cond = f"{{{ev[s.event].output}}} == 1 and ({nominal_active})"
        pre = ET.SubElement(
            sft, "Precondition", {"name": f"{camel(s.name)}SftEH", "condition": cond}
        )
        ET.SubElement(pre, "SubTree", {"ID": f"SubTree{camel(s.name)}"})

    hrd = ET.SubElement(top, "Fallback", {"name": "FallHrdEHList", "Reactive": "1"})
    for h in spec.hard:
        pre = ET.SubElement(
            hrd,
            "Precondition",
            {
                "name": f"{camel(h.name)}HrdEH",
                "condition": f"{{current_segment}} == {h.id}",
            },
        )
        ET.SubElement(pre, "SubTree", {"ID": f"SubTree{camel(h.name)}"})

    subtree_ids = []
    timed = design.timed_segments
    for i, s in enumerate(design.segments):
        sid = f"SubTreeSeg{camel(s.name)}"
        subtree_ids.append(sid)
        bt = ET.SubElement(root, "BehaviorTree", {"ID": sid, "segmentID": str(s.id)})
        if s.is_stop:
            _action(
                bt,
                f"PathSeg{camel(s.name)}",
                "all",
                s.id,
                "replace",
                STOP_WD_TIME,
                s.id,
            )
        else:
            nxt = design.segments[i + 1]
            assert s in timed and nxt.name == s.wd_target
            _action(
                bt,
                f"PathSeg{camel(s.name)}",
                "all",
                s.id,
                "replace",
                s.duration,
                nxt.id,
            )
    for s in spec.soft:
        sid = f"SubTree{camel(s.name)}"
        subtree_ids.append(sid)
        bt = ET.SubElement(root, "BehaviorTree", {"ID": sid, "segmentID": str(s.id)})
        _action(
            bt,
            f"Path{camel(s.name)}",
            s.signal,
            s.id,
            s.type_addition,
            s.wd_time,
            ids[s.wd_target],
            entry=s.entry_rule,
            condition=f"{{{ev[s.event].output}}} == 0" if s.recovery else None,
        )
    for h in spec.hard:
        sid = f"SubTree{camel(h.name)}"
        subtree_ids.append(sid)
        bt = ET.SubElement(root, "BehaviorTree", {"ID": sid, "segmentID": str(h.id)})
        _action(
            bt,
            f"Path{camel(h.name)}",
            "all",
            h.id,
            "replace",
            h.wd_time,
            ids[h.wd_target],
            entry="Linear",
        )

    model = ET.SubElement(root, "TreeNodesModel")
    assign = ET.SubElement(model, "Action", {"ID": "AssignValue"})
    ET.SubElement(assign, "input_port", {"name": "source"})
    ET.SubElement(assign, "input_port", {"name": "target"})
    for sid in subtree_ids:
        ET.SubElement(model, "SubTree", {"ID": sid})
    ET.indent(root, space="    ")
    return root


#: file names written by write_psc_config (mask fields of PSC.slx)
FILES = {
    "intf": "PSCIntConfig.xml",
    "glob": "PSCGlobalMonConfig.xml",
    "bt": "BTree.xml",
    "refgen": "PS.xml",
}


def write_psc_config(design: PulseDesign, out_dir: str | Path) -> Path:
    """Write the four PSC configuration files into ``<out_dir>/psc_config_<name>/``."""
    spec = parse_psc(design)
    d = Path(out_dir) / f"psc_config_{design.name}"
    d.mkdir(parents=True, exist_ok=True)
    for key, el in (
        ("intf", build_interface(design, spec)),
        ("glob", build_globmon(design, spec)),
    ):
        data = ET.tostring(el, encoding="UTF-8", xml_declaration=True)
        (d / FILES[key]).write_bytes(data + b"\n")
    data = ET.tostring(
        build_schedule(design, spec).getroot(),
        encoding="ISO-8859-1",
        xml_declaration=True,
    )
    (d / FILES["refgen"]).write_bytes(data + b"\n")
    bt = ET.tostring(build_btree(design, spec), encoding="unicode")
    (d / FILES["bt"]).write_text(
        '<?xml version="1.0"?>\n' + bt + "\n", encoding="utf-8"
    )
    return d


__all__ = [
    "FILES",
    "IMAS_TO_PCS_IP_SIGN",
    "PscSpec",
    "build_btree",
    "build_globmon",
    "build_interface",
    "build_schedule",
    "parse_psc",
    "write_psc_config",
]
