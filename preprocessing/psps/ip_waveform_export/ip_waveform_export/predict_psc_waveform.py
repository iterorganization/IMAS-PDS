"""PROPOSAL tool: predict the reference the PSC emits for given event times.

Given a designer YAML (the converter format read by ``read_yaml.load_design``)
and the times at which events fire, this module replays, tick by tick, what
the Pulse Supervision Controller (PSC, pcssp-nightly ``merge_IGZ_PSC``
ebf3ee0, ``src/psc/``; unmerged line) does with the four configuration files
written by ``export_psc_config`` (or with an existing ``psc_config_*`` folder),
and returns the waveform signal (``Ipl_ref``, positive PCS frame) together with
the active segment and the active overlays.

It is a Python port of the classes that decide the reference, not a model of
them. Every rule below has its counterpart in the MATLAB code (paths relative
to ``pcssp-nightly@ebf3ee0:src/psc/``):

Tick (``PSCSysObj.m:125-150``, ``+PSC/PSCClass.m:90-114``)
    ``lastTimeDiff = t - LastExecTime`` (0 at the first tick); if the
    ``current_segment`` left by the previous tick differs from the stored one,
    the path bookkeeping is cleared (``RefGenerator.resetPathHandler``,
    PSCSysObj.m:136-141; the signal generators keep their trajectory stacks);
    ``last_mod_segment = 0``; global monitoring (here: the given event
    intervals set the flags ``glb_ps__<event>``); one tick of the behaviour
    tree; ``RefGenerator.execute(lastTimeDiff)`` (generate every output, then
    ``PathHandler.getStatusReferences``). Sample time 0.001 s:
    ``PSC.slx:simulink/systems/system_root.xml`` block PSCMatSys SID 554
    ``sampleTime 0.001``; simulation time ``t_k = k * dt`` (derived: Simulink
    fixed step).
Behaviour tree (``+BT/+BASICS/*.m``)
    Fallback (reactive), Parallel (threshold, mainTask), Sequence,
    Precondition, ForceFailure, ``AssignValue`` and ``RefGen`` actions, with the
    status codes 0 idle, 1 running, 2 success, 3 failure and the reset rules of
    FallbackClass, ParallelClass, SequenceClass, PreconditionClass,
    ForceFailureClass and ActExtClass. ``SubTree`` is replaced by the
    referenced tree (derived). Conditions: ``{x}`` -> blackboard value,
    ``and``/``or``/``!=`` as ``HELPERS/ScriptExecClass.m`` rewrites them.
RefGen action (``+BT/+GENNodes/RefGenClass.m:67-138``)
    path status 0 -> command the RefGen, a ``replace`` path sets
    ``current_segment`` to its id; status 3 (watchdog) -> ``current_segment =
    wd_target`` (also for an overlay); status 2 (condition) -> overlay done.
Paths (``+REFGEN/+MODEL/PathHandler.m``)
    ``addNewCommand`` (new path -> ``SignalGenClass.load``; known path ->
    ``reactivate``, which does not reload the trajectory), ``getStatusPath``
    (condition -> 2 and removal; all trajectories of the path finished -> 3 and
    removal), idle reset after 5 ticks without a call (``maxCycleIdle``,
    ``getStatusReferences``).
Signal generator (``+REFGEN/+MODEL/SignalGenClass.m``)
    stack ``baseName``: ``replace`` overwrites the top (l.189-200), ``*,replace``
    pushes an overlay on top (l.205-214), ``*,offset`` / ``*,scale`` register a
    modifier (l.216-241); a segment without a trajectory of the signal holds
    ``lastValue`` (l.164-170, always a Step entry); under a ``silence`` overlay
    the second stack element keeps its time running (l.399-410), not the
    deeper ones; composition ``Value = base .* scale + offset`` (l.437);
    entry blend ``transitionValue`` (l.457-472) from the last emitted value,
    ``maxTransitionTime`` 0.5 s (l.51), stop test ``abs(diff) <= 0.05 *
    CurrentValue`` (true only for positive targets; for a target <= 0 the blend
    runs until the 0.5 s are used up).
Trajectory (``+REFGEN/+TRAJ/trajGenClass.m:97-182``)
    ``LocalTime += timeDiff`` before evaluating; EXECUTION_RULE ``Step`` holds
    the previous point, otherwise linear; past the last point EXIT_RULE
    ``Loop`` loops, anything else holds the last value; watchdog
    ``LocalTime >= wd_time`` -> state 2. Rule strings as
    ``+REFGEN/+MODEL/RefGenerator.m:144-171`` maps them (case sensitive).

Every output signal of the schedule is simulated (vectors as numpy arrays,
MATLAB ``if`` on an array = all elements true), because path states are
computed over all signals of a path. Only the waveform signal is reported.

Not reproduced (see README): the global-monitoring scripts (the event times
are inputs), expression (FUNCTION) trajectories, anonymous RefGen commands,
``AssignValue`` with fields/indices, the ``freezeTraj`` API.
``BTreeClass.tickroot`` (``+BT/+BASICS/BTreeClass.m:105-108``) calls
``RefGenObj.execute()`` without a time step; it is not reproduced: the run of
2026-11-16 shows exactly one RefGen time step per tick (2.001 s and 4.501 s
between watchdog transitions of 2 s and 4.5 s paths). UNVERIFIED why.

Time: events and outputs are in designer time; the PSC clock is
``t_psc = t_designer - t0`` with ``t0`` = the cut time (D20) or the start of
the first segment.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import yaml

#: PSC sample time (PSC.slx@ebf3ee0 system_root.xml, PSCMatSys SID 554).
DT_PSC = 0.001
#: SignalGenClass.m:51
MAX_TRANSITION_TIME = 0.5
#: PathHandler.m:40-41
MAX_CYCLE_IDLE = 5
RATIO_FINISHED = 2
#: tolerance for comparing event times with the tick grid (s)
EVENT_TOL = 1e-9
#: Ip_ref column of simulink_log.csv = -Ipl_ref (controller model
#: pcssp_controller_and_ps_mcls.slx system_root.xml: BusSelector3 SID 2689
#: psc_ref__Ipl_ref -> Gain SID 2690 (-1) -> Variant Source SID 2691)
LOG_IP_REF_SIGN = -1.0

Value = float | np.ndarray


# --------------------------------------------------------------------------- helpers
def _all(x) -> bool:
    """MATLAB ``if`` on an array: true when every element is true."""
    return bool(np.all(x))


def _parse_value(text: str) -> Value:
    s = text.strip()
    if s[:1] in "[(":
        parts = [p for p in re.split(r"[\s,;]+", s.strip("[]()")) if p]
        return np.array([float(p) for p in parts])
    return float(s)


def _copy(v: Value) -> Value:
    return v.copy() if isinstance(v, np.ndarray) else v


# --------------------------------------------------------------------------- trajGenClass
class TrajGen:
    """Port of ``+REFGEN/+TRAJ/trajGenClass.m``."""

    def __init__(
        self, values: list[tuple[float, Value]], execution: int, exit_: int, wd: float
    ):
        self.values = values
        self.n = len(values)
        self.execution = execution
        self.exit = exit_
        self.wd = wd
        self.last_time = values[-1][0]
        self.local_time = 0.0
        self.state = 0
        self.wd_loop = False
        self.last_value: Value = 0.0

    def reset(self) -> None:  # l.61-65
        self.state = 0
        self.local_time = 0.0
        self.wd_loop = False

    def add_time(self, dt: float) -> None:  # l.146-148
        self.local_time += dt

    def generate(self, dt: float) -> tuple[Value, int]:  # l.97-142
        self.local_time += dt
        wd_over = False
        if self.wd > 0 and (self.local_time >= self.wd or self.wd_loop):
            wd_over = True
        if self.n == 1:
            value = self.values[0][1]
        elif self.local_time > self.last_time:
            if self.exit == 1:  # loop
                self.wd_loop = True
                self.local_time -= self.last_time
                value = self._value(self._range())
            else:  # last value (exit rule 2 "default" is never set by RefGenerator)
                value = self.values[-1][1]
        else:
            value = self._value(self._range())
        self.state = 2 if wd_over else 1
        self.last_value = value
        return value, self.state

    def _range(self) -> tuple[int, int]:  # l.151-165, 1-based indices
        times = [p[0] for p in self.values]
        later = [t for t in times if t >= self.local_time]
        if not later:
            return self.n, 0
        i2 = times.index(later[0]) + 1
        if i2 == 1:
            return 0, 1
        return i2 - 1, i2

    def _value(self, r: tuple[int, int]) -> Value:  # l.167-182
        if r[0] == 0:
            return self.values[0][1]
        x1, y1 = self.values[r[0] - 1]
        if self.execution == 0:
            return y1
        x2, y2 = self.values[r[1] - 1]
        dx = x2 - x1
        return ((self.local_time - x1) * (y2 - y1) + y1 * dx) / dx


# --------------------------------------------------------------------------- SignalGenClass
@dataclass
class KnownTraj:
    """One SIGNAL_TRAJECTORY of PS.xml, rules mapped as RefGenerator.m:144-171."""

    values: list[tuple[float, Value]]
    entry: int
    execution: int
    exit: int


@dataclass
class TrajEntry:
    wd: float
    traj: TrajGen
    value: Value
    state: int
    entry: int
    rplc_on_top: bool
    trans_time: float
    base_frozen: bool


@dataclass
class Command:
    """A RefGen action of the behaviour tree (Action ID="RefGen")."""

    name: str
    signals: list[str]
    segment_id: int
    type_addition: list[str]
    wd_time: float
    wd_target: int
    entry: int | None = None
    condition: str | None = None

    @property
    def is_base(self) -> bool:  # RefGenClass.m:42-46
        return "replace" in self.type_addition[0]


class SignalGen:
    """Port of ``+REFGEN/+MODEL/SignalGenClass.m`` (subset used by the PSC files)."""

    def __init__(self, name: str, known: dict[int, KnownTraj], default: Value):
        self.name = name
        self.known = known
        self.default = default
        self.reset_all()

    def reset_all(self) -> None:  # resetSignalRef(0), l.280-295
        self.ts: dict[str, TrajEntry] = {}
        self.base: list[str] = []
        self.offset_name = ""
        self.scale_name = ""
        self.offset_obj = False
        self.scale_obj = False
        self.base_frozen = False
        self.last_value: Value = _copy(self.default)

    def load(self, cmd: Command) -> None:  # l.87-249
        self.base_frozen = False
        transition = 0
        wd = cmd.wd_time if cmd.wd_time > 0 else 0.0
        k = self.known.get(cmd.segment_id)
        if k is not None:
            if not wd > 0:
                raise ValueError(
                    f"path {cmd.name}: no watchdog (SignalGenClass.m:151-153)"
                )
            traj = TrajGen(k.values, k.execution, k.exit, wd)
            transition = cmd.entry if cmd.entry is not None else k.entry
        else:  # the signal is not defined in this segment: hold lastValue, Step
            traj = TrajGen([(0.0, _copy(self.last_value))], 0, 0, wd)
        ta = cmd.type_addition
        e = TrajEntry(
            wd, traj, _copy(self.last_value), 1, transition, False, 0.0, False
        )
        if ta[0] == "replace":
            if self.base:
                self.base[0] = cmd.name
            else:
                self.base = [cmd.name]
        else:
            self.base_frozen = ta[0] == "freeze"
            e.base_frozen = self.base_frozen
            if ta[1] == "replace":
                self.base = [cmd.name, *self.base]
                e.rplc_on_top = True
            else:
                e.value = 0.0
                if ta[1] == "offset":
                    self.offset_obj, self.offset_name = True, cmd.name
                elif ta[1] == "scale":
                    self.scale_obj, self.scale_name = True, cmd.name
                else:
                    raise ValueError(f"wrong typeAddition {ta} for {self.name}")
        e.trans_time = 0.0 if transition == 0 else MAX_TRANSITION_TIME
        self.ts[cmd.name] = e

    def _drop(self, path: str, addition: int) -> None:  # removeTraj l.316-329
        if addition in (0, 3):
            self.base = [b for b in self.base if b != path]
        elif addition == 1:
            self.offset_name, self.offset_obj = "", False
        elif addition == 2:
            self.scale_name, self.scale_obj = "", False

    def remove_traj(self, path: str, addition: int) -> None:
        self._drop(path, addition)

    def reset_traj(self, path: str, addition: int) -> None:  # l.331-347
        self._drop(path, addition)
        self.ts[path].traj.reset()
        self.ts[path].state = 0

    def reactivate(self, path: str, addition: int) -> None:  # l.349-364
        if addition == 0:
            self.base = [path]
        elif addition == 1:
            self.offset_name, self.offset_obj = path, True
        elif addition == 2:
            self.scale_name, self.scale_obj = path, True
        else:
            self.base = [path, *self.base]
        self.ts[path].traj.reset()
        self.ts[path].state = 0

    def generate(self, dt: float) -> Value:  # l.252-266, 391-441
        if not self.base:
            return self.last_value
        base_dt = 0.0 if self.base_frozen else dt
        top = self.ts[self.base[0]]
        if top.rplc_on_top and len(self.base) > 1 and not top.base_frozen:
            self.ts[self.base[1]].traj.add_time(base_dt)
        scale: Value = 1.0
        if self.scale_obj:
            scale = self._gen(self.scale_name, dt)
        offset: Value = 0.0
        if self.offset_obj:
            offset = self._gen(self.offset_name, dt)
        base = self._gen(self.base[0], dt)
        self.last_value = base * scale + offset  # l.437 (isScaleFirst)
        return self.last_value

    def _gen(self, path: str, dt: float) -> Value:
        e = self.ts[path]
        v, st = e.traj.generate(dt)
        v = self._transition(v, e, dt)
        e.state = st
        return v

    @staticmethod
    def _transition(cur: Value, e: TrajEntry, dt: float) -> Value:  # l.457-472
        if e.trans_time == 0:
            e.value = _copy(cur)
        else:
            diff = cur - e.value
            if _all(np.abs(diff) <= 0.05 * cur):
                e.value = _copy(cur)
                e.trans_time = 0.0
            else:
                ratio = e.trans_time / dt if dt > 0 else math.inf
                cycles = max(1.0, ratio)
                e.value = e.value + diff / cycles
                e.trans_time = max(0.0, e.trans_time - dt)
        return _copy(e.value)


# --------------------------------------------------------------------------- PathHandler / RefGenerator
@dataclass
class PathRec:
    signals: list[str]
    addition: int
    condition: Callable[[], bool] | None
    checked: int = MAX_CYCLE_IDLE


class RefGen:
    """Port of ``RefGenerator.m`` + ``PathHandler.m``."""

    def __init__(self, gens: dict[str, SignalGen], cond: Callable[[str], Callable]):
        self.gens = gens
        self.paths: dict[str, PathRec] = {}
        self._cond = cond

    def command(self, cmd: Command) -> None:  # commandSignals + addNewCommand
        ta = cmd.type_addition
        if ta[0] == "replace":
            if len(ta) > 1:
                raise ValueError("'replace' takes no further option (RefGenerator.m)")
            addition = 0
        else:
            if ta[0] not in ("freeze", "silence") or len(ta) < 2:
                raise ValueError(f"invalid typeAddition {ta}")
            addition = {"offset": 1, "scale": 2, "replace": 3}.get(ta[1])
            if addition is None:
                raise ValueError(f"invalid typeAddition {ta}")
        signals = list(self.gens) if cmd.signals == ["all"] else cmd.signals
        p = self.paths.get(cmd.name)
        if p is not None:
            for s in p.signals:
                self.gens[s].reactivate(cmd.name, addition)
        else:
            cond = self._cond(cmd.condition) if cmd.condition else None
            p = PathRec(signals, addition, cond)
            self.paths[cmd.name] = p
            for s in signals:
                self.gens[s].load(cmd)
        p.checked = MAX_CYCLE_IDLE

    def status(self, name: str) -> int:  # getStatusPath l.115-159
        p = self.paths.get(name)
        if p is None:
            return 0
        if p.condition is not None and p.condition():
            for s in p.signals:
                self.gens[s].remove_traj(name, p.addition)
            return 2
        arr = [0, 0, 0]
        for s in p.signals:
            arr[self.gens[s].ts[name].state] += 1
        total = arr[1] + arr[2]
        if total > 0:
            if 1 + arr[2] / total >= RATIO_FINISHED:
                st = 3
                for s in p.signals:
                    self.gens[s].remove_traj(name, p.addition)
            else:
                st = 1
        else:
            st = 0
        p.checked = MAX_CYCLE_IDLE
        return st

    def execute(self, dt: float) -> None:  # RefGenerator.execute l.78-85
        self.generate_all(dt)
        self.status_references()

    def generate_all(self, dt: float) -> None:
        for g in self.gens.values():
            g.generate(dt)

    def status_references(self) -> None:  # getStatusReferences l.162-181
        for name, p in self.paths.items():
            if p.checked > -1:
                p.checked -= 1
                if p.checked < 1:
                    for s in p.signals:
                        self.gens[s].reset_traj(name, p.addition)
                    p.checked = -1

    def reset_paths(self) -> None:  # resetPathHandler
        self.paths = {}


# --------------------------------------------------------------------------- behaviour tree
class Node:
    def __init__(self, children: list[Node] | None = None):
        self.children = children or []
        self.status = 0
        self.current = 0

    def tick(self, ctx: Psc) -> int:
        raise NotImplementedError

    def reset(self) -> None:
        self.status = 0


class Fallback(Node):  # FallbackClass.m
    def __init__(self, children, reactive: bool):
        super().__init__(children)
        self.reactive = reactive

    def reset(self):
        self.current = 0
        self.status = 0

    def tick(self, ctx):
        first = 0 if self.reactive else self.current
        for i in range(first, len(self.children)):
            st = self.children[i].tick(ctx)
            if st == 1:
                if self.current != i:
                    self.children[self.current].reset()
                self.current = i
                self.status = 1
                return 1
            if st == 2:
                self.status, self.current = 2, 0
                for c in self.children:
                    c.reset()
                return 2
        self.status, self.current = 3, 0
        for c in self.children:
            c.reset()
        return 3


class Parallel(Node):  # ParallelClass.m
    def __init__(self, children, threshold: int, main: int):
        super().__init__(children)
        self.min_success = len(children) if threshold == -1 else threshold
        self.main = main

    def reset(self):
        self.status = 0
        for c in self.children:
            c.reset()

    def tick(self, ctx):
        sts = [c.tick(ctx) for c in self.children]
        if self.main == -1:
            if 1 in sts:
                self.status = 1
            else:
                self.status = 2 if sts.count(2) >= self.min_success else 3
        else:
            self.status = sts[self.main - 1]
        if self.status > 1:
            for c in self.children:
                c.reset()
        return self.status


class SequenceNode(Node):  # SequenceClass.m
    def reset(self):
        self.current = 0
        self.status = 0

    def tick(self, ctx):
        for i in range(self.current, len(self.children)):
            st = self.children[i].tick(ctx)
            if st == 1:
                self.status, self.current = 1, i
                return 1
            if st == 3:
                self.status = 3
                for c in self.children:
                    if c.status > 0:
                        c.reset()
                return 3
        self.status = 2
        for c in self.children:
            c.reset()
        return 2


class Precondition(Node):  # PreconditionClass.m
    def __init__(self, children, condition: str):
        super().__init__(children)
        self.condition = condition
        self.func: Callable[[], bool] | None = None

    def tick(self, ctx):
        if self.func is None:
            self.func = ctx.compile(self.condition)
        if self.func():
            self.children[0].tick(ctx)
            self.status = self.children[0].status
        else:
            self.status = 3
        self.children[0].reset()
        return self.status


class ForceFailure(Node):  # ForceFailureClass.m
    def tick(self, ctx):
        self.children[0].tick(ctx)
        self.status = 3
        self.children[0].reset()
        return 3


class Action(Node):  # ActExtClass.m: reset only when finished
    def reset(self):
        if self.status > 1:
            self.status = 0


class AssignValue(Action):  # AssignValueClass.m (scalar blackboard variables)
    def __init__(self, source: str, target: str):
        super().__init__()
        self.source, self.target = source, target

    def tick(self, ctx):
        ctx.bb[_var(self.target)] = (
            ctx.bb[_var(self.source)]
            if self.source.startswith("{")
            else float(self.source)
        )
        self.status = 2
        return 2


class RefGenAction(Action):  # RefGenClass.m:67-138
    def __init__(self, cmd: Command):
        super().__init__()
        self.cmd = cmd

    def tick(self, ctx):
        c, bb, rg = self.cmd, ctx.bb, ctx.refgen
        st = rg.status(c.name)
        if st == 0:
            rg.command(c)
            if c.is_base:
                bb["old_current_segment"] = bb["current_segment"]
                bb["current_segment"] = c.segment_id
            else:
                bb["old_mod_segment"] = bb["last_mod_segment"]
                bb["last_mod_segment"] = c.segment_id
            st = rg.status(c.name)
        if st == 2:
            if c.is_base:
                bb["old_current_segment"] = bb["current_segment"]
                bb["current_segment"] = c.segment_id
            else:
                bb["old_mod_segment"] = c.segment_id
                bb["last_mod_segment"] = 0
        elif st == 3:
            bb["old_current_segment"] = bb["current_segment"]
            bb["current_segment"] = c.wd_target
        elif c.is_base:
            bb["current_segment"] = c.segment_id
        else:
            bb["last_mod_segment"] = c.segment_id
        self.status = st
        return st


def _var(ref: str) -> str:
    return ref.strip().strip("{}").split(".")[0]


def _entry_rule(text: str | None) -> int | None:  # SignalGenClass.m:117-133
    if text is None:
        return None
    if text == "Step":
        return 0
    if text == "Linear":
        return 1
    return 0  # "Entry rule not recognised" -> 0


def parse_btree(root: ET.Element, signal_names: Sequence[str]) -> Node:
    """Build the node tree of a Groot BTree.xml as the PSC parser reads it."""
    trees = {bt.get("ID"): bt for bt in root.findall("BehaviorTree")}
    main = trees[root.get("main_tree_to_execute", "BehaviorTree")]

    def build(el: ET.Element) -> Node:
        tag = el.tag
        kids = [build(c) for c in el if isinstance(c.tag, str)]
        a = el.attrib
        if tag == "Fallback":
            return Fallback(kids, a.get("Reactive", "1") == "1")
        if tag == "Parallel":
            return Parallel(
                kids, int(a.get("threshold", "0")), int(a.get("mainTask", "-1"))
            )
        if tag == "Sequence":
            return SequenceNode(kids)
        if tag == "Precondition":
            return Precondition(kids, a["condition"])
        if tag == "ForceFailure":
            return ForceFailure(kids)
        if tag == "SubTree":
            sub = [c for c in trees[a["ID"]] if isinstance(c.tag, str)]
            if len(sub) != 1:
                raise ValueError(f"SubTree {a['ID']}: one root node expected")
            return build(sub[0])
        if tag == "Action" and a.get("ID") == "AssignValue":
            return AssignValue(a["source"], a["target"])
        if tag == "Action" and a.get("ID") == "RefGen":
            sig = a.get("signal", "all")
            sigs = ["all"] if sig == "all" else [s.strip() for s in sig.split(",")]
            for s in sigs:
                if s != "all" and s not in signal_names:
                    raise ValueError(f"RefGen {a.get('name')}: signal {s} not declared")
            return RefGenAction(
                Command(
                    name=a["name"],
                    signals=sigs,
                    segment_id=int(float(a["segmentID"])),
                    type_addition=[t.strip() for t in a["typeAddition"].split(",")],
                    wd_time=float(a.get("wd_time", "0")),
                    wd_target=int(float(a["wd_target"])),
                    entry=_entry_rule(a.get("entryRule")),
                    condition=a.get("condition"),
                )
            )
        raise ValueError(f"behaviour-tree node {tag} {a} not supported")

    nodes = [c for c in main if isinstance(c.tag, str)]
    if len(nodes) != 1:
        raise ValueError("the main BehaviorTree must have one root node")
    return build(nodes[0])


# --------------------------------------------------------------------------- schedule
@dataclass
class Schedule:
    """What the simulation needs from PS.xml."""

    defaults: dict[str, Value]
    known: dict[str, dict[int, KnownTraj]]
    segment_names: dict[int, str]


def _rule(el: ET.Element, tag: str) -> str | None:
    r = el.find(tag)
    return None if r is None else r.get("is")


def parse_schedule(root: ET.Element) -> Schedule:
    """Read PS.xml with the rule mapping of RefGenerator.createSignalGen."""
    defaults: dict[str, Value] = {}
    for s in root.findall("DECLARATIONS/OUTPUTS/SIGNAL"):
        defaults[s.get("name", "")] = _parse_value(s.get("value", "0"))
    known: dict[str, dict[int, KnownTraj]] = {n: {} for n in defaults}
    names: dict[int, str] = {}
    for seg in root.findall("SEGMENTS/SEGMENT"):
        sid = int(float(seg.get("id", "nan")))
        names[sid] = seg.get("name", str(sid))
        for tr in seg.findall("SIGNAL_TRAJECTORIES/SIGNAL_TRAJECTORY"):
            sig = tr.get("name", "")
            if sig not in known:
                raise ValueError(f"segment {names[sid]}: signal {sig} not declared")
            pts = tr.findall("REFERENCE/POINT")
            if not pts:
                raise NotImplementedError(
                    f"segment {names[sid]}, {sig}: only POINT references are supported"
                )
            values = [
                (float(p.get("time", "nan")), _parse_value(p.get("value", "nan")))
                for p in pts
            ]
            entry, execution, exit_ = (
                _rule(tr, "ENTRY_RULE"),
                _rule(tr, "EXECUTION_RULE"),
                _rule(tr, "EXIT_RULE"),
            )
            known[sig][sid] = KnownTraj(
                values,
                entry=1 if entry is None or entry != "Step" else 0,
                execution=1 if execution is None or execution != "Step" else 0,
                exit=1 if exit_ == "Loop" else 0,
            )
    return Schedule(defaults, known, names)


def interface_default_segment(root: ET.Element) -> int:
    """Default of ``current_segment`` in PSCIntConfig.xml."""
    for u in root.findall("USAGE"):
        if u.get("name") == "current_segment":
            s = u.find("SIGNAL")
            if s is not None:
                return int(float(s.get("value", "0")))
    raise ValueError("PSCIntConfig.xml: no current_segment")


# --------------------------------------------------------------------------- simulator
Intervals = dict[str, list[tuple[float, float | None]]]


class Psc:
    """One PSC instance: blackboard, behaviour tree, reference generator."""

    def __init__(
        self,
        schedule: Schedule,
        btree: ET.Element,
        first_segment: int,
        events: Intervals,
    ):
        self.schedule = schedule
        self.bb: dict[str, float] = {
            "current_segment": first_segment,
            "old_current_segment": 0,
            "last_mod_segment": 0,
            "old_mod_segment": 0,
        }
        self.events = events
        for e in events:
            self.bb[f"glb_ps__{e}"] = 0
        gens = {
            n: SignalGen(n, schedule.known[n], schedule.defaults[n])
            for n in schedule.defaults
        }
        self.refgen = RefGen(gens, self.compile)
        self.root = parse_btree(btree, list(gens))
        self.stored_segment = 0  # PSCSysObj currentSegment property default
        self.last_exec = 0.0

    def compile(self, expr: str) -> Callable[[], bool]:
        """Condition of a Precondition / RefGen path (ScriptExecClass syntax)."""
        names = re.findall(r"\{([^}]*)\}", expr)
        py = expr.replace("!=", "~=")
        for n in names:
            key = _var(n)
            if key not in self.bb:
                if key.startswith("glb_ps__"):
                    self.bb[key] = 0  # an event that is never given: flag stays 0
                else:
                    raise ValueError(
                        f"condition {expr!r}: {key} is not a blackboard variable known "
                        "to the predictor (only segments and event flags are modelled)"
                    )
            py = py.replace("{" + n + "}", f"bb[{key!r}]")
        py = py.replace("~=", "!=")
        code = compile(py, "<condition>", "eval")
        bb = self.bb
        return lambda: bool(eval(code, {"__builtins__": {}, "abs": abs}, {"bb": bb}))

    def step(
        self,
        t_psc: float,
        t_designer: float,
        snapshot: Callable[[], None] | None = None,
    ) -> None:
        """One PSC tick; ``snapshot`` is called after the outputs are generated
        and before the idle-path bookkeeping (what produced this tick's value)."""
        dt = t_psc - self.last_exec  # PSCSysObj.m:130-131
        self.last_exec = t_psc
        cur = self.bb["current_segment"]
        if cur != self.stored_segment:  # PSCSysObj.m:135-141
            self.stored_segment = cur
            self.refgen.reset_paths()
        self.bb["last_mod_segment"] = 0  # PSCClass.m:98-101
        for e, ivs in self.events.items():  # global monitoring replaced by inputs
            on = any(
                t_designer >= a - EVENT_TOL
                and (b is None or t_designer < b - EVENT_TOL)
                for a, b in ivs
            )
            self.bb[f"glb_ps__{e}"] = 1 if on else 0
        self.root.tick(self)
        self.refgen.generate_all(dt)
        if snapshot is not None:
            snapshot()
        self.refgen.status_references()


@dataclass
class Prediction:
    time: np.ndarray  # designer time (s)
    t_psc: np.ndarray
    value: np.ndarray  # waveform signal, PCS frame
    segment_id: np.ndarray
    segment_name: list[str]
    active_path: list[str]
    overlays: list[str]
    signal: str = "Ipl_ref"
    t0: float = 0.0
    events: Intervals = field(default_factory=dict)

    def write_csv(self, path: str | Path) -> Path:
        path = Path(path)
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "time_s",
                    "t_psc_s",
                    f"{self.signal}_A",
                    "segment_id",
                    "segment_name",
                    "active_path",
                    "overlays",
                ]
            )
            for i in range(self.time.size):
                w.writerow(
                    [
                        f"{self.time[i]:.6f}",
                        f"{self.t_psc[i]:.6f}",
                        repr(float(self.value[i])),
                        int(self.segment_id[i]),
                        self.segment_name[i],
                        self.active_path[i],
                        self.overlays[i],
                    ]
                )
        return path


