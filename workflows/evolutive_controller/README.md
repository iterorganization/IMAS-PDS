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

Structure lives in `workflow.ymmsl`; shared knobs in `settings.ymmsl`; per-scenario DINA source
paths in `scenarios/<shot>/scenario_config.env`; `scenarios/<shot>/settings.ymmsl` overrides
shared knobs when needed (105084's restricts the run to flattop only, see below).

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
  `run/nice/src/main_imas_evo_rd_muscle3.cc`), and nothing else in this workflow feeds that
  port, so the controller is what keeps the coupled system running past the first step.
- `torax.fixed_dt` / `nice_evo_rd.t_interval` / `nice_evo_rd.dt` / `config_nice.xml`'s `<dt>`
  are all assumed to be a consistent 0.01s -- a starting point ported from `workflows/evolutive`'s
  default, not a value tuned for this scenario or validated for solver stability.
- `nice_evo_rd.t_end` (optional, matches `torax.t_final`) bounds `nice_evo_rd`'s own run: once the
  next coupling checkpoint would exceed it, the actor sends its final output with no
  `next_timestamp` and stops, instead of running indefinitely off upstream signaling alone (see
  `run/nice/src/main_imas_evo_rd_muscle3.cc`; same mechanism in `main_imas_evo_muscle3.cc` for the
  non-RD evolutive actor). Left unset, it defaults to `+inf` (old behavior, unchanged). Without it,
  once `torax` finishes at `t_final` and `nice_evo_rd` has no stopping condition of its own, the
  coupled loop livelocks instead of terminating -- this is what `105084/settings.ymmsl` sets it
  for.
- `config_torax.py` assumes DINA's raw `core_sources` labels exactly one entry as ECRH: for
  105084 it has 15 source entries all with an empty `identifier.name`, and `waveforms.yaml`
  relabels only `source(1)` to `'ec'`, so TORAX's `sources_from_IMAS()` picks up exactly `ecrh`
  and nothing else (see the comment in `config_torax.py`). Re-check this for any other shot
  before trusting its self-consistent ohmic/radiation numbers.

## Input requirements

- The ssh-gated `run/pcs` checkout (`setup_files/setup_pcs.sh`) and the
  `nice_imas_evo_rd_muscle3` binary (not yet part of the NICE easybuild module as of this
  writing -- see the commented-out entries in `ci/run_test_workflows.sh` -- so it must be
  source-built, see `run/nice`).
- A completed `inverse_convergence` run's `_out_nice` output for the same shot, to seed
  `source`'s F_INIT equilibrium (see Assumptions).
