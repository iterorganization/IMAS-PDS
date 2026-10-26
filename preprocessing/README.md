# preprocessing

Turns a shot's sources into workflow input. Each workflow's `preprocess.sh` calls these once,
at `pds-create-case`, and writes the result into `$CASE_DIR/preprocess/`.

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
