"""PSC-5 (2026-11-06): the "two-file" designer format of the PSC-in-the-loop run inputs, per variant.

For V in A_nom, B_edit, C_zhold, D_eof (argument: one variant name or "all", default all) it reads the converter
YAML cases/input/psc/<V>/ip_105073_psc_<V>.yaml (the source of truth of the run: waveform,
segments, events, exception handling, constant PSC references) and writes into --out-dir
(default cases/input/psc/<V>/psps_like/):

  <V>_waveforms.yaml   Waveform-Editor YAML (format status REAL) as the presentation file 105073_waveforms.yaml (kept outside this repository):
                       `globals`, then the groups plasma_current (Ip reference, IMAS sign = minus the YAML's +|Ip|
                       values, convention minus_ip), rzip (constant R/Z references) and cspf (constant coil currents).
  <V>_segments.yaml    the PROPOSAL format of the presentation file 105073_segments.yaml (kept outside this repository): `pulse`, `sl_editable`,
                       `events`, `modes`, `segments`, `exception_handling`.

Neither file is consumed by any tool: the run consumed the converter YAML through ip_waveform_export
(--cut-at 84.317598 --psc-config --refgen). Same slide limits as the presentation generator: lines of at most
WIDTH characters and at most MAX_LINES lines (the segments file may use up to MAX_LINES_SEG, reported when it does).
Self-checks after writing: yaml.safe_load round trip, the limits, key order, and Ip values == -(YAML values).

Run:  python3 -I make_psc5_two_file_set.py [all | A_nom | B_edit | C_zhold | D_eof] [--inputs DIR] [--out-dir DIR]
(needs PyYAML; --inputs defaults to <repo>/cases/input/psc, --out-dir to <inputs>/<V>/psps_like)
"""

import argparse
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]                            # <repo>/preprocessing/psps/psc_run -> <repo>
INPUTS = REPO / "cases" / "input" / "psc"         # one sub-folder per variant
VARIANTS = ["A_nom", "B_edit", "C_zhold", "D_eof"]
RUN_DATE = "2026-11-06"
PULSE = 105073
CUT = 84.317598                                   # D20 window cut, s: designer time of PSC clock 0
IP_PATH = "pulse_schedule/flux_control/ip/reference"
COILS = ["CS3U", "CS2U", "CS1", "CS2L", "CS3L", "PF1", "PF2", "PF3", "PF4", "PF5", "PF6"]
WIDTH, MAX_LINES, MAX_LINES_SEG = 110, 45, 60     # slide limits (presentation generator: 110 / 45)
# Effective constant controller settings of the four runs (identical in A-D): configuration.ymmsl:167-172 of
# <fork>/cases/runs/evolutive_controller_105073_psc_<V>/ and the glue default Shape_control 0.
RUN_MODE = {"shape_ip": "none", "ip": "kcurr", "vs": "vs1_vs3", "snu": "off", "cla": "off"}
MODE_NAME = "flattop_kcurr"
EVENT_FLAGS = {"ip_too_high": "glb_ps__ip_too_high", "end_of_flux": "glb_ps__end_of_flux",
               "z_excursion": "glb_ps__z_excursion"}            # PSCGlobalMonConfig.xml MONITORING outputs


def num(x):
    """Shortest exact decimal form of a float (repr), never an exponent for the magnitudes used here."""
    x = float(x)
    if x == int(x) and abs(x) < 1e15:
        return f"{x:.1f}"
    return repr(x)


def lst(xs, f=num):
    return "[" + ", ".join(f(x) for x in xs) + "]"


def q(s):
    """Single-quoted YAML scalar."""
    return "'" + str(s).replace("'", "''") + "'"