def simulate(
    schedule: Schedule,
    btree: ET.Element,
    first_segment: int,
    events: Intervals,
    t0: float,
    t_end: float,
    signal: str = "Ipl_ref",
    dt: float = DT_PSC,
) -> Prediction:
    """Replay the PSC from designer time ``t0`` (PSC clock 0) to ``t_end``."""
    if signal not in schedule.defaults:
        raise ValueError(f"signal {signal} is not an output of the schedule")
    psc = Psc(schedule, btree, first_segment, events)
    n = round((t_end - t0) / dt) + 1
    seg_of_path = {}
    stack = [psc.root]
    while stack:
        nd = stack.pop()
        if isinstance(nd, RefGenAction):
            seg_of_path[nd.cmd.name] = schedule.segment_names.get(
                nd.cmd.segment_id, str(nd.cmd.segment_id)
            )
        stack.extend(nd.children)
    gen = psc.refgen.gens[signal]
    vals = np.empty(n)
    segs = np.empty(n, dtype=int)
    names, active, overlays = [], [], []
    tp = np.arange(n) * dt  # Simulink fixed step t_k = k * h (derived)
    snap: list[tuple[str, str]] = []

    def take() -> None:
        top = gen.base[0] if gen.base else ""
        ov = [seg_of_path.get(b, b) for b in gen.base if gen.ts[b].rplc_on_top]
        if gen.offset_obj:
            ov.append(seg_of_path.get(gen.offset_name, gen.offset_name) + "(offset)")
        if gen.scale_obj:
            ov.append(seg_of_path.get(gen.scale_name, gen.scale_name) + "(scale)")
        snap.append((seg_of_path.get(top, top), ";".join(ov)))

    for k in range(n):
        snap.clear()
        psc.step(float(tp[k]), t0 + float(tp[k]), take)
        v = gen.last_value
        vals[k] = float(np.asarray(v).ravel()[0]) if isinstance(v, np.ndarray) else v
        cs = int(psc.bb["current_segment"])
        segs[k] = cs
        names.append(schedule.segment_names.get(cs, str(cs)))
        active.append(snap[0][0])
        overlays.append(snap[0][1])
    return Prediction(
        t0 + tp, tp, vals, segs, names, active, overlays, signal, t0, events
    )


