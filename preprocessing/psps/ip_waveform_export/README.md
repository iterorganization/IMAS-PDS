# ip_waveform_export: one Ip reference with segments, three exports

Phase **P3** prototype of the PSPS-to-KCURR data-chain plan, sections 6 and 7 (the study notes, kept outside this repository), with
the P5 validation seed and a PROPOSED exception-handling example. It takes ONE designer-level data
item, the **Ip reference waveform with segment structure**, written once in a Waveform-Editor-style
YAML file (format 0), and exports it three ways:

| # | Export | Module | Maturity of the target format |
|---|---|---|---|
| 1 | IMAS `pulse_schedule` IDS (DD 4 and DD 3) | `export_pulse_schedule_ids.py` | Ip node chosen from the loaded DD at run time (imas-python 2.3.0; DD 3.42.0, 4.0.0, 4.1.1 tested); **segments as `event(:)` = proposal** |
| 2 | PCSSP PSC RefGen XML schedule | `export_refgen_xml.py` | format implemented on `pcs@add-AM`; element/attribute set verified against the reference file; reading rules checked against a Python re-implementation of `parsePSXML.m`, **not yet run through the MATLAB parser** |
| 3 | PSPS "WF" dataset JSON | `export_psps_json.py` | **BEST-GUESS**: structure inferred from slides (IDM 97XLXP slide 10, IDM ATPUWU 2024 demo); to be replaced by the PCS v1.1 dataset schema from pulseconfig.iter.org |
| – | validation (P5 seed) | `validate.py`, `--validate` | structure rules + limits from a YAML file with **PLACEHOLDER** values |
| – | exception-handling example (D9) | `export_refgen_eh_example.py`, `--refgen-eh-example` | **PROPOSAL / ILLUSTRATIVE** (superseded for the PSC by PSC-3) |
| 4 | PSC configuration: interface, global monitoring, behaviour tree, schedule (PSC-3) | `export_psc_config.py`, `--psc-config` | **PROPOSAL**; formats of `pcs@add-AM` TC01 + `BTreeFWHL.xml`; loaded by the PSC's own parsers and objects in MATLAB (2026-11-06) |
| – | D20 window cut | `cut.py`, `--cut-at T` | applies to every export |

Design rule (plan section 6): one source, three exports; segments are authored once and never
re-typed downstream. Decisions D8-D12 below were taken by the user on 2026-11-02.

## Input: Waveform-Editor-style YAML + PROPOSED `segments:` and `signals:` blocks

The waveform part follows the PDS Waveform-Editor files (e.g. `cases/pulses/files/*_waveforms.yaml`
in IMAS-PDS): a `globals` block and, under any section key, `<IDS path>: - {time: [...], value: [...]}`
(one piecewise-linear tendency). Example: `examples/ip_105073_like.yaml` (values illustrative,
NOT the DINA 105073 data).

```yaml
globals:
  dd_version: 4.0.0
  pulse: 105073
  name: ip_105073_like
  convention: minus_ip            # D11; optional, default minus_ip (may also sit on the entry)
  time_origin: plasma_initiation  # D10; the only implemented value
  time_offset_s: 0.0              # D10; optional, added to absolute times at export
references:
  pulse_schedule/flux_control/ip/reference:
    - {time: [0, 2.5, ...], value: [0, 0.5e6, ...]}      # -Ip (ITER: positive), A, s
segments:                                                # PROPOSAL
  - {name: ramp-up,   id: 0, start: 0.0, end: 70.0}      # wd_target defaults to the next name
  - {name: flat-top,  id: 1, end: 195.0}                 # start defaults to the previous end
  - {name: ramp-down, id: 2, duration: 75.0}             # end or duration
  - {name: STOP,      id: 99}                            # zero duration, id = --stop-id
signals:                                                 # PROPOSAL, optional (this is the default)
  pulse_schedule/flux_control/ip/reference: Ipl_ref
```

**The `segments:`, `signals:` and `exceptions:` blocks and the `convention`, `time_origin`,
`time_offset_s` keys are proposals** of this prototype; they are not part of the Waveform-Editor
format today (adding segments to the 1D editor is phase P4 of the plan).

