# inverse_convergence

## What it does

A MUSCLE3 workflow that drives a NICE free-boundary inverse equilibrium and TORAX transport
to a self-consistent pulse via an outer Picard loop (`loop`, `outer_convergence_loop.py`).
Each iteration the loop sends a whole-trace pulse (target equilibrium, core_profiles,
coil-current seed); the Waveform-Editor (`waveform_editor`) overlays the designed Ip(t)/B0
onto the target equilibrium, mirrors core_profiles through unchanged, imports the ECRH
heating, and re-exports the scenario's static wall/pf_passive/iron_core machine description
straight to the NICE load balancer (these three never change across the pulse or across
iterations, so the loop never carries them); a parallel NICE-inverse load balancer
(`load_balancer`, `nice_load_balancer.py`) solves it per time slice; its equilibrium goes to
TORAX, whose evolved profiles and NICE's coil currents return to the loop. It converges when
the max coil-current change between iterations drops below `loop.tolerance` (and
`loop.rel_tolerance`).

An `imas-validator` actor (`validator`) checks the converged pf_active against the
`iter-olc` ruleset.

Structure lives entirely in `workflow.ymmsl`; everything scenario- and run-specific lives
in the case.

## Running it

Build a case folder for a shot, then hand it to SLURM:

```bash
export SCENARIOS_REPO=/path/to/pds-scenarios   # defaults to /work/projects/pds/pds-scenarios

bin/pds-create-case inverse_convergence 105084       # -> cases/inverse_convergence_105084
sbatch bin/pds-run-case.sbatch cases/inverse_convergence_105084
```

`pds-create-case` stacks `workflow.ymmsl`, this workflow's `settings.ymmsl` (resources,
loop/solver defaults, this workflow's own `waveforms.yaml` pulse-design template, and the
input DBEntry, all templated from `${SHOT}`), and
`cases/overrides/inverse_convergence_<shot>.ymmsl` if it exists (a `waveforms.yaml` variant
for MD_LAYOUT=combined shots, a calibrated `config_torax.py`, a narrower loop window --
whatever a shot needs beyond the generic template) into numbered files under the case
folder; `pds-run-case.sbatch` runs that folder under `muscle_manager`, writing to
`cases/runs/<case>`.

Scenarios available: 105073, 105078, 105084, 105092, 105099, plus `105084_literal` (same
source data as 105084, a literal rather than loop-designed pulse).

Only the input DBEntry (`data/in`, `data/in_md`) is read live from `pds-scenarios`; the
pulse design (`waveforms.yaml`) lives in this workflow's own directory, and any per-shot
variant or calibrated solver config lives under `cases/overrides/`, so both are versioned
and editable here. See `pds-scenarios`' `GENERATING.md` for how `data/` itself is produced
from DINA and machine-description sources.

## Assumptions

- The pulse design (Ip(t)/B0 boundary target) and the static machine description
  (wall/pf_passive/iron_core) are fixed for the whole run and are not part of the Picard
  iteration -- only the target equilibrium, core_profiles, and coil-current seed are carried
  around the loop.
- Convergence is judged purely on coil currents (`loop.tolerance`/`loop.rel_tolerance`), not on
  a residual of the equilibrium or profiles themselves.
- `loop.max_iterations` bounds the run regardless of whether `loop.tolerance` was reached --
  a run that hits the iteration cap without converging still produces output, so check the
  loop's own convergence log rather than assuming the presence of output means convergence.

## Input requirements

Produced by `tools/prepare <shot>` in the `pds-scenarios` repository.

- A DINA-derived source supplying the equilibrium boundary/target trace, plus `core_profiles`
  (electron/ion temperature and density) for TORAX and the ECRH heating trace picked up via
  `core_sources`.
- Machine descriptions for `pf_active`, `pf_passive`, `wall`, and `iron_core`.
- The `pf_active` machine description must have exactly one element per coil in the `elements`
  array of structures, and each coil must carry a resistance value -- both required by NICE
  inverse.

## Output

The sinks write into the run directory itself:

- `sink_equilibrium` writes the converged per-time-slice `equilibrium` and `pf_active` to
  `<run_dir>/out_nice`; `sink_transport` writes TORAX's evolved `equilibrium` and
  `core_profiles` to `<run_dir>/out_torax`.
- `recorder_equilibrium`/`recorder_transport` write distilled copies of the NICE and TORAX output for the
  muscle3-dashboard (`visualization/nice_inv.py` / `visualization/kinetic_profiles.py`).