# --------------------------------------------------------------------------- inputs
def parse_event_spec(spec: str) -> tuple[str, float, float | None]:
    """``name=t_on`` or ``name=t_on:until=t_off`` (designer time, s)."""
    m = re.fullmatch(
        r"\s*([A-Za-z_]\w*)\s*=\s*([^:\s]+)\s*(?::\s*until\s*=\s*([^\s]+)\s*)?", spec
    )
    if not m:
        raise ValueError(f"event spec {spec!r}: expected name=t_on[:until=t_off]")
    on = float(m.group(2))
    off = float(m.group(3)) if m.group(3) is not None else None
    if off is not None and not off > on:
        raise ValueError(f"event spec {spec!r}: until must be after the event time")
    return m.group(1), on, off


def add_interval(ev: Intervals, name: str, on: float, off: float | None) -> None:
    ev.setdefault(name, []).append((on, off))


def load_events_yaml(path: str | Path) -> Intervals:
    """``events: {name: t | [t, ...] | [{at: t, until: t2}, ...]}`` (designer time)."""
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw = doc.get("events", doc)
    ev: Intervals = {}
    for name, val in (raw or {}).items():
        items = val if isinstance(val, list) else [val]
        for it in items:
            if isinstance(it, dict):
                off = it.get("until")
                # "at" (YAML 1.1 reads a bare key "on" as boolean True: accept both)
                on = it.get("at", it.get("on", it.get(True)))
                if on is None:
                    raise ValueError(f"events.{name}: entry {it} needs 'at'")
                add_interval(
                    ev, str(name), float(on), None if off is None else float(off)
                )
            else:
                add_interval(ev, str(name), float(it), None)
    return ev


