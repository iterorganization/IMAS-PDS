#!/bin/bash
# Validation plots against DINA. Ported from the old
# metis_interpretative_nice_inverse_from_dina/postprocess_data.sh -- run by
# bin/pds-run-case.sbatch after muscle_manager finishes. See that script's header for the
# PDS_REPO/SHOT/CASE_DIR/RUN_DIR contract.
#
# t_list is the same "20 35 60" every one of this workflow's old scenarios used -- not a
# real per-shot calibration, just where the old default happened to land.
# Reconstruct which case matches this run
RUN_DIR=$( cd "$( echo "${BASH_SOURCE[0]%/*}" )"; pwd )
CASE_ROOT=$(basename ${RUN_DIR%_[[:digit:]]*_[[:digit:]]*})
CASE_DIR=$PDS_REPO/cases/$CASE_ROOT
pushd $CASE_DIR
source case.env
popd

# Set runtime variables
PYTHON=python # Best guess of Python interpreter. TODO: Can we use something else?

T_LIST="20 35 60"

mkdir -p "$RUN_DIR/plots"

"$PYTHON" "$PDS_REPO/postprocessing/metis_alone/plot_validation_metis.py"
  --shot_nr "$SHOT" \
  --dina_uri "$CASE_DIR/preprocess/dina_update_in" \
  --nice_uri "$RUN_DIR/nice_out" \
  --metis_uri "$RUN_DIR/metis_out" \
  --output_dir "$RUN_DIR/plots" \
  --t_list $T_LIST
