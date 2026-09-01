# prescribed_transport

## What it does

`equilibrium` is the `nice_inverse` submodel (defined in `workflow.ymmsl`). it concists of:
a load balancer in front of N NICE workers and `recorder_equilibrium`, which records the gathered
output from the load balancer.
The load balancer slices the trace, scatters per-slice calls over the workers, re-gauges
psi, and gathers the results back in the original order.

## Running it

Build a case folder for a shot, then hand it to SLURM:

```bash
export SCENARIOS_REPO=/path/to/pds-scenarios   # defaults to /work/projects/pds/pds-scenarios

bin/pds-create-case prescribed_transport 105084       # -> cases/prescribed_transport_105084
sbatch --time=00:20:00 --cpus-per-task=8 bin/pds-run-case.sbatch cases/prescribed_transport_105084
```

`pds-create-case` stacks: `workflow.ymmsl`, this workflow's `settings.ymmsl`, and
`cases/overrides/prescribed_transport_<shot>.ymmsl`.

The `settings.ymmsl` contains (all templated from `${SHOT}`):

- Resources
- Solver config
- This workflow's own `waveforms_no_transport.yaml` pulse-design template
- The input DBEntry

If an override file was used it is ran by `pds-run-case.sbatch` under `muscle_manager`, writing to `cases/runs/<case>`.

Scenarios available: 105078, 105084, 105092, 105099.

Only the input DBEntry (`data/in`, `data/in_md`) is read live from `pds-scenarios`; the
pulse design (`waveforms_no_transport.yaml`) lives in this workflow's own directory, so it's
versioned and editable here. See `pds-scenarios`' `GENERATING.md` for how `data/` itself is
produced from DINA and machine-description sources.

## Assumptions

- Transport is **not** solved and is **not** self-consistent with the equilibrium. The plasma
  shape, Ip(t)/B0, and profile shape (`p'`, `FF'`) are all fixed externally in the scenario's
  waveform config rather than produced by a transport code.
- Each time slice is an independent NICE-inverse solve -- there is no time coupling between
  slices, and no outer iteration (contrast with `inverse_convergence`, which wraps a similar
  NICE-inverse solve in a Picard loop against TORAX).
- The static machine description (wall, pf_passive, iron_core) and the coil-current seed
  (pf_active) never change across the pulse; they come from the scenario's machine-description
  entry, not from `source`.
- `equilibrium` (the `nice_inverse` submodel) declares `multiplicity: [1]`, and
  multiplicity cannot be overridden from a case, so there is currently one worker. The
  load balancer's round-robin and reassembly paths have only been exercised at one worker.

## Input requirements

Produced by `tools/prepare <shot>` in the `pds-scenarios` repository.

- A DINA-derived source supplying the equilibrium boundary/target trace to seed NICE's first solve:
  `vacuum_toroidal_field/r0`
  `/b0`
  `global_quantities/ip`
  `/psi_boundary`
  `boundary/outline/r`/`/z`
  `psi`
  `f_df_dpsi`
  `dpressure_dpsi`
  `profiles_1d`
- Machine descriptions for `pf_active`, `pf_passive`, `wall`, and `iron_core`.
- The `pf_active` machine description must have exactly one element per coil in the `elements`
  array of structures, and each coil must carry a resistance value -- both required by NICE
  inverse.

## Output

The sink writes into the run directory itself:

- `sink` writes an IMAS HDF5 dataset at `<run_dir>/out_nice`, containing the
  per-time-slice free-boundary `equilibrium` and the solved `pf_active` coil currents.
- `recorder_equilibrium` writes a distilled copy of the same data for the muscle3-dashboard (see
  `visualization/nice_inv.py`).