def read_log(path: str | Path, columns: Sequence[str]) -> dict[str, np.ndarray]:
    """Read selected columns of a PDS ``simulink_log.csv``."""
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        hdr = f.readline().strip().split(",")
    missing = [c for c in columns if c not in hdr]
    if missing:
        raise ValueError(f"{path}: columns {missing} not found")
    idx = [hdr.index(c) for c in columns]
    data = np.genfromtxt(path, delimiter=",", skip_header=1, usecols=idx)
    data = np.atleast_2d(data)
    return {c: data[:, i] for i, c in enumerate(columns)}


def events_from_log(path: str | Path, names: Sequence[str]) -> Intervals:
    """Event intervals from the ``psc_<event>`` flag columns of simulink_log.csv."""
    cols = read_log(path, ["t", *[f"psc_{n}" for n in names]])
    t = cols["t"]
    ev: Intervals = {}
    for n in names:
        f = cols[f"psc_{n}"] > 0.5
        on = None
        for i in range(t.size):
            if f[i] and on is None:
                on = float(t[i])
            elif not f[i] and on is not None:
                add_interval(ev, n, on, float(t[i]))
                on = None
        if on is not None:
            add_interval(ev, n, on, None)
        ev.setdefault(n, [])
    return ev


def flag_names(btree: ET.Element) -> list[str]:
    """Event names referenced by the behaviour tree (``glb_ps__<event>``)."""
    found: list[str] = []
    for el in btree.iter():
        for v in el.attrib.values():
            for m in re.findall(r"\{glb_ps__(\w+)\}", v):
                if m not in found:
                    found.append(m)
    return found


