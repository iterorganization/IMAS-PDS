#!/bin/bash
# The shot's DINA-derived input and machine description into the case (see
# preprocessing/dina/scenario_input.sh), plus the DINA-derived TORAX settings config_torax.py
# reads (see preprocessing/dina/torax_params.py).
set -euo pipefail

"$PDS_REPO/preprocessing/dina/scenario_input.sh" "$CASE_DIR/preprocess/in" "$CASE_DIR/preprocess/in_md"

source "$PDS_REPO/preprocessing/dina/shots/${SHOT%%_*}.env"
python "$PDS_REPO/preprocessing/dina/torax_params.py" "$SOURCE_URI" "$CASE_DIR/preprocess/torax_params.json"
