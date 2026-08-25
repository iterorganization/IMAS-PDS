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

```bash
export PDS_REPO=/path/to/pds
export SCENARIOS_REPO=/path/to/pds-scenarios
export YMMSL_PATH=$PDS_REPO/workflows

muscle_manager --start-all $PDS_REPO/cases/105084_convergence.ymmsl
```

Or via SLURM, which sets all of the above for you:

```bash
sbatch workflows/run_case.sbatch 105084_convergence
```

Cases available: 105073, 105078, 105084, 105092, 105099 (`cases/<shot>_convergence.ymmsl`),
plus `105084_literal_convergence`.

Scenario data and waveform configs live in the separate `pds-scenarios` repository; see its
`GENERATING.md` for how `data/` is produced from DINA and machine-description sources.

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

- `sink_nice` writes the converged per-time-slice `equilibrium` and `pf_active` to
  `<run_dir>/out_nice`; `sink_torax` writes TORAX's evolved `equilibrium` and
  `core_profiles` to `<run_dir>/out_torax`.
- `rec_nice`/`rec_torax` write distilled copies of the NICE and TORAX output for the
  muscle3-dashboard (`visualization/nice_inv.py` / `visualization/kinetic_profiles.py`).