def flow_lines(first, items, last, pad):
    """`first` + items joined by ', ' + `last` on one line when it fits, else wrapped and aligned at `pad`
    (same helper as the presentation generator)."""
    out, cur = [], first
    for k, it in enumerate(items):
        tail = (", " if k < len(items) - 1 else last)
        if cur.rstrip() != first.rstrip() and len(cur + it + tail) > WIDTH:
            out.append(cur.rstrip())
            cur = " " * pad
        while len(cur + it + tail) > WIDTH:          # a single quoted scalar longer than the line: fold it
            assert "'" in it and it.count("'") % 2 == 0, it
            cut = (cur + it)[:WIDTH].rfind(" ")
            assert cut > len(cur) + it.index("'"), it
            out.append((cur + it)[:cut].rstrip())
            cur, it = " " * (pad + 2), (cur + it)[cut + 1:]
        cur += it + tail
    return out + [cur]


def two_line(head, body, comment=""):
    """`head body` on one line when it fits, else head (+ comment) and the body on the next line."""
    line = f"{head} {body}" + (f"   # {comment}" if comment else "")
    if len(line) <= WIDTH:
        return [line]
    return [head + (f"   # {comment}" if comment else ""), "    - " + body[1:-1]]


# ---- file 1: <V>_waveforms.yaml (Waveform-Editor YAML, REAL format) ----
def waveforms_text(v, y):
    g = y["globals"]
    assert g.get("convention") == "minus_ip", g.get("convention")
    ref = y["references"][IP_PATH][0]
    t, vals = [float(x) for x in ref["time"]], [float(x) for x in ref["value"]]
    seg = next(s for s in y["segments"] if s["id"] == 0)
    win = [float(seg["start"]), float(seg["end"])]
    refs = y["psc"]["references"]
    r0, z0 = float(refs["Rpl_ref"]["value"]), float(refs["Zpl_ref"]["value"])
    cspf = [float(c) for c in refs["CSPF_curr_ref"]["value"]]
    assert len(cspf) == len(COILS), len(cspf)
    peak = max(vals) / 1e6
    o = [
        f"# RUN INPUT EQUIVALENT (PSC-5 run {v} of {RUN_DATE}), derived from ip_105073_psc_{v}.yaml",
        f"# Format status: REAL (Waveform-Editor YAML: globals, groups, tendencies); segments: {v}_segments.yaml",
        "# NOT consumed by any tool: the run consumed the converter YAML through ip_waveform_export. IMAS sign, Ip < 0:",
        "# the converter YAML holds +|Ip| (convention minus_ip, Ipl_ref = -Ip_IMAS), negated here; t = 0 plasma init.",
        f"globals: {{dd_version: {g['dd_version']}}}",
        f"plasma_current:   # -> PSC Ipl_ref (KCURR); the run used t >= {num(CUT)} s (PSC clock 0, D20 window cut)",
        f"  {IP_PATH}:   # A, IMAS sign; {len(t)} designer points, |Ip| up to {peak:.3f} MA",
        f"    - time: {lst(t)}",
        f"      value: {lst([-x for x in vals])}",
        f"rzip:   # constant over the flat-top window {lst(win)} s = psc.references Rpl_ref, Zpl_ref (YAML)",
        f"  # (inverse_convergence 105073 NICE slice t = {num(CUT)} s, boundary geometric_axis r, z; m) -> PSC Rpl_ref,",
        "  # Zpl_ref; produced by the PSC, consumed by nothing (D19)",
    ]
    o += two_line("  pulse_schedule/position_control/current_centroid/r/reference:",
                  f"[{{time: {lst(win)}, value: {lst([r0, r0])}}}]")
    o += two_line("  pulse_schedule/position_control/current_centroid/z/reference:",
                  f"[{{time: {lst(win)}, value: {lst([z0, z0])}}}]")
    o += ["cspf:   # constant coil currents, A per turn, IMAS sign = psc.references.CSPF_curr_ref -> PSC CSPF_curr_ref",
          "  # coil(i) order CS3U CS2U CS1 CS2L CS3L PF1..PF6 (CS1 = CS1U = CS1L, series); 14 -> 11 mapping of the fork",
          "  # wrapper is UNVERIFIED (wording of the YAML description); produced by the PSC, consumed by nothing (D19)"]
    for i, (c, name) in enumerate(zip(cspf, COILS), 1):
        o += two_line(f"  pulse_schedule/pf_active/coil({i})/current/reference:",
                      f"[{{time: {lst(win)}, value: {lst([c, c])}}}]", name)
    return "\n".join(o) + "\n"