### Segment identifiers (D8)

As on `pcs@add-AM` `reference/PS_NominalWaveforms.xml`: the first segment ("ramp-up") has id 0,
the following nominal segments 1, 2, ..., the terminal STOP segment id 99; there is no separate
"init" segment. The example is ramp-up 0, flat-top 1, ramp-down 2, STOP 99. `--stop-id 65535`
(or `globals.stop_id`) selects the IPP D15 strawman convention. **This convention may change
depending on what the PSC expects** (open item 3).

Rules enforced by `model.validate` (raised at load; listed by `--validate`):

- time strictly increasing, finite, at least two vertices; a warning if any Ip > 0 in the IMAS
  sign (ITER Ip < 0);
- segment ids and names unique, ids in 0..65535; first segment id 0, nominal ids successive
  0, 1, 2, ...; last segment `STOP` with the configured STOP id, zero duration, no `wd_target`;
- segments contiguous, every non-STOP segment of positive duration, the chain covers the
  waveform exactly (first start = first vertex, STOP time = last vertex);
- `wd_target` of each segment = name of the next one (only a linear chain is supported);
- `time_origin` = `plasma_initiation`, `time_offset_s` finite.

Waveforms are defined independently of the segments: vertices need not sit on segment
boundaries; each export cuts the waveform at the boundaries by linear interpolation.

## Sign convention (D11)

The Session Leader edits −Ip: in the designer YAML the Ip values are positive numbers (ITER Ip is
negative in IMAS). The key `convention:` on the waveform entry or in `globals:` (both allowed; an
error if they disagree) takes:

