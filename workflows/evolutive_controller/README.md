# evolutive_controller

## What it does

A MUSCLE3 workflow that runs TORAX and NICE in genuine evolutive (forward, lockstep)
co-simulation, self-consistently, with a PCSSP magnetic controller closing the coil-current
feedback loop.

Unlike `inverse_convergence` (an outer Picard loop around a static per-slice NICE-inverse
solve) or `prescribed_transport` (NICE-inverse only, no transport solver at all), this
workflow has TORAX and NICE step forward together: each internal step, TORAX evolves
current/temperature and hands `equilibrium` + `core_profiles` to `nice_evo_rd`
(`nice_imas_evo_rd_muscle3`, NICE's resistive-diffusion evolutive free-boundary solver), which
returns the updated `equilibrium` for TORAX's next geometry. TORAX computes its own ohmic
heating and impurity radiation self-consistently from its evolving profiles (see
`config_torax.py`) rather than importing them from DINA; only the ECRH actuator trace is
imported, via `waveform_editor.core_sources_out -> torax.core_sources_in_f` (same mechanism
`inverse_convergence` uses on its own imported `core_sources`).

**F_INIT bootstrap**: `source` reads a NICE-*reconstructed* equilibrium (not raw DINA -- see
Assumptions) from a completed `inverse_convergence` run's `_out_nice`. The Waveform-Editor
(`waveform_editor`) passes that equilibrium through whole (an `equilibrium/*: {ref: eq}`
wildcard import in `waveforms.yaml`, so every field survives, not just hand-picked ones) and
overlays it with the static machine description (`<shot>_in_md`), core_profiles, and the ECRH
trace read directly from this scenario's own DINA-preprocessed data
(`<shot>_in_waveform_editor`), into one assembled F_INIT message for `torax`, `nice_evo_rd`,
and `magnetic_controller`.

A PCSSP `magnetic_controller` (MATLAB/Simulink, see `controllers/KCURR_RZIp/`) reads NICE's `equilibrium`
+ `pf_active` every step and returns a corrected `pf_active`.

Structure lives in `workflow.ymmsl`; shared knobs (including a default `waveforms.yaml`
template) in `settings.ymmsl`; per-shot solver timing (the flattop window genuinely differs
per pulse, so has no sane generic default) in `cases/overrides/evolutive_controller_<shot>.ymmsl`
(105084's restricts the run to flattop only, see below).

## Running it

Requires the scenario's data in `pds-scenarios` (see Input requirements below) and a
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

## Assumptions

- `source` cannot read raw DINA equilibrium here: TORAX's `geometry_type: imas` builder needs
  flux-surface quantities (`r_inboard`/`r_outboard`, `gm1`/`gm2`/`gm3`/`gm7`/`gm9`,
  `dvolume_dpsi`, `j_phi`) that only a real Grad-Shafranov solve computes -- verified DINA's own
  equilibrium record (pre- and post-conversion) never populates them, while
  `inverse_convergence`'s NICE-reconstructed `_out_nice` has all of them. This reintroduces a
  dependency on a completed `inverse_convergence` run for the same shot (`preprocess_data.sh`
  copies its `_out_nice` output), which the very first version of this bootstrap chain had
  tried to avoid.
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
- `config_torax.py` assumes DINA's raw `core_sources` labels exactly one entry as ECRH: for
  105084 it has 15 source entries all with an empty `identifier.name`, and `waveforms.yaml`
  relabels only `source(1)` to `'ec'`, so TORAX's `sources_from_IMAS()` picks up exactly `ecrh`
  and nothing else (see the comment in `config_torax.py`). Re-check this for any other shot
  before trusting its self-consistent ohmic/radiation numbers.
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
- A completed `inverse_convergence` run's `_out_nice` output for the same shot, to seed
  `source`'s F_INIT equilibrium (see Assumptions).
- DINA-preprocessed scenario data supplying the static machine description, `core_profiles`
  (including `conductivity_parallel` and `j_non_inductive`, which the static machine
  description alone doesn't carry), the ECRH trace, and `pf_active` coil `voltage.data` (the
  static machine description's per-coil `voltage.data` is empty, so `waveforms.yaml` sources it
  from DINA's raw `pf_active` instead).

## Output

`sink_equilibrium`, `sink_transport`, and `sink_control` are wired to write NICE's evolutive
equilibrium/pf_active, TORAX's evolved profiles, and the controller's corrected pf_active,
respectively (see `settings.ymmsl`), with `recorder_equilibrium`/`recorder_transport` distilling the NICE and TORAX
output for the muscle3-dashboard. In practice the workflow has not yet run to completion --
see Status below for the current known limitation.
