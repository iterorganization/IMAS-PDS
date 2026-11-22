# preprocessing

Preprocessing is not the task of PDS: workflows expect ready-to-use IMAS (DD4) input. The
tools here are provided for some specific cases only, to turn a shot's sources into workflow
input. Each workflow's `preprocess.sh` calls these once, at `pds-create-case`, and writes the
result into `$CASE_DIR/preprocess/`.

Sorted by data source:

- `dina/`: a DINA run, sliced and converted to DD 4.0.0. `shots/<shot>.env` names each shot's
  run; adding a shot means adding a file there.
  `scenario_input.sh <out-dir> [md-out-dir] [n_timeslices]` is the entry point most
  workflows use.
- `machine_description/`: the ITER machine-description collections (wall, iron_core,
  pf_passive, pf_active geometry), named in `iter.env`. Written alongside the DINA input by
  `scenario_input.sh`.
- `inverse_convergence/`: a completed inverse_convergence run's output, for
  evolutive_controller.
- `metis/`: METIS's own input dataset (MATLAB, slow), for the METIS workflows.

## Keyframe shape interpolation (`inverse_convergence/interpolate_keyframe_shapes.py`)

Turns a few designed shapes (an IMAS entry with one equilibrium slice per keyframe, e.g. the
NICE inverse equilibria of the Waveform-Editor shape editor) into one equilibrium slice per
export time of an inverse_convergence case, so the case's waveforms YAML can take the
outline with `closest` and still get the interpolated shape at every export time. Written
per slice: `boundary.outline.r/z`, `global_quantities.ip`, `global_quantities.psi_boundary`
(also `boundary.psi`), `boundary.type`, `vacuum_toroidal_field.b0` (and `r0` if the
keyframes have it); no pf_active.

Method (details in the script docstring):

- Ip, boundary psi, B0: linear in time between keyframes (as `interp: linear`).
- Outline: polar coordinates about a fixed centre (default R 6.2 m, Z 0.5 m). Every keyframe
  must be star-shaped about it (checked). r(theta) is sampled on 512 equally spaced rays
  plus one ray through each diverted keyframe's X-point (its lowest outline vertex), by
  exact ray-polygon intersection, and is linear in time between two keyframes of the same
  topology: linear interpolation of gap-like distances along fixed rays.
- Topology change between two keyframes: no blending, a step at the given switch time
  (105073: DINA X-point formation, 10.918 s).
- Before the first / after the last keyframe: the end keyframe is held.
- No smoothing, clamps or other constructs.

Export times: iteration 0 exports on the input slice times within `loop.t_min`/`loop.t_max`;
from iteration 1 on, the loop sends the TORAX slices closest to those times, on TORAX's
`fixed_dt` grid (`workflows/lib/actors/outer_convergence_loop.py:181-188, 241-253`). Pass both
time sets with repeated `--times-from` (the case's input entry and the `out_nice` of an
earlier run with the same window and TORAX settings).

Example (case `inverse_convergence_105073_shapes6`, module
`IMAS-MUSCLE3/1.0.0-intel-2025b-pds`):

    python preprocessing/inverse_convergence/interpolate_keyframe_shapes.py \
        "imas:hdf5?path=/home/ITER/schneim/public/shape_editor_105073/imas_6slices" \
        "imas:hdf5?path=$PWD/cases/inverse_convergence_105073_shapes6/shapes_interp_imas" \
        --times-from "imas:hdf5?path=$PWD/cases/inverse_convergence_105073/preprocess/in" \
        --times-from "imas:hdf5?path=$PWD/cases/runs/<earlier run>/out_nice" \
        --t-min 10 --t-max 143 \
        --topology limiter,limiter,limiter,diverted,diverted,diverted \
        --switch-times 10.918

Tests: `python -m pytest preprocessing/inverse_convergence/tests` (no IMAS data needed).