# ---- file 2: <V>_segments.yaml (PROPOSAL format of the presentation file) ----
def event_test(name, e):
    sig, op, thr = e["signal"], e["op"], float(e["threshold"])
    if name == "ip_too_high":
        return f"{sig} {op} {thr / 1e6:.2f} MA"
    if name == "end_of_flux":
        return f"{sig} {op} {thr / 1e3:.2f} kA"
    return f"|{sig} - {num(e['reference'])}| {op} {thr:.2f} m"


def segments_text(v, y):
    ev, eh = y["events"], y["exception_handling"]
    seg = next(s for s in y["segments"] if s["id"] == 0)
    stop = next(s for s in y["segments"] if s["name"] == "STOP")
    start, end = float(seg["start"]), float(seg["end"])
    span = round(end - start, 6)
    soft = {s["name"]: s for s in eh["soft"]}
    hard = {h["name"]: h for h in eh["hard"]}
    sudden = {h["target"]: h["event"] for h in eh["hard_sudden"]}
    o = [
        f"# RUN INPUT EQUIVALENT (PSC-5 run {v} of {RUN_DATE}); Format status: PROPOSAL (same format as",
        "# the presentation file 105073_segments.yaml); NOT consumed by any tool; the run consumed",
        f"# ip_105073_psc_{v}.yaml through ip_waveform_export. segment = PSC current_segment id: modes, transitions",
        f"pulse: {{number: {PULSE}, waveforms: {v}_waveforms.yaml}}   # t in s (0 = plasma initiation), Ip in MA, +|Ip|",
        "sl_editable:   # who edits what",
        "  session_leader: [segments.nominal, 'transitions (to, time_after)', events.ip_too_high.threshold,",
        "                   events.end_of_flux.threshold, events.z_excursion.threshold, exception_handling.action,",
        "                   exception_handling.timeout_s]",
        f"  pcs_expert: ['mode variables (shape_ip, ip, vs, snu, cla)', 'gains (psps_pcs_dataset_{v}.json PARAM)']",
        "events:   # named predicates -> PSC global-monitoring flags (PSCGlobalMonConfig.xml outputs); units MA, kA, m",
    ]
    for name, flag in EVENT_FLAGS.items():
        e = ev[name]
        items = [f"flag: {flag}", f"test: {q(event_test(name, e))}"]
        if name == "end_of_flux":
            items.append(f"latch: {str(bool(e.get('latch', False))).lower()}")
        if name == "z_excursion":
            release = f"|{e['signal']} - {num(e['reference'])}| < {float(e['release_threshold']):.2f} m"
            items.append(f"release: {q(release)}")
        if name != "end_of_flux":
            items.append("kind: alarm")
        items.append(f"description: {q(e['description'])}")
        o += flow_lines(f"  {name}: {{", items, "}", len(name) + 5)
    o += ["# modes = the run's constant settings (D19): configuration.ymmsl KCURR 1, control_Ip 1, RZIp 0, VS 1,",
          "# VS_control_mode 3, Shape_control 0 (glue default); the rzip and cspf references of the waveforms file were",
          "# produced by the PSC but consumed by nothing. pcs@aa217bc values: shape_ip none 0; ip kcurr 1; vs vs1_vs3 3.",
          "modes:"]
    items = [f"{k}: {val}" for k, val in RUN_MODE.items()] + ["references: [plasma_current]"]
    o += flow_lines(f"  {MODE_NAME}: {{", items, "}", len(MODE_NAME) + 5)
    o += [f"segments:   # D20 window cut: PSC clock 0 at {num(CUT)} s (PS.xml watchdog {num(round(end - CUT, 6))} s = end - cut);",
          "            # no MCLS activation window (constant mode); time_after in designer seconds from the nominal start",
          f"  - {{name: {seg['name']}, id: {seg['id']}, nominal: {lst([start, end])}, modes: {{{MODE_NAME}: {{}}}},",
          f"     transitions: [{{to: STOP, time_after: {num(span)}}}]}}",
          f"  - {{name: STOP, id: {stop['id']}}}",
          "exception_handling:  # ids as in PS.xml / BTree.xml (soft 21/22, hard 41/42, FWHL pattern); timeout_s =",
          "                     # wd_time, then = wd_target; soft = overlay on Ipl_ref, hard = termination segment"]
    e21 = soft["eof_rampdown"]
    p = e21["points"]
    rows = [
        {"name": "eof_rampdown", "id": e21["id"], "kind": "soft", "on": e21["event"], "timeout_s": e21["wd_time"],
         "then": e21["wd_target"],
         "action": f"Ip ref {float(p['value'][0]) / 1e6:.2f} -> {float(p['value'][-1]) / 1e6:.2f} MA over "
                   f"{num(float(p['time'][-1]) - float(p['time'][0]))} s on top of the nominal ({e21['type_addition']})"},
    ]
    e22 = soft["z_hold"]
    rows.append({"name": "z_hold", "id": e22["id"], "kind": "soft", "on": e22["event"], "timeout_s": e22["wd_time"],
                 "then": e22["wd_target"],
                 "action": f"hold the Ip reference at its last value until Z recovers ({e22['type_addition']}, no trajectory)"})
    for name in ("ip_termination", "eof_termination"):
        h = hard[name]
        on = sudden.get(name) or next(s["name"] + " timeout" for s in soft.values() if s["wd_target"] == name)
        rows.append({"name": name, "id": h["id"], "kind": "hard", "on": on,
                     "timeout_s": round(float(h["ramp_s"]) + float(h["hold_s"]), 6), "then": h["wd_target"],
                     "action": f"Ip ref {float(h['from_value']) / 1e6:.2f} -> {float(h['to_value']) / 1e6:.0f} MA over "
                               f"{num(h['ramp_s'])} s, held {num(h['hold_s'])} s"})
    assert [r["id"] for r in rows] == [21, 22, 41, 42], rows
    for r in rows:
        items = [f"name: {r['name']}", f"id: {r['id']}", f"kind: {r['kind']}", f"on: {r['on']}",
                 f"timeout_s: {num(r['timeout_s'])}", f"then: {r['then']}", f"action: {q(r['action'])}"]
        o += flow_lines("  - {", items, "}", 5)
    return "\n".join(o) + "\n"


