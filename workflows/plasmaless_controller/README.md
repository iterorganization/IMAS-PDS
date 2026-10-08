# plasmaless_controller

## What it does

`evolutive_controller` with the plant replaced: the PCSSP `magnetic_controller`
(`controllers/KCURR_RZIp/`) is closed on the plasmaless coil+vessel circuit model (no
plasma) instead of NICE direct evolutive (`nice_evo_rd`), and there is no transport (no
TORAX, `temporal_coupler`, transport sink or `recorder_transport`). It tests the
controller and the coil/vessel circuits alone.

`magnetic_controller` and `sink_control` are the same as in `evolutive_controller`.
There is no `waveform_editor` actor: the initial state (F_INIT equilibrium + pf_active of
the controller and of the plant) is built once, at case creation, by this directory's
`preprocess.sh` (Waveform-Editor with `waveforms.yaml`), and `source` sends it directly.
All plasma and coil data come from the inverse run (see below). The `plasmaless` actor (MATLAB, from the plasmaless repository,
`muscle3/muscle_plasmaless_actor.m`; ports, timing and assumptions in that folder's
README) takes nice_evo_rd's place on the controller ports: it receives the F_INIT
equilibrium + pf_active, sends `equilibrium_o_i` + `pf_active_o_i` every `dt` (first at
t0 + dt) and receives the controller's `pf_active` voltages. Its `equilibrium_o_i` is a
reference pass-through (ip and boundary geometric axis of the F_INIT equilibrium,
interpolated in time), so the controller's Ip/R/Z errors are zero and only the coil
current loop acts. It also sends the vessel currents (`pf_passive_o_i`), written with
the other outputs by `sink_equilibrium` to `<run_dir>/out_plasmaless`.

## Data flow (shot 105084 case)

Plasma and coil data come only from the NICE inverse run (`nice_out` of
`cases/runs/metis_nice_inverse_from_dina_<shot>`); only machine descriptions come from
elsewhere. Nothing is read from pds-scenarios `<shot>/data/in` (DINA).

