#!/bin/bash
# The shot's DINA-derived input, machine description and TORAX settings into the case (see
# workflows/inverse_convergence/preprocess.sh), plus the completed inverse_convergence
# run's TORAX core_profiles minus TORAX's repeated axis grid point (see
# preprocessing/inverse_convergence/dedup_core_profiles_grid.py), for waveforms.yaml's
# `torax` import. Rebuild the case after rerunning inverse_convergence.
set -euo pipefail

IC_TORAX="$PDS_REPO/cases/runs/inverse_convergence_${SHOT}/out_torax"
[[ -d "$IC_TORAX" ]] || { echo "preprocess.sh: no $IC_TORAX -- run inverse_convergence $SHOT first" >&2; exit 1; }

"$PDS_REPO/preprocessing/dina/scenario_input.sh" "$CASE_DIR/preprocess/in" "$CASE_DIR/preprocess/in_md"
source "$PDS_REPO/preprocessing/dina/shots/${SHOT%%_*}.env"
python "$PDS_REPO/preprocessing/dina/torax_params.py" "$SOURCE_URI" "$CASE_DIR/preprocess/torax_params.json"

export IMAS_AL_DISABLE_VALIDATE=1
python "$PDS_REPO/preprocessing/inverse_convergence/dedup_core_profiles_grid.py" \
  "imas:hdf5?path=$IC_TORAX" "imas:hdf5?path=$CASE_DIR/preprocess/inverse_convergence_${SHOT}_core_profiles"
