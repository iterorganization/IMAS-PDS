#!/bin/bash
# Validation plots against DINA. Ported from itergit/feature/metis_nice_evol's
# workflows/metis_predictive_nice_evol_from_dina/postprocess_data.sh -- run by
# bin/pds-run-case.sbatch after muscle_manager finishes. See that script's header for the
# PDS_REPO/SHOT/CASE_DIR/RUN_DIR contract.
#
# t_list is the same "20 35 60" every metis_nice_utils validation plot uses -- not a real
# per-shot calibration, just where the old default happened to land.
set -euo pipefail

T_LIST="20 35 60"

mkdir -p "$RUN_DIR/plots"

"$PYTHON" "$PDS_REPO/workflows/metis_nice_utils/plot_validation_metis_nice.py" \
  --shot_nr "$SHOT" \
  --dina_uri "$CASE_DIR/preprocess/dina_update_in" \
  --nice_uri "$RUN_DIR/nice_out" \
  --metis_uri "$RUN_DIR/metis_out" \
  --output_dir "$RUN_DIR/plots" \
  --t_list $T_LIST
