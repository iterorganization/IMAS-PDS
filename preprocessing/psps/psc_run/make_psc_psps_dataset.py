"""PSC-5 (2026-11-06): a PSPS-EQUIVALENT "PCS dataset" JSON for each PSC-in-the-loop run variant.

For V in A_nom, B_edit, C_zhold, D_eof it reads the run inputs in cases/input/psc/<V>/ (the designer YAML
of the converter format, the refgen export, the four PSC files PS.xml / BTree.xml / PSCGlobalMonConfig.xml /
PSCIntConfig.xml in psc_config_ip_105073_psc_<V>/) and the variant's case override
cases/overrides/evolutive_controller_105073_psc_<V>.ymmsl (ps_source.source_uri), and writes
psps_pcs_dataset_<V>.json into --out-dir (default cases/input/psc/<V>/psps_like/), with the SAME top-level
structure as the presentation file 105073_psps_pcs_dataset.json (study notes, kept outside this repository;
format status GUESS):
_header, pulse, name, datasets.PCS.{WF, segments, moduleGroups.CTRL_Magnetic.PARAM}.

Every block carries a `_status`: "real" (taken from a run file), "guess" (structure only), "placeholder".
The KCURR gains come from the pcs-nightly checkout's KCURR_PFPO1_load_gains_tp.m ($PCS_PATH, default
<repo>/local_installs/pcs-nightly installed by pds_setup.sh with INSTALL_PCS_NIGHTLY=true) (the file the
run's glue loads through pcssp_KCURR_PFPO1_obj.m); otherwise the presentation placeholders are written. Since
2026-11-09 the selected gain set (*_Ip, IpControlMode = 1; VERIFIED by static reading of the module's Stateflow
charts) is explicit: KCURR_PFPO1_Gains.selected / .Ip, the unused noIp set under ._not_selected.
Nothing consumes these JSON files.

Run:  python3 -I make_psc_psps_dataset.py      (needs PyYAML; standard library otherwise)
      PCS_PATH=<other pcs-nightly checkout> python3 -I make_psc_psps_dataset.py   to override the default
Options: --inputs <folder> (default <repo>/cases/input/psc), --out-dir <folder> (default <inputs>/<V>/psps_like),
         --gains <KCURR_PFPO1_load_gains_tp.m> (default $PCS_PATH/modules/KCURR_PFPO1/KCURR_PFPO1_load_gains_tp.m)
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]                                      # <repo>/preprocessing/psps/psc_run -> <repo>
INPUTS = REPO / "cases" / "input" / "psc"                   # one sub-folder per variant
OVERRIDES = REPO / "cases" / "overrides"
# KCURR module files of the pcs-nightly checkout, relative to $PCS_PATH (default PCS_NIGHTLY_DEFAULT)
PCS_NIGHTLY_DEFAULT = REPO / "local_installs" / "pcs-nightly"  # installed by pds_setup.sh, INSTALL_PCS_NIGHTLY
GAINS_REL = "modules/KCURR_PFPO1/KCURR_PFPO1_load_gains_tp.m"
TP_REL = "modules/KCURR_PFPO1/KCURR_PFPO1_ext/KCURR_PFPO1_load_tp.m"
SCHED_REL = "modules/KCURR_PFPO1/KCURR_PFPO1_load_scheduling_fp.m"
VARIANTS = ["A_nom", "B_edit", "C_zhold", "D_eof"]
CUT = 84.317598                                             # D20 window cut, s (designer time of PSC clock 0)
IP_PATH = "pulse_schedule/flux_control/ip/reference"
# Effective controller mode settings of the four runs, read from
# <fork>/cases/runs/evolutive_controller_105073_psc_<V>/configuration.ymmsl:167-172 (identical in A-D) and the
# glue defaults for the keys that are not set there (muscle_controller_NICE_IMAS_iter_init_psc.m:176-191).
RUN_MODES = {
    "KCURR": 1, "control_Ip": 1, "RZIp": 0, "VS": 1, "VS_control_mode": 3, "PSModel": 1,   # configuration.ymmsl
    "Shape_control": 0, "schedulingVar_KCURR": 0, "AllocatorMode": 1,                     # glue defaults / constants
}


# ---- the presentation writer (compact JSON layout), same function as the presentation generator ----
def compact(obj, ind=0, lead=0, width=150):
    """JSON with 2-space indentation; a container goes on one line when it fits in `width`."""
    s = json.dumps(obj)
    flat = isinstance(obj, dict) and not any(isinstance(v, (dict, list)) for v in obj.values())
    if lead + len(s) <= width or flat or not isinstance(obj, (dict, list)):
        return s
    pad = " " * (ind + 2)
    if isinstance(obj, dict):
        items = [f"{pad}{json.dumps(k)}: " + compact(v, ind + 2, ind + 4 + len(json.dumps(k)), width)
                 for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + "\n" + " " * ind + "}"
    return "[\n" + ",\n".join(pad + compact(v, ind + 2, ind + 2, width) for v in obj) + "\n" + " " * ind + "]"


# ---- MATLAB gains file -> dict (the subset of syntax used by KCURR_PFPO1_load_gains_tp.m) ----
def matlab_value(expr, known, prefix):
    expr = expr.strip().rstrip(";").strip()
    m = re.fullmatch(r"'([^']*)'", expr)
    if m:
        return m.group(1)
    m = re.fullmatch(r"-" + re.escape(prefix) + r"\.(\w+)", expr)          # -tp.X : negation of a known field
    if m and m.group(1) in known:
        v = known[m.group(1)]
        return [-x for x in v] if isinstance(v, list) else -v
    m = re.fullmatch(r"\[(.*)\]\s*(?:\.?\*\s*(\d+(?:\.\d+)?(?:e-?\d+)?))?", expr, re.S)   # [matrix] or [vector].*k
    if m:
        k = float(m.group(2)) if m.group(2) else 1.0
        body = re.sub(r"\.\.\.\s*\n", " ", m.group(1))          # "..." continues the row on the next line
        rows = [r.strip() for r in re.split(r"[;\n]", body) if r.strip()]
        mat = [[k * float(x) for x in re.split(r"[\s,]+", r.strip()) if x] for r in rows]
        return mat if len(mat) > 1 else mat[0]
    m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)\*)?(ones|zeros|eye)\((\d+)(?:,(\d+))?\)", expr)
    if m:
        k = float(m.group(1)) if m.group(1) else 1.0
        fn, n, p = m.group(2), int(m.group(3)), int(m.group(4) or m.group(3))
        if fn == "eye":
            return [[k if i == j else 0.0 for j in range(p)] for i in range(n)]
        v = k if fn == "ones" else 0.0
        return [v] * p if n == 1 else [[v] * p for _ in range(n)]
    m = re.fullmatch(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", expr)
    if m:
        return float(expr)
    raise ValueError(f"unsupported MATLAB expression: {expr[:60]}")


def parse_matlab_struct(path, prefix):
    """{field: value} for every `<prefix>.<field> = <expr>;` statement (bracketed matrices may span lines and
    contain ';' row separators)."""
    text = re.sub(r"%[^\n]*", "", path.read_text())                 # strip comments
    out = {}
    pat = re.compile(rf"{re.escape(prefix)}\.(\w+)\s*=\s*")
    pos = 0
    while True:
        m = pat.search(text, pos)
        if not m:
            break
        i = m.end()
        if text[i] == "[":                                            # skip to the matching bracket first
            depth, j = 0, i
            while True:
                if text[j] == "[":
                    depth += 1
                elif text[j] == "]":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
        else:
            j = i
        k = text.find(";", j)
        expr = text[i:k]
        try:
            out[m.group(1)] = matlab_value(expr, out, prefix)
        except ValueError as e:
            out[m.group(1)] = f"not parsed ({e})"
        pos = k + 1
    return out


def shape(v):
    if isinstance(v, list) and v and isinstance(v[0], list):
        return f"{len(v)}x{len(v[0])}"
    return f"{len(v)}" if isinstance(v, list) else "scalar"


def gains_block(gains_m, tp_m, sched_m):
    """moduleGroups.CTRL_Magnetic.PARAM for the run: real gains when the framework files are readable."""
    presentation = {
        "_status": "placeholder, run gains not traced",
        "_owner": "PCS expert (gains, matrices); abbreviated, values computed offline, not by the Session Leader",
        "KCURR_ext": {"KCRext_Kdref": "matrix", "KCRext_Ke": "matrix", "KCRext_Ky": "matrix",
                      "KCRext_N": "matrix", "KCRext_Nd": "vector"},
        "gain_set": {"gP0": "[11 values]", "gI0": "[11 values]", "gD0": "[11 values]",
                     "ref_gain_selector": {"amplitudeValues": [1.0, 2.0],
                                           "offsetValues": [120000000, 500000000],
                                           "widthValues": [500000000, 600000000000]}}}
    if not (gains_m.is_file() and tp_m.is_file() and sched_m.is_file()):
        return presentation
    g = parse_matlab_struct(gains_m, "KCURR_Gains")
    tp = parse_matlab_struct(tp_m, "tp")
    sched = parse_matlab_struct(sched_m, "ParameterScheduling_KCURR")
    sets = {}
    for suffix, label in (("noIp", "no plasma current"), ("Ip", "plasma current")):
        fields = {k[: -len(suffix) - 1]: v for k, v in g.items() if k.endswith("_" + suffix)}
        sets[suffix] = {"_label": label, "_shapes": {k: shape(v) for k, v in fields.items()}, **fields}
    return {
        "_status": "real (gain file of the run's KCURR module) / derived (mapping to the ATCKX7 names) / VERIFIED (gain set *_Ip selected, see _source.gain_set_selection)",
        "_owner": "PCS expert (gains, matrices); values computed offline, not by the Session Leader",
        "_source": {
            "gains_file": str(gains_m),
            "loaded_by": "pcssp_KCURR_PFPO1_obj.m: obj.addtunparamstruct('KCURR_PFPO1_Gains', @KCURR_PFPO1_load_gains_tp); "
                         "obj.init/setup called by the run glue muscle_controller_NICE_IMAS_iter_init_psc.m:210-212",
            "framework_copy": "$PCS_PATH checkout (local_installs/pcs-nightly) = pcs aa217bc (git.iter.org/pcs/pcs, 2026-08-17) + "
                              "pcssp-nightly@merge_IGZ_PSC ebf3ee0 src/psc (D18)",
            "module": "pcssp_KCURR_PFPO1 (settiming 0, 0.002, 10); the KCURR_PFPO1_ext variant (external gains) was NOT used: "
                      "its gains loader is commented out in pcssp_KCURR_ext_obj.m",
            "gain_set_selection": "VERIFIED 2026-11-09 by static reading of the module blocks: pcs@aa217bc "
                                  "modules/KCURR_PFPO1/pcssp_KCURR_PFPO1.slx, simulink/stateflow/chart_21.xml MATLAB Function "
                                  "fcn(schedulingVar, IpControlMode, KCURR_PFPO1_Gains): if IpControlMode < 0.5 the *_noIp fields "
                                  "are used, else the *_Ip fields; chart_42.xml ParamThr4Scheduling maps schedulingVar = 0 with "
                                  "levels [0, 1e6] to region 1 (the only element of the gains struct). The runs set "
                                  "IpControlMode_KCURR = setting control_Ip = 1 (glue muscle_controller_NICE_IMAS_iter_init_psc.m:177; "
                                  "configuration.ymmsl control_Ip: 1) and schedulingVar_KCURR = 0 (glue:178) => the *_Ip set was "
                                  "active in runs A-D. Derived: the wrapper Constant block IpControlMode_KCURR "
                                  "(pcssp_controller_and_ps_psc.slx root) feeds the module's IpControlMode port.",
            "coil_order": "CS3U CS2U CS1 CS2L CS3L P1 P2 P3 P4 P5 P6 (module description); matrices 11x12 = 11 coils + Ip column",
        },
        "KCURR_PFPO1_Gains": {
            "selected": "Ip",
            "Ip": sets["Ip"],
            "_not_selected": {"_note": "declared in the gain file, not used in these runs (IpControlMode = 1)",
                              "noIp": sets["noIp"]}},
        "KCURR_PFPO1_tp": {"_status": "real", "_file": str(tp_m),
                           "_units": "PosCurSlewRate/NegCurSlewRate A/s (x1e9 in the file), Vup/Vlow V", **tp},
        "ParameterScheduling_KCURR": {"_status": "real", "_file": str(sched_m), **sched},
        "KCURR_ext": {"_status": "placeholder, not used by the run (ATCKX7 v1.0 s.34 key names, presentation file)",
                      **presentation["KCURR_ext"]},
        "gain_set": {
            "_status": "derived: gP0/gI0/gD0 = P_Ip/I_Ip/D_Ip of KCURR_PFPO1_Gains (ATCKX7 s.34 names; mapping ours); "
                       "ref_gain_selector = placeholder, no counterpart in the run",
            "gP0": sets["Ip"].get("P"), "gI0": sets["Ip"].get("I"), "gD0": sets["Ip"].get("D"),
            "ref_gain_selector": presentation["gain_set"]["ref_gain_selector"]},
    }


# ---- run files ----
def read_yaml(folder, v):
    return yaml.safe_load((folder / f"ip_105073_psc_{v}.yaml").read_text())


def points(traj):
    pts = [(float(p.get("time")), p.get("value")) for p in traj.find("REFERENCE").findall("POINT")]
    x = [round(t, 6) for t, _ in pts]
    y = []
    for _, val in pts:
        if val.startswith("["):
            y.append([float(s) for s in val.strip("[]").split(",")])
        else:
            y.append(float(val))
    return x, y


def read_ps(path):
    root = ET.parse(path).getroot()
    segs = []
    for s in root.find("SEGMENTS").findall("SEGMENT"):
        d = {"name": s.get("name"), "id": int(s.get("id"))}
        if s.get("wd_time") is not None:
            d["wd_time"] = float(s.get("wd_time"))
            d["wd_target"] = s.get("wd_target")
        d["trajectories"] = {}
        st = s.find("SIGNAL_TRAJECTORIES")
        for tr in (st.findall("SIGNAL_TRAJECTORY") if st is not None else []):
            x, y = points(tr)
            d["trajectories"][tr.get("name")] = {
                "entry_rule": tr.find("ENTRY_RULE").get("is"), "exit_rule": tr.find("EXIT_RULE").get("is"),
                "execution_rule": tr.find("EXECUTION_RULE").get("is"), "x": x, "y": y}
        segs.append(d)
    outputs = [(sig.get("name"), int(sig.get("dimension"))) for sig in root.find("DECLARATIONS/OUTPUTS").findall("SIGNAL")]
    params = {p.get("name"): float(p.get("value")) for p in root.find("DECLARATIONS/PARAMETERS").findall("PARAMETER")}
    return root.get("name"), root.get("comment"), segs, outputs, params


def read_monitoring(path):
    root = ET.parse(path).getroot()
    ns = {"e": "http://www.ipp.mpg.de/2004/Schema/Exceptions_Desc"}
    rules = {}
    for m in root.findall("e:MONITORINGS/e:MONITORING", ns):
        rules[m.get("output")] = {"name": m.get("name"), "script": m.find("e:SCRIPT", ns).get("code")}
    scen = {s.get("output"): s.find("e:SCRIPT", ns).get("code") for s in root.findall("e:SCENARIOS/e:SCENARIO", ns)}
    goals = {g.get("output"): g.find("e:SCRIPT", ns).get("code") for g in root.findall("e:GOALS/e:GOAL", ns)}
    return rules, scen, goals


def read_btree(path):
    """Which segment or overlay each flag leads to, and the RefGen actions of every sub-tree."""
    root = ET.parse(path).getroot()
    actions = {}                                       # segment id -> RefGen action attributes
    for bt in root.findall("BehaviorTree"):
        for a in bt.iter("Action"):
            if a.get("ID") == "RefGen":
                actions[int(a.get("segmentID"))] = dict(a.attrib)
    rules = []
    main = root.find("BehaviorTree[@ID='BehaviorTree']")
    for pre in main.iter("Precondition"):
        cond = pre.get("condition")
        flags = re.findall(r"\{(glb_\w+)\} == 1", cond)
        if not flags:
            continue
        assign = [a for a in pre.iter("Action") if a.get("ID") == "AssignValue" and a.get("target") == "{current_segment}"]
        sub = pre.find("SubTree")
        if assign:
            rules.append({"flag": flags[0], "kind": "hard_sudden", "leads_to_segment": int(assign[-1].get("source")),
                          "condition": cond, "node": pre.get("name")})
        elif sub is not None:
            seg = int(root.find(f"BehaviorTree[@ID='{sub.get('ID')}']").get("segmentID"))
            rules.append({"flag": flags[0], "kind": "soft_overlay", "leads_to_segment": seg,
                          "condition": cond, "node": pre.get("name"),
                          "release_condition": actions[seg].get("condition")})
    return rules, actions


def pulse_schedule_ids_uri(v):
    """ps_source.source_uri of the variant's case override: the pulse_schedule IDS the run's source actor read."""
    ov = OVERRIDES / f"evolutive_controller_105073_psc_{v}.ymmsl"
    if not ov.is_file():
        return None
    os.environ.setdefault("PDS_REPO", str(REPO))
    os.environ.setdefault("CASE_DIR", str(REPO / f"cases/evolutive_controller_105073_psc_{v}"))
    return os.path.expandvars(yaml.safe_load(ov.read_text()).get("settings", {}).get("ps_source.source_uri", ""))


def refgen_vs_ps(folder, v, ps_segs):
    """Compare the refgen export with PS.xml: same Ipl_ref points? what is missing?"""
    _, _, rg_segs, rg_out, _ = read_ps(folder / f"ip_105073_psc_{v}_refgen.xml")
    ps_by = {s["id"]: s for s in ps_segs}
    same_ip = all(s["trajectories"].get("Ipl_ref") == ps_by[s["id"]]["trajectories"].get("Ipl_ref") for s in rg_segs)
    only_ps = sorted(set(ps_by) - {s["id"] for s in rg_segs})
    return {"refgen_segment_ids": [s["id"] for s in rg_segs], "refgen_outputs": [n for n, _ in rg_out],
            "ipl_ref_points_identical_in_common_segments": same_ip, "segment_ids_only_in_PS_xml": only_ps}


# ---- the dataset ----
def build(v, folder, out_dir, param):
    y = read_yaml(folder, v)
    g = y["globals"]
    cfg = folder / f"psc_config_ip_105073_psc_{v}"             # the four PSC files of the variant
    ps_name, ps_comment, segs, outputs, params = read_ps(cfg / "PS.xml")
    mon, scen, goals = read_monitoring(cfg / "PSCGlobalMonConfig.xml")
    bt_rules, actions = read_btree(cfg / "BTree.xml")
    by_id = {s["id"]: s for s in segs}
    events = y.get("events", {})
    flag_of = {ev: f"glb_ps__{ev}" for ev in events}

    # exception rules: YAML event (threshold) + global monitoring script + behaviour-tree target
    rules = []
    for r in bt_rules:
        ev = r["flag"].replace("glb_ps__", "")
        e = events.get(ev, {})
        tgt = by_id.get(r["leads_to_segment"], {})
        rules.append({
            "event": ev, "flag": r["flag"], "kind": r["kind"],
            "signal": e.get("signal"), "op": e.get("op"), "threshold": e.get("threshold"),
            "reference": e.get("reference"), "release_threshold": e.get("release_threshold"),
            "latch": e.get("latch", False), "description": e.get("description"),
            "monitoring_script": mon.get(r["flag"], {}).get("script"),
            "leads_to": {"segment": r["leads_to_segment"], "name": tgt.get("name"),
                         "wd_time": tgt.get("wd_time"), "wd_target": tgt.get("wd_target")},
            "bt_condition": r["condition"], "release_condition": r.get("release_condition"),
            "_status": "real (YAML events + PSCGlobalMonConfig.xml + BTree.xml)"})

    # WF: the designer's Ip reference, absolute designer time, positive |Ip| (YAML convention minus_ip)
    ref = y["references"][IP_PATH][0]
    wf = {"_status": "real (variant YAML references, whole designer waveform; the PSC ran the part from the cut)",
          "_time": "absolute designer time, s, t = 0 at plasma_initiation; the run used t >= 84.317598 s (PSC clock 0)",
          "_sign": "+|Ip| as shown to the Session Leader (YAML convention minus_ip: Ipl_ref = -Ip_IMAS)",
          "plasma_current": {"Ipl_ref": {"x": [float(t) for t in ref["time"]], "y": [float(a) for a in ref["value"]]}}}
    psc_refs = y.get("psc", {}).get("references", {})
    if psc_refs:
        wf["rzip"] = {"_status": "real (constant PSC references of the variant YAML, from the inverse slice; the run's own "
                                 "Rpl/Zpl/CSPF references to KCURR stayed on the fork path, D19)",
                      "Rpl_ref": {"x": [CUT], "y": [psc_refs["Rpl_ref"]["value"]]},
                      "Zpl_ref": {"x": [CUT], "y": [psc_refs["Zpl_ref"]["value"]]}}
        wf["cspf"] = {"_status": "real (constant, same source)", "_coils": "CS3U, CS2U, CS1, CS2L, CS3L, PF1..PF6, A per turn, IMAS sign",
                      "CSPF_curr_ref": {"x": [CUT], "y": [psc_refs["CSPF_curr_ref"]["value"]]}}

    # segments: PS.xml + BTree actions + the rules that start in / lead to them
    modes = {"_status": "real (constant modes of the run: cases/runs/evolutive_controller_105073_psc_<V>/configuration.ymmsl:167-172 "
                        "+ glue defaults; the PSC did not switch modes, D19)",
             "mcm": "constant", "controllers": {"shape_control": f"off / {RUN_MODES['Shape_control']}",
                                                "ip_control": f"kcurr / {RUN_MODES['control_Ip']}",
                                                "vs_control": f"vs1_vs3 / {RUN_MODES['VS_control_mode']}"},
             "main_settings": {"KCURR": RUN_MODES["KCURR"], "RZIp": RUN_MODES["RZIp"], "VS": RUN_MODES["VS"],
                               "PSModel": RUN_MODES["PSModel"], "AllocatorMode": RUN_MODES["AllocatorMode"],
                               "RefSmooth": "Off (omitted in the PSC wrapper copy)", "SNU": "n/a", "CLA": "Off"}}
    out = []
    for s in segs:
        a = actions.get(s["id"], {})
        kind = ("stop" if s["id"] == 99 else
                "hard_exception" if any(r["leads_to"]["segment"] == s["id"] and r["kind"] == "hard_sudden" for r in rules)
                or s["wd_target"] == "STOP" and s["id"] >= 40 else
                "soft_overlay" if any(r["leads_to"]["segment"] == s["id"] and r["kind"] == "soft_overlay" for r in rules) else
                "nominal")
        d = {"name": s["name"], "id": s["id"], "kind": kind, "_status": "real (PS.xml segment + BTree.xml RefGen action)"}
        if s["id"] == 99:
            d["refgen_action"] = a
            out.append(d)
            continue
        d["modes"] = [modes] if kind == "nominal" else []
        d["refgen_action"] = {k: a.get(k) for k in ("signal", "entryRule", "typeAddition", "wd_time", "wd_target", "condition") if k in a}
        d["transition_conditions"] = {
            "_status": "real (watchdog from PS.xml/BTree.xml; events from the rules)",
            "watchdog": {"wd_time": s["wd_time"], "wd_target": s["wd_target"],
                         "wd_target_id": next((t["id"] for t in segs if t["name"] == s["wd_target"]), None)},
            "next_segment": s["wd_target"],
            "exception_rules_active_here": [r["event"] for r in rules if r["kind"] == "hard_sudden" and
                                            f"{{current_segment}} != {s['id']}" in r["bt_condition"] or
                                            r["kind"] == "soft_overlay" and f"{{current_segment}} == {s['id']}" in r["bt_condition"]],
            "entered_by": [r["event"] for r in rules if r["leads_to"]["segment"] == s["id"]]}
        d["control_conditions"] = {"_status": "guess (presentation structure; the run had no per-segment control conditions)",
                                   "VS3_Failure_Management": "n/a", "VS3_Kicks": "n/a", "Dsep_Min": None}
        ipmax = events.get("ip_too_high", {}).get("threshold")
        zmax = events.get("z_excursion", {}).get("threshold")
        d["alarms"] = {"_status": "real thresholds (YAML events, global monitoring) in the presentation's alarm keys",
                       "Max_Ip": ipmax, "Max_Zpl_Ctrl_Error": zmax, "Maximum_Time": s["wd_time"]}
        tr = s["trajectories"].get("Ipl_ref")
        d["setpoints"] = {"_status": "real (PS.xml POINTs, segment-relative time, +|Ip| PCS frame)",
                          "ip_reference": ({"x": tr["x"], "y": tr["y"], "entry_rule": tr["entry_rule"], "exit_rule": tr["exit_rule"],
                                            "execution_rule": tr["execution_rule"]} if tr else
                                           "none: the last Ipl_ref value is held (PS.xml comment: SignalGenClass.m:164-169)")}
        others = {k: {"x": t["x"], "y": t["y"]} for k, t in s["trajectories"].items() if k != "Ipl_ref"}
        if others:
            d["setpoints"]["constant_references"] = others
        out.append(d)

    cmp = refgen_vs_ps(folder, v, segs)
    header = [
        f"PSPS-EQUIVALENT of the PSC run inputs of 2026-11-06, variant {v}; format status GUESS as in the presentation file "
        "(presentation file 105073_psps_pcs_dataset.json, kept outside this repository: tree = IDM ATCKX7 v1.0 s.34 moduleGroups/CTRL_Magnetic/PARAM "
        "+ the 2026 segment-editor mock-up fields, build vc59b3ce7); generated from the variant YAML and the four PSC files; "
        "not consumed by anything.",
        f"Window cut (D20): PSC clock t = 0 at designer t = {CUT} s; PS.xml POINT times are PSC-clock (segment-relative) seconds, "
        "WF times are absolute designer seconds. Ip as +|Ip| (PCS frame, YAML convention minus_ip: Ipl_ref = -Ip_IMAS).",
        "_status per block: real = taken from a run file; guess = structure only (presentation file); placeholder = value not from the run.",
        f"Generated by preprocessing/psps/psc_run/make_psc_psps_dataset.py from cases/input/psc/{v}/ "
        "of the IMAS-PDS fork (5620eb5 + P2d/P2e/PSC-4 changes).",
        f"Companion files: {v}_waveforms.yaml and {v}_segments.yaml (two-file designer format, "
        "preprocessing/psps/psc_run/make_psc_two_file_set.py)",
    ]
    data = {
        "_header": header,
        "pulse": int(g["pulse"]), "name": g["name"],
        "_run": {"_status": "real", "variant": v, "comment": g.get("comment"), "dd_version": str(g["dd_version"]),
                 "convention": g.get("convention"), "time_origin": g.get("time_origin"), "time_offset_s": g.get("time_offset_s"),
                 "psc_schedule_name": ps_name, "psc_schedule_comment": ps_comment,
                 "psc_outputs": {n: dim for n, dim in outputs}, "psc_parameters": params,
                 "psc_inputs": [i["name"] for i in y.get("psc", {}).get("inputs", [])],
                 "run_plasma_scenario": scen, "pulse_done_goal": goals,
                 "pulse_schedule_ids": pulse_schedule_ids_uri(v),
                 "pulse_schedule_ids_note": "ps_source.source_uri of the case override; received by the glue, "
                                            "logged only, not read by the PSC",
                 "refgen_export_vs_PS_xml": cmp},
        "datasets": {"PCS": {
            "WF": wf,
            "segments": out,
            "exception_rules": {"_status": "real (variant YAML events/exception_handling + PSCGlobalMonConfig.xml + BTree.xml)",
                                "rules": rules},
            "moduleGroups": {"CTRL_Magnetic": {"PARAM": param}},
        }},
    }
    text = compact(data, width=150) + "\n"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"psps_pcs_dataset_{v}.json").write_text(text)
    json.loads(text)
    return cmp


def main():
    ap = argparse.ArgumentParser(description="PSPS-equivalent PCS dataset JSON per PSC run variant")
    ap.add_argument("--inputs", default=str(INPUTS), help="folder with one sub-folder per variant")
    ap.add_argument("--out-dir", default=None, help="output folder (default <inputs>/<V>/psps_like)")
    ap.add_argument("--gains", default=None, help="KCURR_PFPO1_load_gains_tp.m (default under $PCS_PATH)")
    args = ap.parse_args()
    inputs = Path(args.inputs)
    framework = Path(os.environ.get("PCS_PATH") or PCS_NIGHTLY_DEFAULT)
    if not (framework / "pcssp" / "src" / "psc").is_dir():
        sys.exit(f"pcs-nightly not installed ({framework}/pcssp/src/psc missing): run pds_setup.sh with "
                 "INSTALL_PCS_NIGHTLY=true, or export PCS_PATH to a pcs + pcssp-nightly checkout")
    gains_m = Path(args.gains) if args.gains else framework / GAINS_REL
    param = gains_block(gains_m, framework / TP_REL, framework / SCHED_REL)
    print("PARAM status:", param["_status"])
    for v in VARIANTS:
        folder = inputs / v
        if not folder.is_dir():
            print(f"{v}: folder missing, skipped", file=sys.stderr)
            continue
        out_dir = Path(args.out_dir) if args.out_dir else folder / "psps_like"
        cmp = build(v, folder, out_dir, param)
        print(f"{v}: psps_pcs_dataset_{v}.json written; refgen vs PS.xml: {cmp}")


if __name__ == "__main__":
    main()
