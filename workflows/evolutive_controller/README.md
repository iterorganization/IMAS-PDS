# evolutive_controller

## What it does

A MUSCLE3 workflow that runs TORAX and NICE in genuine evolutive (forward, lockstep)
co-simulation, self-consistently, with a PCSSP magnetic controller closing the coil-current
feedback loop.

Unlike `inverse_convergence` or `prescribed_transport`, this
workflow has TORAX and NICE step forward together: each internal step, TORAX evolves
temperature and hands `equilibrium` + `core_profiles` to `nice_evo_rd`, which does the
resistive diffusion and returns the updated `equilibrium` for TORAX's next geometry. NICE
owns psi: TORAX runs with `evolve_current: False` and takes psi and I_p from that
equilibrium (`profile_conditions` `psi_source`/`I_p_source: geometry`), never from the
inverse_convergence core_profiles. This needs TORAX >= 2.0.0 (per-step `psi_source`),
and TORAX's sawtooth model is off since it only redistributes when TORAX evolves the
current. TORAX computes its own ohmic
heating and impurity radiation self-consistently from its evolving profiles (see
`config_torax.py`) rather than importing them from DINA; only the EC power is imported, via
`waveform_editor.core_sources_out -> torax.core_sources_in_f`, as in `inverse_convergence`.

**F_INIT bootstrap**: `source` reads a NICE-*reconstructed* equilibrium (not raw DINA -- see
Assumptions) from a completed `inverse_convergence` run's `_out_nice`. The `waveform_editor` passes that equilibrium through whole (an `equilibrium/*: {ref: eq}`
wildcard import in `waveforms.yaml`, so every field survives, not just hand-picked ones) and
overlays it with that same run's converged TORAX core_profiles and NICE coil currents, plus
the static machine description, EC power and coil voltages from this scenario's DINA data
(inverse_convergence never writes those), into one assembled F_INIT message for `torax`,
`nice_evo_rd`, and `magnetic_controller`. `preprocess.sh` (run by `pds-create-case`) copies
the TORAX core_profiles into the case, dropping TORAX's repeated axis grid point: its psiN
starting 0, 0 makes NICE evo_rd's F decomposition divide by zero and NaN on the first solve.

A PCSSP `magnetic_controller` (MATLAB/Simulink, see `controllers/KCURR_RZIp/`) reads NICE's `equilibrium`
+ `pf_active` every step and returns a corrected `pf_active`.

