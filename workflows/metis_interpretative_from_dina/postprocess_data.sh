set -euo pipefail # stop if anything doesn't work

# IMAS-Python/IDStools already provided by `module load PDS`. Loading the
# stale IDStools/2.3.0 (intel-2023b) here used to silently downgrade the
# whole 2025b toolchain back to 2023b -- see setup_files/PDS.lua.

PLOTDIR="$SUBDIR/tmp/data"

# load T_LIST from string
IFS=' ' read -r -a T_LIST <<< "$T_LIST"

python $PWD/workflows/metis_alone_utils/plot_validation_metis.py \
  --shot_nr $SHOT_NR \
  --dina_uri "$PLOTDIR/${SHOT_NR}_dina_update_in" \
  --metis_uri "$PLOTDIR/${SHOT_NR}_metis_out" \
  --output_dir "$SUBDIR/tmp" \
  --t_list "${T_LIST[@]}"