- Case creation (`bin/pds-create-case`, once): `preprocess.sh` runs
  `preprocess_initial_state.py`, which makes the calls the former in-workflow chain
  `source` -> `waveform_editor` made: read the native `nice_out` slices in
  [`source.t_min`, `source.t_max`] (19 slices for 105084, 136.2276 .. 251.0776 s; window
  read from the case's own `workflow_settings.ymmsl` + `scenario_settings.ymmsl`), then
  one Waveform-Editor export with `waveforms.yaml` on the equilibrium times:
  equilibrium time slices passed through; `pf_active` = machine description of
  `<shot>/data/in_md` with the coil currents and voltages of the inverse `pf_active`
  (resampled onto the equilibrium times, closest sample). Output:
  `<case>/preprocess/initial_state` (IMAS HDF5, equilibrium + pf_active) and the frozen
  `<case>/preprocess/waveforms.yaml`.
- Run: `source` (non-iterative) sends that entry, one message per port
  (`equilibrium_out`, `pf_active_out`) with all its slices; its first time is t0.

| Quantity | Consumer | Origin |
|---|---|---|
| equilibrium time slices (ip, boundary incl. outline and geometric axis, profiles) | controller (Ip/R/Z references), plasmaless (pass-through) | `nice_out` equilibrium |
| `vacuum_toroidal_field`, `grids_ggd`, `code` | nobody in this workflow | not passed (only `equilibrium/time_slice/*` is imported, see below) |
| pf_active coil current | controller (coil-current reference, R*I feed-forward), plasmaless (initial currents) | `nice_out` pf_active |
| pf_active coil voltage | plasmaless (first-step voltages at t0) | `nice_out` pf_active; for 105084 these equal the DINA `data/in` voltages of the closest DINA sample exactly (carried through the inverse run, not computed by it) |
| pf_active geometry, turns, resistance, limits; wall, pf_passive, iron_core | controller (resistances) | pds-scenarios `<shot>/data/in_md` |
| model em_coupling, pf_active, pf_passive | plasmaless | plasmaless repository `data/md_dd4` (default `md_uri`) |

- `plasmaless`: coil names must match the F_INIT pf_active names exactly (CS3U ... PF6,
  VS3U, VS3L; `nice_out` and `data/in_md` use the same 14 names in the same order).

## Running it

Prerequisites: pds-scenarios data for the shot, a completed `metis_nice_inverse_from_dina`
run for the shot in `cases/runs/metis_nice_inverse_from_dina_<shot>` (a symlink to another
clone's run directory works), and a checkout of the plasmaless repository. Set
`PLASMALESS_REPO` to your (or a colleague's) clone before running; the default in the
`plasmaless` program (`workflows/lib/easybuild_programs.ymmsl`) is one user's clone,
`/home/ITER/schneim/public/git/plasmaless-tokamak-circuits`. The model machine description
ships with that repository (`data/md_dd4`), so no `plasmaless.md_uri` is needed.

```bash
export PLASMALESS_REPO=<your clone of plasmaless-tokamak-circuits>
bin/pds-create-case plasmaless_controller 105084   # runs preprocess.sh, about 2 min
sbatch bin/pds-run-case.sbatch cases/plasmaless_controller_105084
```

`bin/pds-create-case` runs `preprocess.sh` (single-threaded, about 2-3 GB of RAM) and fails
if `nice_out` is missing. Changing the source window or `waveforms.yaml` needs a new
`bin/pds-create-case`; `plasmaless.t_end` and `dt` only need a new run.

Per-shot settings (source window, `plasmaless.t_end`) are in
`cases/overrides/plasmaless_controller_<shot>.ymmsl`. Two MATLAB sessions run (controller
and plasmaless).

### Live figures (m3dash)

`recorder_plasmaless` (`recorder_component` from imas_muscle3, as `recorder_equilibrium` /
`recorder_transport` in `evolutive_controller`) is an extra receiver on
`plasmaless.pf_active_o_i` and `plasmaless.pf_passive_o_i` (S ports `pf_active_in`,
`pf_passive_in`). It writes one Zarr store per port under
`<run_dir>/instances/recorder_plasmaless/workdir/<port>/0000.zarr`, using the plot file
`recorder_plasmaless.config` (`visualization/plasmaless_currents.py`, copied to the case's
`config/` by `bin/pds-create-case`). Panels, as `plot_plasmaless_imas.m` of the plasmaless
repository: (a) CS/PF coil currents [A], (b) VS3U/VS3L currents [kA], (c) the passive loop
currents [kA]; plus (d) CS/PF and (e) VS coil voltages [V], the voltages the plasmaless
actor applied over the step ending at each time (the controller's command of the
previous exchange; the F_INIT voltage at t0 for the first step). The F_INIT reference
currents are not shown: the recorder names its ports after the IDS, so a second
`pf_active` port in the same tab is not possible.

To watch a run live or afterwards, on a node with a desktop session (NoMachine):

```bash
module use /work/projects/pds/modules/all
module load IMAS-MUSCLE3/1.0.0-intel-2025b-pds
export NUMEXPR_MAX_THREADS=2
m3dash open cases/runs        # or one run directory; opens a browser
```

then pick the run and the `recorder_plasmaless` tab (it appears once the first message
was recorded; "Live View" follows new data). Without a local browser, `m3dash open
--no-open-browser` and forward the printed port over SSH.

## Initial state as case pre-processing (why there is no waveform_editor actor)

Until 2026-10-08 the workflow ran `source` -> `waveform_editor` inside MUSCLE3, with
`equilibrium/*` in `waveforms.yaml`: on every run the `waveform_editor` actor needed
7 to 8.5 minutes between its F_INIT inputs and its outputs, before the first control step.

Root cause (standalone reproducer, no MUSCLE3:
`/home/ITER/schneim/public/git/wfe_slow_init_repro`, see its README.md and reproduce.py):
`equilibrium/*` copies the received NICE equilibrium leaf by leaf, including `grids_ggd`
(up to 12 749 objects per slice, 367 131 leaves for 19 slices), and each copy computes the
leaf path by a linear search (Waveform-Editor `import_resolver.py:191-212`, imas-python
`ids_base.py:55-80`), quadratic overall: 507 s of export.

Now:

- `waveforms.yaml` imports `equilibrium/time_slice/*` only: 67-68 s of export, and every
  field the controller and the plasmaless actor consume is identical (checked against the
  reproducer's export of the original file: equilibrium time, homogeneous_time, 19
  slices, ip and boundary geometric axis, and in fact all 2345 time_slice leaves; all 306
  pf_active leaves). Dropped: `grids_ggd`, `vacuum_toroidal_field`, `code` and the
  `ids_properties/comment` of the equilibrium, read by no component of this workflow.
- The export runs once per case, in `preprocess.sh`: `bin/pds-create-case` took 123 s for
  105084 (42 s reading the `nice_out` window, 68 s Waveform-Editor export).
- In a MUSCLE3 run (source from `preprocess/initial_state`, the real plasmaless actor, a
  Python dummy in place of the PCS controller, t_end = t0 + 0.02, dt 0.005, login node)
  the first exchange completed 47.6 s after the manager started; the source sent its F_INIT
  messages 0.8 s after all peers had connected, the wait being MATLAB start-up of the
  plasmaless actor (registered at 39.5 s). The F_INIT data received by the controller
  equal the `initial_state` entry (all leaves identical except the DD version stamp).

Notes:

- `preprocess.sh` follows the existing per-workflow pre-processing hook of
  `bin/pds-create-case` (as `metis_from_dina` and `metis_nice_inverse_from_dina` do). We
  hope this configuration can be generalised (e.g. driven by the pulse files of the
  pulse-preprocessing work).
- Merge note: on the pulse-preprocessing branch (`feature/pulse-preprocessing`), case
  overrides are generated from `cases/pulses/<shot>.yaml` and hand-written overrides are
  refused by `pds/configure.py`. When merging, add `plasmaless_controller` to
  `cases/pulses/105084.yaml` `workflows:` with its window and step (`source.t_min` 136.0,
  `source.t_max` 256.0, `plasmaless.t_end` 136.6, `plasmaless.dt` =
  `plasmaless.t_interval` = 0.005) and remove the hand-written
  `cases/overrides/plasmaless_controller_105084.ymmsl`.
