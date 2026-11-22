"""predict_psc_waveform: tick-level replay of the PSC RefGen/BT on synthetic designs.

Values are in the positive PCS frame (Ipl_ref = -Ip_IMAS); dt = 0.01 s keeps the
tests fast (the PSC runs at 0.001 s; the rules do not depend on dt except the
number of blend cycles, 0.5 s / dt).
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest
import yaml
from ip_waveform_export import load_design
from ip_waveform_export.export_psc_config import build_btree, build_schedule, parse_psc
from ip_waveform_export.predict_psc_waveform import (
    KnownTraj,
    SignalGen,
    TrajEntry,
    TrajGen,
    load_events_yaml,
    main,
    parse_event_spec,
    parse_schedule,
    predict,
    simulate,
)

DT = 0.01
IP = "pulse_schedule/flux_control/ip/reference"


def _design(tmp_path: Path, soft: list[dict] | None = None):
    """Two nominal segments 0-10 s (1 -> 2 MA) and 10-20 s (2 MA), STOP 99,
    one hard termination 41 (0.5 MA -> 0 over 2 s, held 0.5 s)."""
    doc = {
        "globals": {"name": "syn", "convention": "minus_ip"},
        "references": {
            IP: [{"time": [0.0, 10.0, 20.0], "value": [1.0e6, 2.0e6, 2.0e6]}]
        },
        "segments": [
            {"name": "s0", "id": 0, "start": 0.0, "end": 10.0},
            {"name": "s1", "id": 1, "end": 20.0},
            {"name": "STOP", "id": 99},
        ],
        "events": {
            "eof": {"signal": "ip_ip__meas", "op": ">", "threshold": 1.0e7},
            "trip": {"signal": "ip_ip__meas", "op": ">", "threshold": 2.0e7},
        },
        "exception_handling": {
            "hard_sudden": [{"event": "trip", "target": "term"}],
            "soft": soft
            if soft is not None
            else [
                {
                    "name": "ov",
                    "id": 21,
                    "event": "eof",
                    "points": {"time": [0.0, 4.0], "value": [1.5e6, 0.5e6]},
                    "wd_time": 4.0,
                    "wd_target": "term",
                }
            ],
            "hard": [
                {
                    "name": "term",
                    "id": 41,
                    "from_value": 0.5e6,
                    "to_value": 0.0,
                    "ramp_s": 2.0,
                    "hold_s": 0.5,
                }
            ],
        },
    }
    p = tmp_path / "syn.yaml"
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return load_design(p)


def _at(pred, t):
    return int(np.argmin(np.abs(pred.time - t)))


def _first(pred, seg_id):
    return float(pred.time[np.nonzero(pred.segment_id == seg_id)[0][0]])


def test_nominal_only(tmp_path):
    d = _design(tmp_path)
    pred = predict(d, {}, t_end=22.0, dt=DT)
    m = pred.time < 9.95  # segment 0: Step entry, linear execution on LocalTime
    np.testing.assert_allclose(pred.value[m], 1.0e6 + 1.0e5 * pred.time[m], atol=1e-3)
    assert pred.segment_id[0] == 0 and set(pred.active_path[: _at(pred, 9.9)]) == {"s0"}
    assert abs(_first(pred, 1) - 10.0) <= 2 * DT  # watchdog 10 s -> segment 1
    np.testing.assert_allclose(pred.value[_at(pred, 15.0)], 2.0e6, atol=1e-3)
    assert abs(_first(pred, 99) - 20.0) <= 3 * DT  # watchdog 10 s -> STOP
    # STOP: explicit zero trajectory with a Step entry (export_psc_config, F_story v2)
    assert pred.value[-1] == 0.0 and pred.segment_name[-1] == "STOP"
    assert pred.overlays[_at(pred, 5.0)] == ""


def test_soft_overlay_blend_and_silenced_base(tmp_path):
    d = _design(tmp_path)
    pred = predict(d, {"eof": [(3.0, None)]}, t_end=12.0, dt=DT)
    k = _at(pred, 3.0)
    before = pred.value[k - 1]
    np.testing.assert_allclose(before, 1.0e6 + 1.0e5 * 2.99, atol=1e-3)
    # first overlay tick: one blend step of 0.5 s / dt cycles from the last value
    target = 1.5e6 - 0.25e6 * DT
    np.testing.assert_allclose(pred.value[k], before + (target - before) / (0.5 / DT))
    assert pred.active_path[k] == "ov" and pred.overlays[k] == "ov"
    assert pred.segment_id[k] == 0  # an overlay does not change current_segment
    # after the blend the overlay trajectory itself (LocalTime counted from load)
    m = (pred.time > 3.6) & (pred.time < 6.9)
    np.testing.assert_allclose(
        pred.value[m], 1.5e6 - 0.25e6 * (pred.time[m] - 3.0 + DT), atol=1e-3
    )


def test_hard_segment_by_watchdog_and_stop(tmp_path):
    d = _design(tmp_path)
    pred = predict(d, {"eof": [(3.0, None)]}, t_end=12.0, dt=DT)
    t41 = _first(pred, 41)
    assert abs(t41 - 7.0) <= 2 * DT  # overlay watchdog 4 s -> hard 41
    k = _at(pred, t41)
    # watchdog tick: the overlay is removed before RefGen.execute, the silenced
    # nominal base is re-exposed for one tick (D28, PathHandler.m:144-151)
    np.testing.assert_allclose(pred.value[k], 1.0e6 + 1.0e5 * pred.time[k], atol=1e-3)
    assert pred.active_path[k] == "s0"
    # the hard path loads at the next tick and blends from that value
    assert pred.active_path[k + 1] == "term" and pred.value[k + 1] < pred.value[k]
    m = (pred.time > t41 + 0.6) & (pred.time < t41 + 1.9)
    t_loc = pred.time[m] - (t41 + DT) + DT
    np.testing.assert_allclose(pred.value[m], 0.5e6 * (1 - t_loc / 2.0), atol=1e-3)
    assert abs(_first(pred, 99) - (t41 + 2.5)) <= 2 * DT  # hard watchdog -> STOP
    assert pred.value[-1] == 0.0


def test_sudden_hard_event(tmp_path):
    d = _design(tmp_path)
    pred = predict(d, {"trip": [(4.0, None)]}, t_end=8.0, dt=DT)
    assert abs(_first(pred, 41) - 4.0) <= DT
    assert pred.active_path[_at(pred, 4.0) + 1] == "term"


def test_stop_without_trajectory_holds_reexposed_base(tmp_path):
    """v1 schedules (before F_story v2): STOP without a trajectory holds lastValue."""
    d = _design(tmp_path)
    spec = parse_psc(d)
    ps = copy.deepcopy(build_schedule(d, spec).getroot())
    for seg in ps.findall("SEGMENTS/SEGMENT"):
        if seg.get("name") == "STOP":
            for tr in seg.findall("SIGNAL_TRAJECTORIES"):
                seg.remove(tr)
    bt = build_btree(d, spec)
    for a in bt.iter("Action"):
        if a.get("name") == "PathSegStop":
            del a.attrib["entryRule"]
    # trip during the overlay: the hard 'replace' path overwrites only the top of
    # the stack [ov, s0] -> [term, s0] (SignalGenClass.m:189-200); s0 stays below,
    # its time frozen at the trip (only a 'silence' overlay advances it, l.406-410)
    ev = {"eof": [(3.0, None)], "trip": [(4.0, None)]}
    pred = simulate(parse_schedule(ps), bt, 0, ev, 0.0, 12.0, dt=DT)
    k = _at(pred, _first(pred, 99))
    # hard watchdog tick: s0 is re-exposed (value at LocalTime ~4 s) and STOP,
    # without a trajectory, holds it (run F_story v1: 15.08 MA after 137.88 s)
    assert pred.active_path[k] == "s0"
    np.testing.assert_allclose(pred.value[k], 1.0e6 + 1.0e5 * 4.0, atol=1.0e5 * 3 * DT)
    assert np.all(pred.value[k:] == pred.value[k]) and pred.segment_name[-1] == "STOP"


def test_scale_overlay_composition(tmp_path):
    soft = [
        {
            "name": "half",
            "id": 21,
            "event": "eof",
            "type_addition": "silence,scale",
            "entry_rule": "Step",
            "points": {"time": [0.0, 10.0], "value": [0.5, 0.5]},
            "recovery": True,
            "wd_time": 9.0,
            "wd_target": "term",
        }
    ]
    d = _design(tmp_path, soft)
    pred = predict(d, {"eof": [(2.0, 4.0)]}, t_end=6.0, dt=DT)
    m = (pred.time > 2.05) & (pred.time < 3.95)  # Value = base .* scale + offset
    np.testing.assert_allclose(
        pred.value[m], 0.5 * (1.0e6 + 1.0e5 * pred.time[m]), atol=1e-3
    )
    assert "half(scale)" in pred.overlays[_at(pred, 3.0)]
    # flag down at 4 s: the node is no longer ticked, the idle reset removes the
    # scale after 5 ticks (PathHandler.m:40,162-181)
    k = _at(pred, 4.0)  # first tick with the flag down; last call at k - 1
    assert "half(scale)" in pred.overlays[k + 3]
    np.testing.assert_allclose(
        pred.value[k + 3], 0.5 * (1.0e6 + 1.0e5 * pred.time[k + 3])
    )
    assert pred.overlays[k + 4] == ""
    np.testing.assert_allclose(
        pred.value[k + 4], 1.0e6 + 1.0e5 * pred.time[k + 4], atol=1e-3
    )


def test_transition_5_percent_test_depends_on_sign():
    def entry(v0):
        return TrajEntry(
            1.0, TrajGen([(0.0, 0.0)], 0, 0, 1.0), v0, 1, 1, False, 0.5, False
        )

    e = entry(100.0)
    assert SignalGen._transition(104.0, e, 0.001) == 104.0  # within 5 %: snap
    e = entry(-100.0)
    v = SignalGen._transition(-104.0, e, 0.001)  # negative target: never snaps
    assert v != -104.0 and e.trans_time == pytest.approx(0.499)


def test_trajgen_rules():
    step = TrajGen([(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)], 0, 0, 5.0)
    assert step.generate(0.5)[0] == 1.0 and step.generate(1.0)[0] == 2.0
    assert step.generate(5.0) == (3.0, 2)  # past the end: last value; watchdog
    loop = TrajGen([(0.0, 0.0), (1.0, 1.0)], 1, 1, 0.0)
    assert loop.generate(1.5)[0] == pytest.approx(0.5)


def test_known_traj_rules_from_schedule(tmp_path):
    d = _design(tmp_path)
    sched = parse_schedule(build_schedule(d, parse_psc(d)).getroot())
    k0 = sched.known["Ipl_ref"][0]
    assert isinstance(k0, KnownTraj) and (k0.entry, k0.execution, k0.exit) == (0, 1, 0)
    assert sched.known["Ipl_ref"][41].entry == 1  # ENTRY_RULE "None" -> linear
    assert sched.segment_names[41] == "term"


def test_event_inputs(tmp_path):
    assert parse_event_spec("end_of_flux=119.6") == ("end_of_flux", 119.6, None)
    assert parse_event_spec("z=131.4:until=133") == ("z", 131.4, 133.0)
    with pytest.raises(ValueError):
        parse_event_spec("z=2:until=1")
    p = tmp_path / "ev.yaml"
    p.write_text("events:\n  a: 1.0\n  b: [{at: 2.0, until: 3.0}, {on: 4.0}]\n")
    assert load_events_yaml(p) == {"a": [(1.0, None)], "b": [(2.0, 3.0), (4.0, None)]}
    d = _design(tmp_path)
    with pytest.raises(ValueError, match="not used"):
        predict(d, {"unknown": [(1.0, None)]}, t_end=2.0, dt=DT)


def test_cli(tmp_path):
    d = _design(tmp_path)
    assert d is not None
    out = tmp_path / "p.csv"
    rc = main(
        [
            "--yaml",
            str(tmp_path / "syn.yaml"),
            "--event",
            "eof=3.0",
            "--t-end",
            "8",
            "--dt",
            str(DT),
            "--out-csv",
            str(out),
            "--png",
            str(tmp_path / "p.png"),
        ]
    )
    assert rc == 0 and out.read_text().splitlines()[0].startswith(
        "time_s,t_psc_s,Ipl_ref_A"
    )
    assert (tmp_path / "p.png").stat().st_size > 0