# ---- self-checks ----
def check(path, text, y, kind, v):
    lines = text.rstrip("\n").split("\n")
    limit = MAX_LINES if kind == "waveforms" else MAX_LINES_SEG
    assert len(lines) <= limit, (path.name, len(lines), limit)
    assert all(len(ln) <= WIDTH for ln in lines), (path.name, max(len(ln) for ln in lines))
    d = yaml.safe_load(path.read_text())
    if kind == "waveforms":
        assert list(d) == ["globals", "plasma_current", "rzip", "cspf"], list(d)
        assert d["globals"] == {"dd_version": y["globals"]["dd_version"]}, d["globals"]
        ip = d["plasma_current"][IP_PATH][0]
        src = y["references"][IP_PATH][0]
        assert ip["time"] == [float(x) for x in src["time"]], "Ip times differ"
        assert ip["value"] == [-float(x) for x in src["value"]], "Ip values are not minus the YAML values"
        assert all(x < 0 for x in ip["value"]), "IMAS Ip must be negative"
        refs = y["psc"]["references"]
        r = d["rzip"]["pulse_schedule/position_control/current_centroid/r/reference"][0]["value"]
        z = d["rzip"]["pulse_schedule/position_control/current_centroid/z/reference"][0]["value"]
        assert r == [float(refs["Rpl_ref"]["value"])] * 2 and z == [float(refs["Zpl_ref"]["value"])] * 2
        for i, c in enumerate(refs["CSPF_curr_ref"]["value"], 1):
            assert d["cspf"][f"pulse_schedule/pf_active/coil({i})/current/reference"][0]["value"] == [float(c)] * 2, i
        assert len(d["cspf"]) == 11, len(d["cspf"])
    else:
        assert list(d) == ["pulse", "sl_editable", "events", "modes", "segments", "exception_handling"], list(d)
        assert d["pulse"] == {"number": PULSE, "waveforms": f"{v}_waveforms.yaml"}, d["pulse"]
        assert list(d["events"]) == list(EVENT_FLAGS) and all(d["events"][k]["flag"] == f for k, f in EVENT_FLAGS.items())
        assert d["events"]["end_of_flux"]["latch"] is True and "release" in d["events"]["z_excursion"]
        assert list(d["modes"]) == [MODE_NAME] and d["modes"][MODE_NAME]["references"] == ["plasma_current"]
        assert [s["id"] for s in d["segments"]] == [0, 99] and d["segments"][0]["transitions"][0]["to"] == "STOP"
        seg = next(s for s in y["segments"] if s["id"] == 0)
        assert d["segments"][0]["nominal"] == [float(seg["start"]), float(seg["end"])]
        assert abs(d["segments"][0]["transitions"][0]["time_after"] - (float(seg["end"]) - float(seg["start"]))) < 1e-6
        assert [e["id"] for e in d["exception_handling"]] == [21, 22, 41, 42]
        # PyYAML (YAML 1.1) reads the key `on` as the boolean True, as it does for the presentation file
        assert all({str(k) for k in e} == {"name", "id", "kind", "True", "timeout_s", "then", "action"} or
                   set(e) == {"name", "id", "kind", "on", "timeout_s", "then", "action"} for e in d["exception_handling"])
        soft = {s["name"]: s for s in y["exception_handling"]["soft"]}
        assert d["exception_handling"][0]["timeout_s"] == float(soft["eof_rampdown"]["wd_time"])
    return len(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="two-file designer format of the PSC run inputs, per variant")
    ap.add_argument("variant", nargs="?", default="all", help="A_nom | B_edit | C_zhold | D_eof | all (default)")
    ap.add_argument("--inputs", default=str(INPUTS), help="folder with one sub-folder per variant")
    ap.add_argument("--out-dir", default=None, help="output folder (default <inputs>/<V>/psps_like)")
    args = ap.parse_args(argv[1:])
    variants = VARIANTS if args.variant == "all" else [args.variant]
    bad = [v for v in variants if v not in VARIANTS]
    if bad:
        sys.exit(f"unknown variant(s) {bad}; choose from {VARIANTS} or 'all'")
    inputs = Path(args.inputs)
    for v in variants:
        folder = inputs / v
        y = yaml.safe_load((folder / f"ip_105073_psc_{v}.yaml").read_text())
        out_dir = Path(args.out_dir) if args.out_dir else folder / "psps_like"
        out_dir.mkdir(parents=True, exist_ok=True)
        for kind, fn in (("waveforms", waveforms_text), ("segments", segments_text)):
            path = out_dir / f"{v}_{kind}.yaml"
            text = fn(v, y)
            path.write_text(text)
            n = check(path, text, y, kind, v)
            limit = MAX_LINES if kind == "waveforms" else MAX_LINES_SEG
            over = "" if n <= MAX_LINES else f" (above the presentation limit {MAX_LINES}, within {MAX_LINES_SEG})"
            shown = path.relative_to(REPO) if path.is_relative_to(REPO) else path
            print(f"{shown}: {n} lines (limit {limit}), max width "
                  f"{max(len(ln) for ln in text.split(chr(10)))} <= {WIDTH}, safe_load + checks OK{over}")


if __name__ == "__main__":
    main(sys.argv)
