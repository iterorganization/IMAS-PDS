#!/bin/bash
# Validation plots: reference vs NICE output for R, Z, Ip, PF coil current, plus NICE and
# TORAX profiles, each against its own psi grid. Run by
# bin/pds-run-case.sbatch after muscle_manager finishes -- see that script's header for the
# PDS_REPO/SHOT/CASE_DIR/RUN_DIR/PYTHON contract.
#
# reconstruction_path mirrors settings.ymmsl's source.source_uri (the inverse_convergence run
# this case's F_INIT reference equilibrium is read from).
#
# Options for the gyrokinetics plots (plot_gyrokinetics.py), e.g. when re-running this script
# by hand from a run directory:
#   --max_slices N   number of time slices on the time slider (default: 3)
#   --interactive    open a matplotlib window with the slider instead of writing the HTML
set -euo pipefail # stop if anything doesn't work

MAX_SLICES=3
INTERACTIVE=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --max_slices) MAX_SLICES="$2"; shift 2 ;;
    --max_slices=*) MAX_SLICES="${1#*=}"; shift ;;
    --interactive) INTERACTIVE=(--interactive); shift ;;
    *) echo "postprocess.sh: unknown option $1 (use --max_slices N, --interactive)" >&2; exit 1 ;;
  esac
done

# Reconstruct which case matches this run
RUN_DIR=$( cd "$( echo "${BASH_SOURCE[0]%/*}" )"; pwd )
CASE_ROOT=$(basename ${RUN_DIR%_[[:digit:]]*_[[:digit:]]*})
CASE_DIR=$PDS_REPO/cases/$CASE_ROOT
pushd $CASE_DIR
source case.env
popd

# Set runtime variables
PYTHON=${PYTHON:-python}

mkdir -p "$RUN_DIR/plots"

"$PYTHON" "$PDS_REPO/postprocessing/evolutive_controller/plot_validation_evolutive_controller.py" \
  --shot_nr "$SHOT" \
  --reconstruction_path "$RUN_DIR/out_nice" \
  --nice_path "$RUN_DIR/out_nice" \
  --torax_path "$RUN_DIR/out_torax" \
  --dina_path "$CASE_DIR/preprocess/in" \
  --output_dir "$RUN_DIR/plots"

"$PYTHON" "$PDS_REPO/postprocessing/evolutive_controller/plot_gyrokinetics.py" \
  --shot_nr "$SHOT" \
  --nice_uri "$RUN_DIR/out_nice" \
  --torax_uri "$RUN_DIR/out_torax" \
  --output_dir "$RUN_DIR/plots" \
  --max_slices "$MAX_SLICES" \
  "${INTERACTIVE[@]}"
