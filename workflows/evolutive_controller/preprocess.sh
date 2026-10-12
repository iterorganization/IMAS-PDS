#!/bin/bash
# Freezes the completed inverse_convergence run's TORAX core_profiles into the case, minus
# TORAX's repeated axis grid point (see workflows/utils/dedup_core_profiles_grid.py), for
# waveforms.yaml's `torax` import. Rebuild the case after rerunning inverse_convergence.
set -euo pipefail

IC_TORAX="$PDS_REPO/cases/runs/inverse_convergence_${SHOT}/out_torax"
[[ -d "$IC_TORAX" ]] || { echo "preprocess.sh: no $IC_TORAX -- run inverse_convergence $SHOT first" >&2; exit 1; }

mkdir -p "$CASE_DIR/preprocess"
export IMAS_AL_DISABLE_VALIDATE=1
python "$PDS_REPO/workflows/utils/dedup_core_profiles_grid.py" \
  "imas:hdf5?path=$IC_TORAX" "imas:hdf5?path=$CASE_DIR/preprocess/inverse_convergence_${SHOT}_core_profiles"
