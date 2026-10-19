# EC heating from waveforms: design

## The previous import and why it was wrong

The Waveform-Editor designs of the TORAX workflows (`workflows/inverse_convergence/waveforms.yaml`,
`workflows/evolutive_controller/waveforms.yaml` and their per-pulse copies) used to copy DINA's whole
`core_sources` (`core_sources/*: {ref: input}`) and relabel its `source(1)` as `ec`. DINA's `source(1)`
is the "total" source (additional + ohmic - radiation), so TORAX's `sources_from_IMAS()` prescribed that
net profile as ECRH, and its current-drive profile (bootstrap included) as EC current drive. The generic
`inverse_convergence` config had to keep TORAX's own ohmic source off and the radiation at ZERO to avoid a
double count, and `evolutive_controller` (ohmic already on) double-counted the ohmic heating anyway.

## The mechanism

- The EC heating is a designed waveform: `core_sources/source(1)` named `ec` (identifier index 3 as a
  constant tendency with an explicit `start`/`end` spanning the pulse, since a tendency is 0 outside its
  interval) with `global_quantities/power` as a piecewise-linear tendency reproducing DINA's
  `summary/heating_current_drive/power_additional` -- the only additional power DINA fills (`power_ec`,
  `power_nbi`, `power_ic`, `power_lh` and the `ec`/`nbi`/`ic` arrays of structures are empty in every
  entry used; `bin/pds-tendencies` checks and reports it).
- `bin/pds-tendencies` (`pds/tendencies.py`) reads that trace, fits the tendency (Douglas-Peucker on the
  power error, `--tol` default 0.1 MW, knots rounded, deviation re-measured against the rounded knots)
  and writes the entries into a per-pulse copy of the generic waveform file (`--write FILE
  --from GENERIC`; only the `core_sources/...` entries are replaced, everything else is kept, the
  command and the fit error are recorded next to them; `--check FILE` re-measures a stored tendency).
  Usage: `cases/pulses/README.md`, Step 0b.
- TORAX computes the EC deposition (`ecrh` gaussian, centre 0.30, width 0.33, fitted to DINA 105073's
  electron heating profile), the ohmic heating (`ohmic: {}`), the bremsstrahlung (Wesson) and the Mavrin
  impurity radiation itself, in both `workflows/<wf>/config_torax.py`.
- Requires TORAX-MUSCLE3 with power-only source support (`power_only_sources` in
  `torax_muscle3/torax_actor.py`), which maps an `ec` source carrying only `global_quantities/power` to
  `sources.ecrh.P_total`. Without it an `ec` source without `profiles_1d` goes through
  `sources_from_IMAS()` unchanged and yields at best no EC heating.
- `prescribed_transport` has no TORAX; the METIS workflows have no Waveform-Editor actor (their EC power
  is METIS's `pulse_schedule` input; `bin/pds-tendencies --ids pulse_schedule` prints that form for hand use).

## One file per pulse and workflow

Neither the Waveform-Editor yaml (`waveform_editor/yaml/yaml_parser.py`, `export/exporter.py`) nor
`bin/pds-configure` has an include/overlay mechanism for waveform files: `pds-configure` generates
settings overrides and, with `transport_calibration`, a calibrated `config_torax.py`, nothing else, and
the generic `waveforms.yaml` keeps `${SHOT}` placeholders and cannot carry pulse data. So each (TORAX
workflow, pulse) gets a copy of the generic file under `cases/pulses/files/<wf>_<case>_waveforms.yaml`
whose only difference is the EC entries (generated and marked, so a future pulse-level fragment merged by
`pds-configure` can replace them without touching the pulse files), referenced through
`settings.<wf>.waveform_editor.waveforms` in the pulse file. The generic files declare the `ec` source
with a 0 W placeholder: a case built without the per-pulse file runs without EC heating but does not crash.

## Fit errors (tolerance 0.1 MW; `bin/pds-tendencies <case> --check <file>`)

| case | DINA entry (DD) | samples | peak P_add | knots | max deviation |
|---|---|---|---|---|---|
| 105033 | hdf5 ITER/3/105033/1 (3.38.1) | 391 | 1.0 MW (1.2-1.3 s only) | 6 | 0.0056 MW |
| 105073 | mdsplus dina 105073/6 (3.39.0) | 39896 | 40 MW | 10 | 0.0126 MW |
| 105078 | mdsplus dina 105078/6 (3.39.0) | 40453 | 40 MW | 13 | 0.0737 MW |
| 105084, 105084_literal | hdf5 ITER/3/105084/1 (3.39.0) | 41602 | 3.0 MW | 9 | 0.0063 MW |
| 105092 | mdsplus dina 105092/1 (3.39.0) | 23610 | 1.0 MW | 9 | 0.0113 MW |
| 105099 | mdsplus dina 105099/2 (3.39.0) | 21159 | 17 MW | 11 | 0.0127 MW |

105078 and 105092 have `workflows: []` in their pulse file; their inverse_convergence waveform files are
ready but not referenced (comment in the pulse file). 105084's inverse_convergence file is ready too;
only evolutive_controller is listed for it.