def psc_inputs_from_design(design) -> tuple[ET.Element, ET.Element, int]:
    """PS.xml root, BTree.xml root and current_segment default as
    ``export_psc_config.write_psc_config`` would write them."""
    from .export_psc_config import build_btree, build_schedule, parse_psc

    spec = parse_psc(design)
    ps = build_schedule(design, spec).getroot()
    bt = build_btree(design, spec)
    return ps, bt, design.segments[0].id


def psc_inputs_from_dir(d: str | Path) -> tuple[ET.Element, ET.Element, int]:
    d = Path(d)
    ps = ET.parse(d / "PS.xml").getroot()
    bt = ET.parse(d / "BTree.xml").getroot()
    first = interface_default_segment(ET.parse(d / "PSCIntConfig.xml").getroot())
    return ps, bt, first


def predict(
    design,
    events: Intervals,
    t_end: float | None = None,
    psc_config_dir: str | Path | None = None,
    t0: float | None = None,
    dt: float = DT_PSC,
) -> Prediction:
    """Importable entry point.

    ``design``: a (cut) ``PulseDesign``; the PSC files are generated in memory by
    ``export_psc_config`` unless ``psc_config_dir`` names an existing folder.
    ``events``: name -> [(t_on, t_off or None)] in designer time.
    ``t0``: designer time of PSC clock 0 (default: ``design.cut_at`` or the start
    of the first segment). ``t_end``: default the end of the nominal schedule.
    """
    if psc_config_dir is None:
        ps, bt, first = psc_inputs_from_design(design)
    else:
        ps, bt, first = psc_inputs_from_dir(psc_config_dir)
    timed = design.timed_segments
    if t0 is None:
        t0 = design.cut_at if design.cut_at is not None else timed[0].start
    if t_end is None:
        t_end = timed[-1].end
    known = flag_names(bt)
    unknown = [e for e in events if e not in known]
    if unknown:
        raise ValueError(
            f"events {unknown} are not used by the behaviour tree (known: {known})"
        )
    ev = {k: list(events.get(k, [])) for k in known}
    return simulate(
        parse_schedule(ps),
        bt,
        first,
        ev,
        float(t0),
        float(t_end),
        design.waveform.signal_name,
        dt,
    )


