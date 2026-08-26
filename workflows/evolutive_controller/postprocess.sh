#!/bin/bash
# Validation plots against DINA. Restored from the pre-modularisation
# postprocess_data.sh (removed in cb5fdf6 "working ci locally, cleanup"). Run by
# bin/pds-run-case.sbatch after muscle_manager finishes.
#
# t_list is genuinely per-shot (each shot's own ramp-up/flattop/ramp-down times), carried
# over as-is from that script's scenario_config.env values -- only 105073/105084 ever had one.
set -euo pipefail

case "$SHOT" in
  105073) T_LIST="80 105 130" ;;
  105084) T_LIST="136 196 256" ;;
  *) echo "postprocess.sh: no known t_list for shot $SHOT" >&2; exit 1 ;;
esac

mkdir -p "$RUN_DIR/plots"

"$PYTHON" "$PDS_REPO/workflows/torax_nice_utils/plot_validation.py" \
  --shot_nr "$SHOT" \
  --dina_uri "$SCENARIOS_REPO/$SHOT/data/in" \
  --nice_uri "$RUN_DIR/out_nice" \
  --torax_uri "$RUN_DIR/out_torax" \
  --output_dir "$RUN_DIR/plots" \
  --t_list $T_LIST
