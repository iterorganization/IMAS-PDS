# prescribed_transport

## What it does

A minimal MUSCLE3 chain -- `source -> waveform_editor -> solve -> sink` (+ `rec_nice`) --
that produces a "prescribed" (fixed, not self-consistently coupled to transport) NICE
free-boundary equilibrium dataset for one scenario. The waveform editor overlays the designed
Ip(t)/B0 boundary target onto the source's raw equilibrium and supplies the static machine
description (wall, pf_passive, iron_core) plus the coil-current seed (pf_active), all imported
from the scenario's waveform config rather than carried through `source`. NICE-inverse solves
the free-boundary equilibrium per time slice; `sink` stores the resulting equilibrium and coil
currents; `rec_nice` distills the same data (config: `visualization/nice_inv.py`) for the
muscle3-dashboard.

`solve` is the `lib/nice_inverse` submodel: a load balancer in front of N NICE workers. It
slices the trace, scatters per-slice calls over the workers, re-gauges psi, and gathers the
results back in the original order.

## Running it

```bash
export PDS_REPO=/path/to/pds
export SCENARIOS_REPO=/path/to/pds-scenarios
export YMMSL_PATH=$PDS_REPO/workflows

muscle_manager --start-all $PDS_REPO/cases/105084_prescribed.ymmsl
```

Or via SLURM, which sets all of the above for you:

```bash
sbatch workflows/prescribed_transport/run_job.sbatch 105084
```

Cases available: 105078, 105084, 105092, 105099 (`cases/<shot>_prescribed.ymmsl`).

Scenario data and waveform configs live in the separate `pds-scenarios` repository; see its
`GENERATING.md` for how `data/` is produced from DINA and machine-description sources.

## Assumptions

- Transport is **not** solved and is **not** self-consistent with the equilibrium: the plasma
  shape, Ip(t)/B0, and profile shape (`p'`, `FF'`) are fixed externally in the scenario's
  waveform config rather than produced by a transport code.
- Each time slice is an independent NICE-inverse solve -- there is no time coupling between
  slices, and no outer iteration (contrast with `inverse_convergence`, which wraps a similar
  NICE-inverse solve in a Picard loop against TORAX).
- The static machine description (wall, pf_passive, iron_core) and the coil-current seed
  (pf_active) never change across the pulse; they come from the scenario's machine-description
  entry, not from `source`.
- `lib/nice_inverse` declares `multiplicity: [1]`, and multiplicity cannot be overridden from
  a case, so there is currently one worker. The load balancer's round-robin and reassembly
  paths have only been exercised at one worker.

## Input requirements

Produced by `tools/prepare <shot>` in the `pds-scenarios` repository.

- A DINA-derived source supplying the equilibrium boundary/target trace:
  `vacuum_toroidal_field/r0` and `/b0`, `global_quantities/ip` and `/psi_boundary`, and
  `boundary/outline/r`/`/z`, plus `psi`, `f_df_dpsi`, and `dpressure_dpsi` on `profiles_1d`
  to seed NICE's first solve.
- Machine descriptions for `pf_active`, `pf_passive`, `wall`, and `iron_core`.
- The `pf_active` machine description must have exactly one element per coil in the `elements`
  array of structures, and each coil must carry a resistance value -- both required by NICE
  inverse.

## Output

Relative sink URIs resolve against each instance's own work directory, so results land under
`<run_dir>/instances/<sink>/workdir/`:

- `sink` writes an IMAS HDF5 dataset at `instances/sink/workdir/out_nice`, containing the
  per-time-slice free-boundary `equilibrium` and the solved `pf_active` coil currents.
- `rec_nice` writes a distilled copy of the same data for the muscle3-dashboard (see
  `visualization/nice_inv.py`).