Structure lives in `workflow.ymmsl`; shared knobs (including a default `waveforms.yaml`
template) in `settings.ymmsl`; per-shot solver timing (the flattop window genuinely differs
per pulse, so has no sane generic default) in `cases/overrides/evolutive_controller_<shot>.ymmsl`
(105084's restricts the run to flattop only, see below).

## Running it

Requires a
completed `inverse_convergence` case run for the same shot (`bin/pds-create-case
inverse_convergence <shot>` + `bin/pds-run-case.sbatch`, which writes to
`cases/runs/inverse_convergence_<shot>/out_nice` -- this workflow's `source` reads from there).
Then build a case folder and hand it to SLURM:

```bash
bin/pds-create-case evolutive_controller 105084       # -> cases/evolutive_controller_105084
sbatch bin/pds-run-case.sbatch cases/evolutive_controller_105084
```

`pds-create-case` stacks `workflow.ymmsl`, `settings.ymmsl` (resources, shared knobs), and
`cases/overrides/evolutive_controller_<shot>.ymmsl` if it exists into numbered files under
the case folder; `pds-run-case.sbatch` runs that folder under `muscle_manager`, writing to
`cases/runs/<case>`.

## PSC and MCLS case (ip_story_mockup)

`run_psc_cases.sh` runs 105073 with the Pulse Supervision Controller (PSC) and the MCLS (Magnetic Control Local
Supervisor) in the controller actor, for the case `ip_story_mockup` (scenario story, `cases/input/psc/ip_story_mockup/`,
README there). It copies `cases/evolutive_controller_105073` to `cases/evolutive_controller_105073_ip_story_mockup`,
expands the override `cases/overrides/evolutive_controller_105073_ip_story_mockup.ymmsl` (`${PDS_REPO}`, `${CASE_DIR}`)
into it, switches `magnetic_controller` to the program `magnetic_controller_psc` with `make_psc_workflow.py`, and runs
`bin/pds-run-case.sbatch` under an init lock (one MATLAB controller init at a time).

Window 115.817598 -> 138.0 s (22.2 s of plasma, ~2.5 h of wall time). The run ends at a fixed time shortly after the
PSC STOP of the reference run (137.88 s) because the controller cannot end the coupled run itself, and the results
after 131.46 s (plasma lost by an upward VDE in the reference run) are not physical: see the case README, section
"End of the run".

Options: `VARIANT=ip_story_mockup` (the only one); `SHORT_WINDOW=1` = smoke check on 115.817598 -> 116.02 s (window
written into the case folder `cases/evolutive_controller_105073_ip_story_mockup_smoke`); `DRY_RUN=1` builds the case
folder and prints the expanded overrides without running; `RUN_TIMEOUT` (s, default 10800, 5100 with `SHORT_WINDOW=1`).
The case needs the model `controllers/CCS/pcssp_controller_and_ps_mcls.slx` (built by
`controllers/CCS/mcls/model_build/build_mcls_controller.sh`) and the PCS framework with the PSC in
`local_installs/pcs-with-pcssp-nightly` (`pds_setup.sh` with `INSTALL_PCSSP_NIGHTLY=true`). From the repository root:

```bash
mkdir -p cases/runs/psc_logs
DRY_RUN=1 VARIANT=ip_story_mockup bash workflows/evolutive_controller/run_psc_cases.sh
sbatch --time=01:30:00 --chdir=$PWD --export=ALL,PDS_REPO=$PWD,VARIANT=ip_story_mockup,SHORT_WINDOW=1 workflows/evolutive_controller/run_psc_cases.sh
sbatch --time=03:30:00 --chdir=$PWD --export=ALL,PDS_REPO=$PWD,VARIANT=ip_story_mockup workflows/evolutive_controller/run_psc_cases.sh
```

More in `preprocessing/psps/README.md` and `cases/input/psc/ip_story_mockup/README.md`.

## Assumptions

- `source` cannot read raw DINA equilibrium here: TORAX's `geometry_type: imas` builder needs
  flux-surface quantities (`r_inboard`/`r_outboard`, `gm1`/`gm2`/`gm3`/`gm7`/`gm9`,
  `dvolume_dpsi`, `j_phi`) that only a real Grad-Shafranov solve computes -- verified DINA's own
  equilibrium record (pre- and post-conversion) never populates them, while
  `inverse_convergence`'s NICE-reconstructed `_out_nice` has all of them. This reintroduces a
  dependency on a completed `inverse_convergence` run for the same shot (`preprocess_data.sh`
  copies its `_out_nice` output), which the very first version of this bootstrap chain had
  tried to avoid.
- `nice_evo_rd` runs with 4 threads (`workflow.ymmsl` `resources:`), TORAX with 8. The NICE
  actor's `OMP_NUM_THREADS` in `lib/easybuild_programs.ymmsl` is overwritten by `resources:
  threads`, so that line is the only place the count can be set. NICE is on the lockstep
  critical path, so its per-step compute comes off the wall time one for one.
- The `magnetic_controller` is not optional decoration: `nice_imas_evo_rd_muscle3`
  unconditionally receives on `pf_active_s` every internal step (see
  `local_installs/nice/src/main_imas_evo_rd_muscle3.cc`), and nothing else in this workflow feeds that
  port, so the controller is what keeps the coupled system running past the first step.
- `torax.fixed_dt` / `nice_evo_rd.t_interval` / `nice_evo_rd.dt` / `config_nice.xml`'s `<dt>`
  are all assumed to be a consistent 0.01s -- a starting point ported from this workflow's
  pre-rename `workflows/evolutive` default, not a value tuned for this scenario or validated
  for solver stability.
- `nice_evo_rd.t_end` (optional, matches `torax.t_final`) bounds `nice_evo_rd`'s own run: once the
  next coupling checkpoint would exceed it, the actor sends its final output with no
  `next_timestamp` and stops, instead of running indefinitely off upstream signaling alone (see
  `local_installs/nice/src/main_imas_evo_rd_muscle3.cc`; same mechanism in `main_imas_evo_muscle3.cc` for the
  non-RD evolutive actor). Left unset, it defaults to `+inf` (old behavior, unchanged). Without it,
  once `torax` finishes at `t_final` and `nice_evo_rd` has no stopping condition of its own, the
  coupled loop livelocks instead of terminating -- this is what `105084/settings.ymmsl` sets it
  for.
- `magnetic_controller`'s MATLAB script points `pyenv()` explicitly at
  `$PDS_REPO/local_installs/IMAS-MUSCLE3/venv/bin/python` rather than resolving Python via `PATH`
  (`which python`): PATH can resolve to an unrelated Python with its own muscle3 install,
  which breaks registration silently if that muscle3 is wire-incompatible with the 0.10.0
  manager every other actor here runs against.

## Input requirements

- The ssh-gated `local_installs/pcs` checkout (`setup_files/setup_pcs.sh`) and the
  `nice_imas_evo_rd_muscle3` binary (not yet part of the NICE easybuild module as of this
  writing -- see the commented-out entries in `ci/run_test_workflows.sh` -- so it must be
  source-built, see `local_installs/nice`).
- A completed `inverse_convergence` run for the same shot *before* `pds-create-case`: its
  `out_nice` seeds the F_INIT equilibrium and coil currents, its `out_torax` the core_profiles
  (frozen into the case by `preprocess.sh`, so rebuild the case after rerunning it).
- DINA-preprocessed scenario data supplying the static machine description, the EC power,
  and `pf_active` coil `voltage.data` (the
  static machine description's per-coil `voltage.data` is empty, so `waveforms.yaml` sources it
  from DINA's raw `pf_active` instead).

## Output

`sink_equilibrium`, `sink_transport`, and `sink_control` are wired to write NICE's evolutive
equilibrium/pf_active, TORAX's evolved profiles, and the controller's corrected pf_active,
respectively (see `settings.ymmsl`), with `recorder_equilibrium`/`recorder_transport` distilling the NICE and TORAX
output for the muscle3-dashboard. In practice the workflow has not yet run to completion --
see Status below for the current known limitation.
