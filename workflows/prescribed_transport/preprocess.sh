#!/bin/bash
# The shot's DINA-derived input and machine description into the case, see
# preprocessing/dina/scenario_input.sh.
set -euo pipefail

"$PDS_REPO/preprocessing/dina/scenario_input.sh" "$CASE_DIR/preprocess/in" "$CASE_DIR/preprocess/in_md"
