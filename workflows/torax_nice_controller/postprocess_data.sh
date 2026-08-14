set -euo pipefail # stop if anything doesn't work

module load IMAS-Python
module load IDStools/2.3.0

PLOTDIR="$SUBDIR/tmp/data" 

# load T_LIST from string
IFS=' ' read -r -a T_LIST <<< "$T_LIST"

python $PWD/workflows/torax_nice_utils/plot_validation.py \
  --shot_nr $SHOT_NR \
  --dina_uri "$PLOTDIR/${SHOT_NR}_in" \
  --nice_uri "$PLOTDIR/${SHOT_NR}_out_nice" \
  --torax_uri "$PLOTDIR/${SHOT_NR}_out_torax" \
  --output_dir "$SUBDIR/tmp" \
  --t_list "${T_LIST[@]}"
