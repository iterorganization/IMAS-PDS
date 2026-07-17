# prescribed_transport

A minimal MUSCLE3 chain -- `source -> we -> nice_inv -> sink` -- that produces a "prescribed"
(fixed, not self-consistently coupled to transport) NICE free-boundary equilibrium dataset for
one scenario. The waveform editor (`we`) overlays the designed Ip(t)/B0 boundary target
(`waveforms.yaml`) onto the source's raw equilibrium and supplies the static machine
description (wall, pf_passive, iron_core) plus the coil-current seed (pf_active), all imported
from `waveforms.yaml` rather than carried through `source`. NICE-inverse solves the
free-boundary equilibrium per time slice; `sink` stores its resulting equilibrium and coil
currents. Downstream transport workflows (e.g. `torax_nice_controller`) consume this output as
their fixed NICE input -- see how they copy `<shot>_out_nice` in their own `preprocess_data.sh`.

Unlike `inverse_convergence`, there is no outer Picard loop, no TORAX coupling, and no
validator/visualization/recorder components -- just the four-actor chain. Structure lives in
`workflow.ymmsl`; shared knobs in `settings.ymmsl`; per-scenario overrides (if any) in
`scenarios/<shot>/settings.ymmsl`; the pulse design (Ip(t)/B0) lives in `waveforms.yaml`
(overridable per scenario the same way).

## Build

Same repo-local stack as `inverse_convergence` -- see its README for the one-time build
recipe (MUSCLE3 0.10.0 + actor venv, NICE inverse binary, Waveform-Editor venv). No TORAX
build is needed for this workflow.

## Run a scenario (e.g. 105073)

First preprocess the DINA input once (converts the shared DD3.x SDCC database to DD4 and
splits it into `<shot>_in` -- the DINA-derived equilibrium/boundary trace `we` designs onto --
and `<shot>_in_md` -- the machine-description reference `we` re-exports):

```
bash run_workflow.sh prescribed_transport 105073
```

(this runs `preprocess_data.sh` then `run_job.sbatch` then `postprocess_data.sh`), or run
preprocessing alone and launch directly with `bin/pds-prescribed_transport 105073` (or
`sbatch workflows/prescribed_transport/run_job.sbatch 105073`). The launcher stacks
`workflow.ymmsl + settings.ymmsl + scenarios/105073/settings.ymmsl` (if present), expands
`${PDS_REPO}`/`${SCEN}` (MUSCLE3 does not interpolate settings), and starts the manager; runs
land in `scenarios/105073/tmp/runs` and can be browsed with `m3dash open`. Output lands in
`scenarios/<shot>/tmp/data/<shot>_out_nice`. `postprocess_data.sh` reuses
`workflows/torax_nice_utils/plot_validation.py` (no `--torax_uri`, so it only produces the
dina-nice panels: coil currents and equilibrium 0D/1D) into `scenarios/<shot>/tmp/`.
