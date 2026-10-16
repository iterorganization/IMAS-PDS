# EC heating as designed tendencies instead of DINA's relabelled "total" source

Branch `feature/waveform_fix` (worktree of `feature/pulse-preprocessing` @ 2878e25), 2026-10-15.

## What changed and why

Until now every Waveform-Editor design of the TORAX workflows (`workflows/inverse_convergence/waveforms.yaml`,
`workflows/evolutive_controller/waveforms.yaml`, and the per-pulse copies
`cases/pulses/files/inverse_convergence_105073_waveforms.yaml`,
`evolutive_controller_105073_waveforms.yaml`, `inverse_convergence_105084_literal_waveforms.yaml`) copied
DINA's whole `core_sources` (`core_sources/*: {ref: input}`) and relabelled its `source(1)` as `ec`
(`core_sources/source(1)/identifier/name: [{value: ec}]`). DINA's `source(1)` is the "total" source
(additional + ohmic - radiation): TORAX's `sources_from_IMAS()` prescribed that net profile as ECRH, so
the generic `inverse_convergence` config had to keep TORAX's own ohmic source off and the radiation at
ZERO, while `evolutive_controller` (ohmic already on) double-counted the ohmic heating.

Now:

- the EC heating is a designed waveform: `core_sources/source(1)` named `ec` (identifier index 3 as a
  constant tendency with an explicit `start`/`end` spanning the pulse, since a tendency is 0 outside its
  interval) with `global_quantities/power` as a piecewise-linear tendency reproducing DINA's
  `summary/heating_current_drive/power_additional`;
