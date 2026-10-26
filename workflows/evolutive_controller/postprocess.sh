#!/bin/bash
# Validation plots: reference vs NICE output for R, Z, Ip, PF coil current, plus NICE and
# TORAX profiles, each against its own psi grid. Run by
# bin/pds-run-case.sbatch after muscle_manager finishes -- see that script's header for the
# PDS_REPO/SHOT/CASE_DIR/RUN_DIR/PYTHON contract.
#
# reconstruction_path mirrors settings.ymmsl's source.source_uri (the inverse_convergence run
# this case's F_INIT reference equilibrium is read from).
set -euo pipefail

mkdir -p "$RUN_DIR/plots"

"$PYTHON" "$PDS_REPO/workflows/utils/plot_validation_evolutive_controller.py" \
  --shot_nr "$SHOT" \
  --dina_path "$CASE_DIR/preprocess/in" \
  --reconstruction_path "$PDS_REPO/cases/runs/inverse_convergence_${SHOT}/out_nice" \
  --nice_path "$RUN_DIR/out_nice" \
  --torax_path "$RUN_DIR/out_torax" \
  --output_dir "$RUN_DIR/plots"
