# inverse_convergence

A MUSCLE3 workflow that drives a NICE free-boundary inverse equilibrium and TORAX transport
to a self-consistent pulse via an outer Picard loop. Each iteration the loop sends a
whole-trace pulse (target equilibrium, core_profiles, coil-current seed); the Waveform-Editor
(`we`) overlays the designed Ip(t)/B0 onto the target equilibrium, mirrors core_profiles
through unchanged, imports the ECRH heating, and re-exports the scenario's static
wall/pf_passive/iron_core machine description straight to the NICE load balancer (these three
never change across the pulse or across iterations, so the loop never carries them); a
parallel NICE-inverse load balancer (`nice_lb.py`) solves it per time slice; its equilibrium
goes to TORAX, whose evolved profiles and NICE's coil currents return to the loop. It
converges when the max coil-current change between iterations drops below `loop.tolerance`.
Structure lives in `workflow.ymmsl`; shared knobs in `settings.ymmsl`; per-scenario data paths
in `scenarios/<shot>/settings.ymmsl`; the pulse design (Ip(t)/B0) lives in `waveforms.yaml`.

## Build (one-time, SDCC)

The PDS repo is a hub — the runnable pieces are built alongside it under `~/pds/opt` and
per-tool venvs, not from env modules. `pds_setup.sh` is the guide (it lists the repos and
upstream install docs): you need **MUSCLE3 0.10.0** + the actor venv `venv-m3091-actors`
(holds `imas_muscle3` and the `waveform-editor` entry point), the **NICE** inverse binary
(`nice_imas_inv_muscle3`, built from `gitlab.inria.fr:blfauger/nice` master — its muscle3/v0.2
actors are already upstream there), and the **TORAX** actor venv (`iterorganization/torax-muscle3`,
`develop`). Preprocessing additionally needs the `IMAS-Python` and `IDStools/2.3.0` modules.
`bin/pds-inverse` resolves all of these through a single `$PDS_REPO` anchor (default: the repo
location), so a different install only needs `export PDS_REPO=<repo>` (and optionally
`PDS_RUNS`, default `<repo>/../runs/pds_inverse`).

## Run a scenario (e.g. 105084)

First preprocess the DINA input once — the shared SDCC database
(`/work/imas/shared/imasdb/ITER/3/<shot>/1`) is DD 3.x, so it must be converted to the DD4
`<shot>_in` the actors read: `bash run_workflow.sh inverse_convergence 105084` runs preprocess
→ run → postprocess, or run the steps individually (`bash workflows/inverse_convergence/preprocess_data.sh`).
Then launch with `bin/pds-inverse 105084` (or `sbatch workflows/inverse_convergence/run_job.sbatch 105084`).
`pds-inverse` stacks `workflow.ymmsl + settings.ymmsl + scenarios/105084/settings.ymmsl`,
expands `${PDS_REPO}`/`${SCEN}` (MUSCLE3 does not interpolate settings), and starts the
manager; runs land in `$PDS_RUNS` and can be browsed with `m3dash open $PDS_RUNS`. A converged
run reports `converged at iteration N` and exits 0.