- the TORAX actor puts that power into `sources.ecrh.P_total` (`power_only_sources()` in
  `torax_muscle3/torax_actor.py`, see "Pending" below) and TORAX computes the EC deposition
  (`ecrh` gaussian, centre 0.30, width 0.33, fitted earlier to DINA 105073's positive electron heating),
  the ohmic heating (`ohmic: {}`), the bremsstrahlung (Wesson, `bremsstrahlung: {}`) and the Mavrin
  impurity radiation (`impurity_radiation: {}`) itself, in both `workflows/inverse_convergence/config_torax.py`
  (before: ohmic off, bremsstrahlung ZERO, no impurity radiation, no ecrh block) and
  `workflows/evolutive_controller/config_torax.py` (before: ohmic on, bremsstrahlung ZERO,
  `impurity_radiation` = `P_in_scaled_flat_profile` 0.3, ecrh created dynamically from the DINA profile).
  `prescribed_transport` has no TORAX and never had the relabel; `torax_nice_utils` only holds plot
  utilities. The METIS workflows have no Waveform-Editor actor (their EC power is METIS's own
  `pulse_schedule` input; `bin/pds-tendencies --ids pulse_schedule` prints that form for hand use).

`power_additional` is the only additional power DINA fills: for all six pulses `power_ec`, `power_nbi`,
`power_ic` and `power_lh` of the summary are empty (0 points), and the `ec`/`nbi`/`ic` arrays of
structures are empty too (verified with imas-python 2.3.0 on the raw entries, see the table).

## The tool: `bin/pds-tendencies` (`pds/tendencies.py`)

Bash wrapper + Python module, same conventions as `bin/pds-configure` (loads
`IMAS-MUSCLE3/1.0.0-intel-2025b-pds` when the current python lacks PyYAML/numpy/imas; sets
`IMAS_VERSION=4.0.0` and `HDF5_USE_FILE_LOCKING=FALSE` unless set). Resolves the pulse like
`pds-create-case` resolves a case (`cases/pulses/<case>.yaml` `prepare.summary`/`prepare.source`, else
`$SCENARIOS_REPO/<shot>/source.env` `SUMMARY_URI`/`SOURCE_URI`) or takes `--uri`. The raw DINA entries
are DD 3 (HDF5 or MDSplus): the summary is read with `DBEntry.get("summary", autoconvert=False)`
(`autoconvert` is an argument of `get()`, not of `DBEntry()`; the paths used are identical in DD 3/4).
Fit: Douglas-Peucker on the power error (`--tol`, default 0.1 MW), knots rounded (times 2 decimals,
values 3 significant digits, more if the tolerance is lost by rounding; |P| < 1 W snapped to 0), the
maximum deviation re-measured against the rounded knots. `--write FILE` replaces the `core_sources/...`
entries of the `targets:` section line by line (all other lines and comments kept, the command and the
fit error recorded next to the entries, idempotent); `--from GENERIC` creates a missing FILE as a copy
of the workflow's generic file; `--check FILE` re-measures the stored tendency. Documented in
`cases/pulses/README.md` (Step 0b), `README.md`, `docs/source/contributing.rst`.

## File layout decision

Neither the Waveform-Editor yaml (`waveform_editor/yaml/yaml_parser.py`, `export/exporter.py` @ 08eebe8)
nor `bin/pds-configure` has an include/overlay mechanism for waveform files: `pds-configure` generates
settings overrides and, with `transport_calibration`, a calibrated `config_torax.py`, nothing else. The
generic `waveforms.yaml` keeps `${SHOT}` placeholders and cannot carry pulse data. So, as instructed for
that case, each (TORAX workflow, pulse) gets a per-pulse copy of the generic file under
`cases/pulses/files/<wf>_<case>_waveforms.yaml` whose only difference is the EC entries (header line
says so; generated and marked, so a future pulse-level fragment merged by `pds-configure`, in the spirit of
the calibrated TORAX config, can replace them without touching the pulse files), referenced through
`settings.<wf>.waveform_editor.waveforms` in the pulse file. The generic files now declare the `ec`
source with a 0 W placeholder (loud comment): a case built without the per-pulse file runs without EC
heating but does not crash.

## Pulses converted (tolerance 0.1 MW; `bin/pds-tendencies <case> --check <file>`)

| case | DINA entry (DD) | samples | peak P_add | knots | max deviation | files |
|---|---|---|---|---|---|---|
| 105033 | hdf5 ITER/3/105033/1 (3.38.1) | 391 | 1.0 MW (1.2-1.3 s only) | 6 | 0.0056 MW | inverse_convergence (new), evolutive_controller (new); pulse file `settings:` added |
| 105073 | mdsplus dina 105073/6 (3.39.0) | 39896 | 40 MW | 10 | 0.0126 MW | inverse_convergence, evolutive_controller (existing files, entries replaced) |
| 105078 | mdsplus dina 105078/6 (3.39.0) | 40453 | 40 MW | 13 | 0.0737 MW | inverse_convergence (new; `workflows: []`, so not referenced, comment in the pulse file) |
| 105084 | hdf5 ITER/3/105084/1 (3.39.0) | 41602 | 3.0 MW | 9 | 0.0063 MW | evolutive_controller (new, referenced), inverse_convergence (new, ready, not listed) |
| 105084_literal | same entry | 41602 | 3.0 MW | 9 | 0.0063 MW | inverse_convergence (existing file, entries replaced) |
| 105092 | mdsplus dina 105092/1 (3.39.0) | 23610 | 1.0 MW | 9 | 0.0113 MW | inverse_convergence (new; `workflows: []`, comment in the pulse file) |
| 105099 | mdsplus dina 105099/2 (3.39.0) | 21159 | 17 MW | 11 | 0.0127 MW | inverse_convergence (new); pulse file `settings:` added |

No DINA source was unavailable. The 105033 "total" source carried no heating at all (its
`inverse_convergence_105033_config_torax.py` of the main checkout only switched ohmic on); the generic
config now has ohmic on, so that uncommitted file and its `python_config_module` setting were not brought
into this branch (nothing to `git rm`: neither was ever committed).

## Pending: TORAX actor patch to upstream

`power_only_sources()` (`torax_muscle3/torax_actor.py`, diff `torax_actor_power_only_sources.diff` in the
PDS notes repository) is an uncommitted local change of `local_installs/TORAX-MUSCLE3` (origin
iterorganization/TORAX-MUSCLE3 @ f375ae2). It must be upstreamed to
https://github.com/iterorganization/TORAX-MUSCLE3 and the `torax` module of
`workflows/lib/easybuild_programs.ymmsl` rebuilt: with the module actor, an `ec` source without
`profiles_1d` goes through `sources_from_IMAS()` unchanged (`_extract_source_profiles` returns empty
arrays; outcome UNVERIFIED, at best no EC heating). Until then the CI end-to-end cases
`inverse_convergence 105073` and `evolutive_controller 105073` (`ci/run_test_workflows.sh`) run with the
module actor and must be expected to differ or fail. The v2 run with the patched actor on 105073
(job 1286005, 2026-10-15) converged like the reference. No simulation was run for this branch.

## Checks run in the worktree

`ruff check .` (2 pre-existing UP038 findings in `workflows/lib/actors/outer_convergence_loop.py`, identical on
the main checkout, none in the touched files), `ruff format --check .` (clean), `uvx ty check .`
(`ty 0.0.88`, module python: 7 pre-existing diagnostics in `docs/source/conf.py` and
`workflows/torax_nice_utils/plot_validation.py`, none in `pds/tendencies.py` after two fixes),
`ci/check_ymmsl.py` (all checks passed), `bash -n` on every `bin/` script, `pds-configure --dry-run` on
all seven pulse files (ok), yaml parse of every waveform file. Not run: `uv sync` + docs build, the
Bamboo end-to-end cases (Slurm, patched actor needed).