# --------------------------------------------------------------------------- comparison / plot
def compare(
    pred: Prediction, t_ref: np.ndarray, v_ref: np.ndarray, t_max: float | None = None
) -> dict:
    """Max |pred - ref| per active path and in total, on the common ticks."""
    keep = t_ref <= (t_max if t_max is not None else np.inf) + EVENT_TOL
    t_ref, v_ref = t_ref[keep], v_ref[keep]
    idx = np.rint((t_ref - pred.t0) / (pred.t_psc[1] - pred.t_psc[0])).astype(int)
    ok = (idx >= 0) & (idx < pred.time.size)
    idx, v_ref, t_ref = idx[ok], v_ref[ok], t_ref[ok]
    d = pred.value[idx] - v_ref
    out: dict[str, Any] = {
        "total": float(np.max(np.abs(d))) if d.size else math.nan,
        "t_at_total": float(t_ref[np.argmax(np.abs(d))]) if d.size else math.nan,
        "phases": {},
    }
    labels = np.array([pred.active_path[i] or "-" for i in idx])
    for lab in dict.fromkeys(labels):
        m = labels == lab
        j = np.argmax(np.abs(d[m]))
        out["phases"][str(lab)] = {
            "max_abs": float(np.abs(d[m][j])),
            "t_at_max": float(t_ref[m][j]),
            "t_from": float(t_ref[m][0]),
            "t_to": float(t_ref[m][-1]),
            "n": int(m.sum()),
        }
    return out


