#!/bin/bash
# Validation plots against DINA. Restored from the pre-modularisation
# postprocess_data.sh (removed in a692fc1 "Add ci/compare_ids.py and remove the
# inverse_convergence legacy layer"). Run by bin/pds-run-case.sbatch after muscle_manager
# finishes.
#
# t_list is genuinely per-shot (each shot's own ramp-up/flattop/ramp-down times), carried
# over as-is from that script's scenario_config.env values.
set -euo pipefail # stop if anything doesn't work

# Reconstruct which case matches this run
RUN_DIR=$( cd "$( echo "${BASH_SOURCE[0]%/*}" )"; pwd )
CASE_ROOT=$(basename ${RUN_DIR%_[[:digit:]]*_[[:digit:]]*})
CASE_DIR=$PDS_REPO/cases/$CASE_ROOT
pushd $CASE_DIR
source case.env
popd

# Set runtime variables
PYTHON=python # Best guess of Python interpreter. TODO: Can we use something else?

case "$SHOT" in
  105073) T_LIST="25 130 175" ;;
  105078) T_LIST="20 150 270" ;;
  105084) T_LIST="10 150 270" ;;
  105092) T_LIST="30 110 130" ;;
  105099) T_LIST="20 35 60" ;;
  *) echo "postprocess.sh: no known t_list for shot $SHOT" >&2; exit 1 ;;
esac

mkdir -p "$RUN_DIR/plots"

"$PYTHON" "$PDS_REPO/postprocessing/torax_nice/plot_validation.py" \
  --shot_nr "$SHOT" \
  --dina_uri "$CASE_DIR/preprocess/in" \
  --nice_uri "$RUN_DIR/out_nice" \
  --torax_uri "$RUN_DIR/out_torax" \
  --output_dir "$RUN_DIR/plots" \
  --t_list $T_LIST