- DINA-preprocessed scenario data supplying the static machine description, `core_profiles`
  (including `conductivity_parallel` and `j_non_inductive`, which the static machine
  description alone doesn't carry), the ECRH trace, and `pf_active` coil `voltage.data` (the
  static machine description's per-coil `voltage.data` is empty, so `waveforms.yaml` sources it
  from DINA's raw `pf_active` instead).

## Output

`sink_nice`, `sink_torax`, and `sink_controller` are wired to write NICE's evolutive
equilibrium/pf_active, TORAX's evolved profiles, and the controller's corrected pf_active,
respectively (see `settings.ymmsl`), with `rec_nice`/`rec_torax` distilling the NICE and TORAX
output for the muscle3-dashboard. In practice the workflow has not yet run to completion --
see Status below for how far it currently gets.

### Status

Environment verified locally: `nice_imas_evo_rd_muscle3` is built and runs cleanly (correct
libs once the `NICE/3.0.0-intel-2023b-DD-4.1.0` module is loaded), and `run/pcs`+`pcssp`
(including its `scdds` submodule) are checked out and up to date.

Run repeatedly end-to-end against 105084 (flattop-restricted, `t_min=25 t_max=250`), fixing
real bugs found each time (each confirmed via gdb backtraces on the actual segfaults, not
guessed):

1. **`magnetic_controller`'s `pyenv` picked up the wrong muscle3.** Its MATLAB script used
   `unix('which python')` to find a Python for `pyenv()`; on this system that resolves to a
   stray user `~/.local` install of **muscle3 0.8.0**, wire-incompatible with the 0.10.0
   manager every other actor here runs against (a `pip show muscle3` confirms the mismatch).
   Symptom: registration failed after ~2 minutes of MATLAB startup with `SocketClosed: Socket
   closed while receiving` in `instance._register`. Fixed by pointing `pyenv()` explicitly at
   `$PDS_REPO/run/IMAS-MUSCLE3/venv/bin/python` instead of relying on `PATH`.
2. **`source` couldn't supply everything from one directory.** The original design read all of
   `source`'s F_INIT ports from a single directory that didn't have all the needed IDSs.
   Fixed by adding a `waveform_editor` (Waveform-Editor) actor that assembles the F_INIT
   message: static machine description, core_profiles and ECRH come from this scenario's own
   DINA data; equilibrium comes from `source`, which -- per item 3 below -- has to be
   NICE-reconstructed data, not raw DINA.
3. **TORAX's F_INIT geometry needs a real reconstructed equilibrium.** Feeding it raw DINA (via
   `waveform_editor`) crashed TORAX's geometry builder with `IndexError: index -1 is out of
   bounds ... size 0` (`R_major_profile` from empty `r_inboard`/`r_outboard`). Verified DINA
   never populates the flux-surface quantities (`r_inboard`/`r_outboard`/`gm1`/`gm2`/`gm3`/
   `gm7`/`gm9`/`dvolume_dpsi`/`j_phi`) TORAX's `geometry_from_single_IMAS_slice` requires --
   only a real Grad-Shafranov solve (NICE) computes them, confirmed by inspecting
   `inverse_convergence`'s `_out_nice` (has all of them) against DINA's raw equilibrium (has
   none). Fixed by pointing `source` at a completed `inverse_convergence` run's `_out_nice` and
   adding the wildcard passthrough in `waveform_editor`'s `waveforms.yaml` (item 2) so the full
   equilibrium survives `waveform_editor`.
4. **`nice_evo_rd` segfaulted in `ReadDataEvolutiveProblemWithRD`** (confirmed via gdb:
   `core_profiles.profiles_1d(0).conductivity_parallel(i)` at `nice_imas.cc:9277`, no bounds/size
   check) because `waveform_editor`'s core_profiles bootstrap never set `conductivity_parallel` (or
   `j_non_inductive`). Fixed by adding both to `waveforms.yaml`'s `state:` section, sourced from
   DINA's raw core_profiles (which has them).
5. **`nice_evo_rd` segfaulted again in the same function**, this time on
   `pf_active.coil(i).voltage.data(0)`: the `supply`-based branch is guarded with a
   `.size() > 0` check but the `coil` fallback branch isn't, and the static machine description
   (`_in_md`) has empty `voltage.data` per coil (only DINA's raw `_in` has real values). Fixed
   by adding `pf_active/coil(*)/voltage/data: {ref: input}` to `waveforms.yaml`.

**Still crashing** as of the last run: a *third* segfault, now inside NICE's own solver
internals rather than IDS field access -- gdb backtrace shows `SIGSEGV` in a `memmove` inside
`Solver::_ComputeCurrents()`, called from `_OutputDataFullEquiEvolutionSpecific` ->
`_OutputDataFullEqui` -> `OutputDataEqui`, itself called from `niceEvoP1withRD` (i.e. this
happens on NICE's first real evolutive step, past the F_INIT bootstrap). Coil/circuit counts in
the machine description look consistent with `config_nice.xml`'s `n_coil_group_index`/
`n_group_current_index`/etc. (14 coils, 14 supplies) at a glance, but the actual mismatched
buffer size feeding that `memmove` hasn't been identified -- this requires reading
`Solver::_ComputeCurrents()`'s implementation in `run/nice/src/nice_imas.cc` (or an equivalent
solver source file) rather than another IDS-field guess. `workflow.ymmsl`'s `nice_evo_rd`
program can be temporarily wrapped with
`gdb -batch -ex run -ex "bt full" --args <binary> "$@"` (as used for the fixes above) to
continue this from where it left off.

### Still open (once the crash above is resolved)

- No `validator` (olc) actor is wired in, unlike `inverse_convergence` -- straightforward to
  add later if useful for a time-evolving (not single-final-slice) coil-current check.
- The overall run has not yet reached a real TORAX<->NICE<->controller exchange cycle (the
  crash above happens on NICE's very first evolutive step, before it ever sends back to
  TORAX) -- so none of the coupling's actual runtime behavior (timestep stability, controller
  response, dt matching) has been observed yet.