def plot(
    pred: Prediction,
    design,
    png: str | Path,
    ref: tuple[np.ndarray, np.ndarray] | None = None,
    title: str | None = None,
) -> Path:
    """Designed nominal vs predicted (vs reference run), landscape 11.7 in, >= 14 pt."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from .export_refgen_xml import IMAS_TO_PCS_IP_SIGN

    plt.rcParams.update({"font.size": 16, "font.family": "DejaVu Sans"})
    nrow = 2 if ref is not None else 1
    fig, axes = plt.subplots(
        nrow,
        1,
        figsize=(11.7, 6.6 if ref is not None else 5.6),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1.3]} if ref is not None else None,
        squeeze=False,
    )
    ax = axes[0, 0]
    wf = design.waveform
    m = (wf.time >= pred.time[0] - 1e-9) & (wf.time <= pred.time[-1] + 1e-9)
    td = np.concatenate(([pred.time[0]], wf.time[m], [pred.time[-1]]))
    vd = IMAS_TO_PCS_IP_SIGN * wf.sample(td)
    ax.plot(td, vd / 1e6, "--", color="#8a8a85", lw=2, label="designed (nominal)")
    if ref is not None:
        ax.plot(ref[0], ref[1] / 1e6, color="#eb6834", lw=5, label="PDS run")
    ax.plot(pred.time, pred.value / 1e6, color="#2a78d6", lw=1.8, label="predicted")
    ymax = max(np.nanmax(pred.value), np.nanmax(vd)) / 1e6
    for ivs in pred.events.values():
        for a, b in ivs:
            ax.axvline(a, color="#444441", lw=1, ls=":")
            if b is not None:
                ax.axvspan(a, b, color="#444441", alpha=0.08, lw=0)
    first = {}
    for name, ivs in pred.events.items():
        if ivs:
            first[name] = ivs[0][0]
    for name, a in sorted(first.items(), key=lambda x: x[1]):
        ax.annotate(
            name,
            (a, 0.03 * ymax),
            fontsize=14,
            ha="left",
            va="bottom",
            rotation=90,
            xytext=(3, 0),
            textcoords="offset points",
            color="#444441",
        )
    ax.set_ylabel(f"{pred.signal} (MA, PCS frame)", fontsize=16)
    ax.set_ylim(bottom=min(0.0, np.nanmin(pred.value) / 1e6), top=ymax * 1.06)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=14, loc="lower right", frameon=False)
    ax.tick_params(labelsize=14)
    if title:
        ax.set_title(title, fontsize=16)
    if ref is not None:
        ax2 = axes[1, 0]
        idx = np.rint((ref[0] - pred.t0) / (pred.t_psc[1] - pred.t_psc[0])).astype(int)
        ok = (idx >= 0) & (idx < pred.time.size)
        ax2.plot(ref[0][ok], pred.value[idx[ok]] - ref[1][ok], color="#2a78d6", lw=1.5)
        ax2.set_ylabel("pred. - run (A)", fontsize=16)
        ax2.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax2.grid(alpha=0.3)
        ax2.tick_params(labelsize=14)
    axes[-1, 0].set_xlabel("time (s, designer time = pulse time)", fontsize=16)
    fig.tight_layout()
    png = Path(png)
    fig.savefig(png, dpi=200)
    plt.close(fig)
    return png


# --------------------------------------------------------------------------- CLI
def main(argv: Sequence[str] | None = None) -> int:
    from .cut import cut_design
    from .model import ValidationError
    from .read_yaml import load_design

    ap = argparse.ArgumentParser(
        prog="python -m ip_waveform_export.predict_psc_waveform",
        description="Predict the PSC reference (Ipl_ref, PCS frame) for given event times.",
    )
    ap.add_argument("--yaml", required=True, help="designer YAML (converter format)")
    ap.add_argument(
        "--cut-at", type=float, help="D20 cut: designer time of PSC clock 0"
    )
    ap.add_argument(
        "--psc-config-dir",
        help="use this psc_config_* folder (PS.xml, BTree.xml, PSCIntConfig.xml) "
        "instead of generating the files from the YAML",
    )
    ap.add_argument(
        "--event",
        action="append",
        default=[],
        help="name=t_on[:until=t_off] in designer time; repeatable",
    )
    ap.add_argument("--events-yaml", help="YAML with an events: mapping")
    ap.add_argument(
        "--t-end", type=float, help="designer end time (default: schedule end)"
    )
    ap.add_argument("--dt", type=float, default=DT_PSC, help="PSC sample time (s)")
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--png", help="figure: designed vs predicted with event markers")
    ap.add_argument(
        "--reference-log",
        help="simulink_log.csv of a PDS run: compare with its Ip_ref (= -Ipl_ref)",
    )
    ap.add_argument(
        "--events-from-log",
        action="store_true",
        help="take the event intervals from the psc_<event> columns of --reference-log",
    )
    ap.add_argument(
        "--compare-until", type=float, help="designer time limit of the comparison"
    )
    a = ap.parse_args(argv)
    try:
        design = load_design(a.yaml)
        if a.cut_at is not None:
            design = cut_design(design, a.cut_at)
        ev: Intervals = {}
        if a.events_yaml:
            ev = load_events_yaml(a.events_yaml)
        for s in a.event:
            add_interval(ev, *parse_event_spec(s))
        if a.events_from_log:
            if not a.reference_log:
                ap.error("--events-from-log needs --reference-log")
            bt = (
                psc_inputs_from_dir(a.psc_config_dir)[1]
                if a.psc_config_dir
                else psc_inputs_from_design(design)[1]
            )
            for k, v in events_from_log(a.reference_log, flag_names(bt)).items():
                for on, off in v:
                    add_interval(ev, k, on, off)
        pred = predict(design, ev, a.t_end, a.psc_config_dir, dt=a.dt)
    except (ValidationError, ValueError, NotImplementedError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    pred.write_csv(a.out_csv)
    print(f"wrote {a.out_csv} ({pred.time.size} ticks, t0 = {pred.t0:.6f} s)")
    for name, ivs in pred.events.items():
        txt = ", ".join(
            f"{on:.6f}" + (f"-{off:.6f}" if off else "-") for on, off in ivs
        )
        print(f"  event {name}: {txt or 'never'}")
    ch = np.nonzero(np.diff(pred.segment_id))[0]
    for i in ch:
        print(
            f"  t = {pred.time[i + 1]:.6f} s: current_segment -> {pred.segment_name[i + 1]}"
        )
    ref = None
    if a.reference_log:
        log = read_log(a.reference_log, ["t", "Ip_ref"])
        ref = (log["t"], LOG_IP_REF_SIGN * log["Ip_ref"])
        res = compare(pred, *ref, t_max=a.compare_until)
        print(
            f"max |predicted - run| = {res['total']:.1f} A at t = {res['t_at_total']:.6f} s"
        )
        for lab, r in res["phases"].items():
            print(
                f"  {lab}: {r['max_abs']:.1f} A at {r['t_at_max']:.6f} s "
                f"({r['t_from']:.3f}-{r['t_to']:.3f} s, {r['n']} ticks)"
            )
    if a.png:
        plot(pred, design, a.png, ref, title=design.name)
        print(f"wrote {a.png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
