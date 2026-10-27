#!/bin/bash
# Validation plots: reference vs NICE output for R, Z, Ip, PF coil current, plus NICE and
# TORAX profiles, each against its own psi grid. Run by
# bin/pds-run-case.sbatch after muscle_manager finishes -- see that script's header for the
# PDS_REPO/SHOT/CASE_DIR/RUN_DIR/PYTHON contract.
#
# reconstruction_path mirrors settings.ymmsl's source.source_uri (the inverse_convergence run
# this case's F_INIT reference equilibrium is read from).
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

mkdir -p "$RUN_DIR/plots"

"$PYTHON" "$PDS_REPO/postprocessing/evolutive_controller/plot_validation_evolutive_controller.py"
  --shot_nr "$SHOT" \
  #--dina_path "$CASE_DIR/preprocess/in" \
  --reconstruction_path "$RUN_DIR/out_nice" \
  --nice_path "$RUN_DIR/out_nice" \
  --torax_path "$RUN_DIR/out_torax" \
  --output_dir "$RUN_DIR/plots"