- `minus_ip` (default for the designer file): YAML values = −Ip; every value must be ≥ 0, a
  negative value is an error naming its time ("set `convention: imas` if the file holds
  IMAS-sign values");
- `imas`: values already in the IMAS sign (for files produced by tools).

The reader converts to the IMAS sign; the model always holds the IMAS sign.

| Stage | Quantity written | ITER sign | Where the sign is applied |
|---|---|---|---|
| designer YAML, `convention: minus_ip` | −Ip | positive | `read_yaml._to_imas` (× −1 on input) |
| designer YAML, `convention: imas` | Ip (IMAS) | negative | none |
| model (`IpWaveform.value`) | Ip (IMAS) | negative | – |
| pulse_schedule IDS (stored IMAS data) | Ip (IMAS) | negative | none: IMAS sign kept |
| RefGen XML `Ipl_ref` | PCS frame = −Ip | positive | `export_refgen_xml` (`IMAS_TO_PCS_IP_SIGN = -1`), documented by `PARAMETER ImasToPcsIpSign = -1` (relation IDS → PCS) |
| PSPS JSON `ip_reference.y` | −Ip as displayed to the SL | positive | `export_psps_json`; `_sign_note`: "displayed as −Ip; sign convention of the real PSPS dataset to be confirmed" |

Units are SI throughout (A, s).

## Time origin (D10)

t = 0 is the plasma initiation in the designer file (`globals.time_origin: plasma_initiation`, the
only implemented value). Reserved, rejected with an explanatory error: `control_handover_T0` and
`dina`; **the offset between plasma initiation and T0 (or the DINA time base) is a decision still
to take**. When a target needs another origin, `globals.time_offset_s` (default 0) is added to the
absolute times at export: IDS `time`, `flux_control/time` and `event(:)/time_stamp`. The RefGen
XML POINTs and the JSON `x` vectors are segment-relative and therefore unchanged; the JSON records
`time_origin` and `time_offset_s` in `_conventions`.

## The three exports

**RefGen XML** (`<name>_refgen.xml`). `SCHEDULE` root with the reference's `xsi:schemaLocation`;
`DECLARATIONS/PARAMETERS` (always written: `parsePSXML.m` defines `ListParams` only inside a
PARAMETERS block and passes it to every segment) and `DECLARATIONS/OUTPUTS/SIGNAL name="Ipl_ref"`
with the attribute set of the reference declaration; per timed segment a
`SEGMENT name id wd_time wd_target` (wd_time = duration, wd_target = next name) holding one
`SIGNAL_TRAJECTORY name="Ipl_ref"` with `EXECUTION_RULE is="Linear"`, `ENTRY_RULE is="Step"`,
`EXIT_RULE is="last"` (the only values used by the 32 trajectories of the reference) and
`REFERENCE/POINT time value` (segment-relative times); the STOP segment has `name` and `id` only,
as in the reference.

**PSPS JSON** (`<name>_psps_wf.json`), BEST-GUESS:
`{"pulse_schedule": {"name", "id", "segments": [{"name", "id", "duration", "setpoints":
{"ip_reference": {"x": [...], "y": [...]}}}]}, "_note", "_status": "BEST-GUESS", "_sign_note",
"_conventions"}`. STOP is listed with duration 0 and no set-point. The 2024 demo also had
`segment_id` and `modulation_gate` set-points; they are not written.

**pulse_schedule IDS** (`<out-dir>/ids`, HDF5) (D12). The DD version is selectable with
`--dd-version` (else `globals.dd_version`, else 4.0.0, the version PDS uses). The Ip node is
detected in the loaded DD and the one that exists is filled:

| DD version (tested) | Ip reference node | `event(:)` |
|---|---|---|
| 3.42.0 | `pulse_schedule.flux_control.i_plasma` | present |
| 4.0.0 (default) | `pulse_schedule.flux_control.ip` | present |
| 4.1.1 | `pulse_schedule.flux_control.ip` | present |

(verified with imas-python 2.3.0 `IDSFactory(version=...).pulse_schedule()`, 2026-11-02; each
version is written and read back by `test_ids_roundtrip`). `ids_properties.homogeneous_time = 0`;
`time` and `flux_control/time` = waveform vertices plus segment boundaries (+ `time_offset_s`);
`<ip node>/reference` in the IMAS sign and `reference_name = ip_reference`; one `event(:)` per
segment [proposal]: `type/name = pcs_segment`, `identifier = segment:<id>:<name>`, `time_stamp` =
start (+ offset), `duration`. Any other field absent from the loaded DD is skipped with a warning.
imas-python is imported lazily, so the other exports work without IMAS.

## Validation (P5 seed)

`validate.check(design, limits)` returns a list of `Violation(rule, message, segment, time, value,
limit)` (empty = valid) and never raises on a rule. It reuses the structural rules of
`model.validate` (monotonic time; segments contiguous, covering, ids unique, STOP last, ...) and
adds limits read from a YAML file, default `limits/ip_limits_example.yaml`:

| Limit | Example value | Status |
|---|---|---|
| \|Ip\| max at every vertex | 15.0 MA | PLACEHOLDER; equals the TC01 monitoring threshold `glb_ps__ip_too_high = {ip_ip__meas.value} > 15e6`, `pcs@bb29ad6` (add-AM) `top-models/magnetic-control/CREATE_TC_01/PSC_config/PSCGlobalMonConfig.xml:17-19` |
| \|dIp/dt\| max on each linear piece | 0.3 MA/s | PLACEHOLDER |
| minimum duration of the segments named in `flat_top_segment_names` | 50 s | PLACEHOLDER |

Each violation names the segment and the time (designer origin) where it occurs. **The values are
illustrative: the real limits must come from Operations (Operational Limits and Conditions, OLC).**
This function is the P5 seed, intended to become a function registered in the PSPS CVVF
(Configuration Verification & Validation Framework; IDM 4F2JYS; IDM 2PVHKE p.4). CLI:
`--validate [--limits file]` prints the report (exit code 4 on violations); combined with export
flags, the exports are written only when there is no violation.

## Exception-handling example (D9) — PROPOSAL / ILLUSTRATIVE

`--refgen-eh-example` with `examples/ip_105073_like_with_exceptions.yaml` (same nominal waveform
plus a PROPOSED `exceptions:` block) writes, in addition to the nominal `<name>_refgen.xml`:

- `<name>_refgen_eh.xml`: the nominal schedule plus, after STOP (as in `PS_FWHLEH.xml`),
  - SOFT exception segment id 20 `ip_reduce_on_heating_loss` (`wd_time 30`, `wd_target
    ip_termination`): one `SIGNAL_TRAJECTORY Ipl_ref` whose POINTs are a **scale factor**
    1.0 → 0.8 over 10 s (ENTRY `None`, EXIT `Last`, EXECUTION `Linear`, as in FWHL). It is meant
    to be applied by the behaviour-tree action `typeAddition='silence,scale'`; on `PSC-FWHL`
    RefGen composes `Value = base .* scale + offset` (`pcssp@2233365`
    `generic/psc/+REFGEN/+MODEL/SignalGenClass.m` l.411-439). Pattern: `PS_FWHLEH.xml` l.184-201
    (segment 20, `FUNCTION code`, used with `silence,offset`);
  - HARD exception termination segment id 41 `ip_termination` (`wd_target STOP`): `Ipl_ref` from
    the nominal maximum (15 MA, PCS frame) to 0 over 60 s, modelled on FWHL segments 41/51;
- `<name>_btree_eh.xml`: a Groot behaviour tree modelled on `pcs@add-AM`
  `BTreeNominalWaveforms.xml` plus the FWHL priority structure (reactive Fallback
  `FallbackNomEH`): [1] `FallHrdEHListSudden`: when `{glb_ps__ip_too_high} == 1`, AssignValue
  `41 → {current_segment}`; [2] `ParSegNom`: the nominal segments (Preconditions on
  `{current_segment} == 0/1/2/99`, RefGen `replace` with `wd_time` = duration and `wd_target` = next
  id; STOP self-loop `wd_time 5` as in add-AM) in Parallel with the soft-EH overlay
  (`Precondition {heating_loss} == 1` → `Action ID="RefGen" signal='Ipl_ref' segmentID='20'
  entryRule='Linear' typeAddition='silence,scale' condition='{heating_loss} == 0' wd_time="30"
  wd_target="41"`); [3] `FallHrdEHList`: segment 41 (RefGen `replace`, `wd_target 99`).

Caveats, all part of the proposal:

- the trigger `heating_loss` is a **hypothetical** blackboard signal (not defined in any PCS
  configuration). Physically Ip is driven by the CS/PF circuits, not by heating; the story is
  "the operating point changed after the loss of a heating source → the Ip target is scaled down
  as a precaution";
- TC01 declares `glb_ps__ip_too_high` (`PSCGlobalMonConfig.xml:17-19`, `PSCIntConfig.xml:90-91`)
  but **no behaviour tree consumes it**; its use here is invented;
- the termination ramp starts from the nominal maximum, not from the current reference value; a
  real termination needs a rate-limited ramp from the actual value (FUNCTION or entry-rule
  semantics to be checked with the PSC team);
- whether a `scale` trajectory may be defined on `Ipl_ref` itself (dimensionless values on an
  Amplitude signal) is not verified; nothing was run through MATLAB `parsePSXML.m` / RefGen /
  the PSC. Tests check that the EH XML parses with the Python re-implementation of the
  `parsePSXML.m` rules and that the BT XML is well-formed with the expected node ids.

## PSC-3: the four PSC configuration files (`--psc-config`) and the window cut (`--cut-at`) — PROPOSAL

Plan: the PSC-in-the-loop plan §4 (the study notes, kept outside this repository); decisions D16-D20 (2026-11-06). Example:
`examples/ip_105073_psc.yaml` (the P2e "+3 %" edit of 105073 plus three PROPOSED blocks):

- `psc:` interface inputs (all `Pcssignal`, read as `{name.value}`): `ip_ip__meas` (PCS frame,
  = -Ip_IMAS), `plasma_exist` (bus element `plasma_state__exist_diag`, as TC01), `z_meas`,
  `cs_margin`; `run_plasma_ip_min` (SCENARIO, as TC01); `references:` constant schedule signals
  with a mandatory `source` (example: `CSPF_curr_ref[11]`, `Rpl_ref`, `Zpl_ref` from the
  inverse_convergence 105073 slice at 84.317598 s);
- `events:` (segment data model of `magnetic_control_supervision_and_segments.md` §8): `name:
  {description, signal, op (> >= < <=), threshold, [reference: number or name -> abs(signal -
  reference)], [release_threshold] (hysteresis), [latch], debounce}` or `{description, expr,
  signals}` with `expr` in PSC script syntax. Each event becomes a MONITORING whose output flag
  is `glb_ps__<event>`; latch and hysteresis are written into the script (the flag reads its own
  previous value);
- `exception_handling:` `hard_sudden: [{event, target}]` (priority [1]), `soft: [{name, id, event,
  signal, type_addition, entry_rule, points{time,value} | hold: true, recovery, wd_time,
  wd_target}]` ([2]), `hard: [{name, id, from_value, to_value, ramp_s, hold_s, wd_target: STOP}]`
  ([3]). Values are in the frame of the PSC signal (Ip positive PCS frame), independent of
  `globals.convention`.

Files written to `<out-dir>/psc_config_<name>/` (names for the PSC mask fields):

| File | Format modelled on | Content |
|---|---|---|
| `PSCIntConfig.xml` | TC01 `PSCIntConfig.xml` (`AP_CONF`, `USAGE name class` + `SIGNAL name type dimension value description`) | inputs above; outputs `Ipl_ref` + the references (`psc_ref__*`); the TC01 internals (`current_segment` default = id of the first kept segment, `SegmentTime`, `simTime`, ...) and one boolean `glb_ps__<event>` per event; no `glb__ip_valid` |
| `PSCGlobalMonConfig.xml` | TC01 `PSCGlobalMonConfig.xml` (same namespaces; four sections) | SCENARIO `glb_ps__run_plasma`; SIGNAL_VALIDS empty (see caveats); one MONITORING per event, e.g. `{ip_ip__meas.value} > 15250000.0`, `{cs_margin.value} < 8000.0 or {glb_ps__end_of_flux} == 1`, `abs({z_meas.value} - 0.261) > 0.02 or ({glb_ps__z_excursion} == 1 and abs(...) > 0.01)`; GOAL `{simTime} > <schedule length>` |
| `BTree.xml` | `BTreeFWHL.xml` priority structure + add-AM nominal subtrees | `FallbackNomEH` (reactive): [1] `FallHrdEHListSudden` (guarded Precondition -> ForceFailure(AssignValue old, AssignValue 41)); [2] `ParSegNom` = nominal list (RefGen `all` `replace`, `wd_time` = duration, `wd_target` = next id, STOP self-loop 5 s) in Parallel with `ParSftEHList` (overlays only while a nominal segment is active); [3] `FallHrdEHList` (RefGen `all` `replace` `entryRule='Linear'`, then STOP) |
| `PS.xml` | `export_refgen_xml` + TC01 vector POINTs `[a, b, ...]` | nominal `Ipl_ref`; the constant references in every nominal segment; soft segments (21 ramp-down `Ipl_ref` points; 22 hold = no trajectory, RefGen holds the last value, `SignalGenClass.m:164-169`); hard segment 41 (`from_value` -> `to_value` over `ramp_s`, held `hold_s`); `wd_time`/`wd_target` identical to the BT (only the BT values are read) |

`--cut-at T` (D20; `cut.py`): drops the timed segments that end at or before T, starts the
segment that contains T at T (its POINTs shifted by T minus its original start, an interpolated
first POINT at 0, `wd_time` shortened by the same amount), drops the earlier waveform vertices
and inserts the interpolated vertex at T. Segment ids are kept (the interface default of
`current_segment` follows). The offset is recorded in the RefGen XML (`comment` attribute and an
XML comment), the BT header comment, the IDS `ids_properties.comment`
(`psc_clock_offset_s = T + time_offset_s`; IDS times stay absolute) and the JSON `_conventions`.
For 105073: `--cut-at 84.317598` (first NICE slice), shift 5.100 s, flat-top `wd_time` 10.5 s.

MATLAB check (2026-11-06, MATLAB 2023b-r5, pcssp-nightly ebf3ee0; details and job ids in
the study notes, kept outside this repository): the four files (cut and uncut) load
through `PSC.MODEL.parserPSCInterface`, `BBoard.populateBB`, `parserGlobMonConf` + `EHGlobalMon`,
`parsePSXML` + `RefGenerator.loadDP`, `BT.MODEL.parseXML` + `BTreeClass` and `PSC.PSCClass` without
error (the obsolete `BBOARD.parserGlobMonInterface` fails on TC01's file and ours alike). Dry PSC
executions (stepImpl sequence outside Simulink) of the four D17 scenarios behave as designed, with
two PSC behaviours to know: leaving a soft overlay is a step (no exit blend), and a watchdog
escalation from a soft overlay to a hard segment re-exposes the silenced base trajectory first.

Caveats: no debounce exists in the PSC global monitoring (`EHGlobalMon.m:115-165`: SCRIPT,
PRECONDITION, VALIDATION only), a `debounce` > 0 is written as a comment and warned about; no
SIGNAL_VALID is generated (`SignalValClass.m:98-160`, ebf3ee0: wall-clock timers, inverted RUNNING
test, undefined `PcsQuality`); the Z excursion is measured against the P2e start Z 0.261 m, not
against `Zpl_ref` (0.2487 m in the inverse equilibrium, 1.2 cm away); the `end_of_flux` threshold
8.0 kA is a PLACEHOLDER (CS3L headroom 8.12 kA at 84.3176 s); the `CSPF_curr_ref` order
[CS3U, CS2U, CS1, CS2L, CS3L, PF1..PF6] and frame (pf_active per turn, IMAS sign, as passed by
the fork glue) must be checked against the fork wrapper (14-wide input today) in PSC-4.

## How to run

```bash
cd preprocessing/psps/ip_waveform_export
python3 ip_waveform_export.py --yaml examples/ip_105073_like.yaml --out-dir /scratch/users/$USER/ipwf_out \
    [--refgen] [--psps-json] [--ids [--dd-version 4.0.0]] [--stop-id 99]   # no flag = --refgen --psps-json
python3 ip_waveform_export.py --yaml examples/ip_105073_like.yaml --validate [--limits limits/ip_limits_example.yaml]
python3 ip_waveform_export.py --yaml examples/ip_105073_like_with_exceptions.yaml --out-dir ... --refgen-eh-example
python3 ip_waveform_export.py --yaml examples/ip_105073_psc.yaml --out-dir ... --cut-at 84.317598 \
    --psc-config [--refgen --ids]                          # PSC-3, D20
python3 -I -m pytest -q                                   # pytest.ini sets pythonpath = .
```

Exit codes: 0 ok, 2 invalid input, 3 IMAS unavailable, 4 validation violations.

Requirements: Python >= 3.10 (developed for 3.11), PyYAML, numpy, pytest; for `--ids` and the IDS
tests, imas-python, e.g. `module use /work/projects/pds/modules/all; module load
IMAS-MUSCLE3/1.0.0-intel-2025b-pds`. Note that `python3 -I` ignores `PYTHONPATH`, so the module's
packages are not seen under `-I`; the tests were run with `-I` in a venv over the module Python
that lists the module `PYTHONPATH` in a `.pth` file. Without imas the IDS tests are skipped.

Tests (`tests/`, helper `tests/psxml_rules.py` = Python re-implementation of the `parsePSXML.m`
reading rules, POINT and FUNCTION references): `test_roundtrip.py` (example + a synthetic design
whose segment boundaries fall inside slopes: XML structure vs reference, parser reconstruction
within 1e-9, JSON structure/sign/reconstruction, IDS round trip for DD 3.42.0 / 4.0.0 / 4.1.1,
default DD and time offset, segment rules); `test_conventions.py` (D11 conventions, D10 time
origin, D8 ids); `test_validate.py` (P5 limits, located violations, CLI); `test_eh_example.py`
(FWHL references parse, EH schedule parse, BT structure and node ids); `test_psc_config.py`
(PSC-3: cut values/ids/offset, schedule parse with the parsePSXML rules and reconstruction, global
monitoring scripts, every `{name}` in scripts and BT conditions declared in the interface with
`.value` exactly for inputs, BT priority order and BT = schedule watchdogs, invalid blocks, debounce
warning, CLI, IDS offset metadata).

## Reference files (`reference/`)

| File | Source |
|---|---|
| `PS_NominalWaveforms.xml` | `pcs@bb29ad6` (branch add-AM), `top-models/magnetic-control/CREATE_TC_01/PSC_config/` |
| `BTreeNominalWaveforms.xml` | same commit and directory (behaviour tree using segment ids) |
| `parsePSXML.m` | `pcssp-nightly@ebf3ee0` (PSC merge branch), `src/psc/+REFGEN/+MODEL/`; the three header lines naming the author are replaced by `[redacted]`, the code is unchanged |
| `PS_FWHLEH.xml` | `pcssp@2233365` (branch PSC-FWHL), `generic/psc/Tests/assets/`; no author line present, copied unchanged |
| `BTreeFWHL.xml` | same commit and directory; no author line present, copied unchanged |

## Open items

1. 2026-11-02: the nominal and the exception-schedule RefGen XMLs were parsed without error by
   `REFGEN.MODEL.parsePSXML` (`pcssp-nightly@merge_IGZ_PSC` ebf3ee0, MATLAB 2023b; results in
   the study notes, kept outside this repository). RefGen and PSC execution itself is
   still untested.
2. Replace the JSON guess by the PCS v1.1 dataset schema (pulseconfig.iter.org); confirm the sign
   convention of the real PSPS dataset (−Ip displayed today, `_sign_note`) and units, and whether
   `segment_id` / `modulation_gate` set-points are mandatory.
3. Agree with the PCS team on the segment identifiers (D8 follows add-AM: ramp-up 0, STOP 99; the
   PSC may expect 65535 or an init segment), `wd_target` by name (PS XML) vs by id (behaviour
   tree), and whether generated behaviour trees are wanted.
4. Agree on the encoding of segments in the pulse_schedule IDS (`event(:)` is a proposal). The DD
   naming is now verified for 3.42.0 (`i_plasma`) and 4.0.0 / 4.1.1 (`ip`); the exact DD release
   of the rename between 3.42 and 4.0 was not checked.
5. D10: decide the offset between plasma initiation and the control hand-over T0 (and the DINA
   time base) before implementing the reserved origins `control_handover_T0` / `dina`.
6. P5: replace the PLACEHOLDER limits by Operations (OLC) values, add the missing checks (coil
   currents, flux consumption, ...), and register the function in the CVVF (IDM 4F2JYS).
7. D9 example: agree with the PSC team on real triggers (no `heating_loss` signal exists; the
   TC01 `glb_ps__ip_too_high` is not consumed), on `scale` trajectories on `Ipl_ref`, and on a
   termination that starts from the actual Ip.
8. Only Ip is supported; coil-current references (`CSPF_curr_ref`, PSPS7-9 mock-up) would follow
   the same pattern with multi-dimensional values. Non-linear segment chains, time-skip and
   conditional transitions are not handled in the nominal chain.
9. The `ImasToPcsIpSign` PARAMETER is an addition of this prototype (needed so that the parser
   finds a PARAMETERS block); check that RefGen ignores unknown parameters.
10. PSC-3 (2026-11-06): soft -> hard escalation starts the hard segment's blend from the silenced base
    trajectory, not from the overlay value (resetPathHandler at the segment change); the PSC clock must
    start at 0 (`PSCSysObj.m:66-70` defaults; a Simulink start at 84.3176 s gives a first dt of 84.3 s);
    the end_of_flux threshold is a PLACEHOLDER (PSC-1); the `CSPF_curr_ref[11]` order/frame against the
    fork wrapper is UNVERIFIED; debounce is not representable in the PSC global monitoring.
