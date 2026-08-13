set -euo pipefail # stop if anything doesn't work

# The workflow data is DD 4.1.1; the unversioned IMAS-Python module resolves to 2.0.1,
# whose newest known DD is 4.0.0, so it cannot read the data. Use the repo-local
# IMAS-MUSCLE3 venv (imas 2.3.0 + matplotlib) like the rest of the pds stack, with a
# pinned new-enough module as fallback for installs without that venv.
PYTHON="${PDS_REPO:-$PWD}/run/IMAS-MUSCLE3/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  module load IMAS-Python/2.3.0-intel-2023b
  PYTHON=python
fi

PLOTDIR="$SUBDIR/tmp/data"

# load T_LIST from string
IFS=' ' read -r -a T_LIST <<< "$T_LIST"

"$PYTHON" $PWD/workflows/torax_nice_utils/plot_validation.py \
  --shot_nr $SHOT_NR \
  --dina_uri "$PLOTDIR/${SHOT_NR}_in" \
  --nice_uri "$PLOTDIR/${SHOT_NR}_out_nice_evo_rd" \
  --torax_uri "$PLOTDIR/${SHOT_NR}_out_torax" \
  --output_dir "$SUBDIR/tmp" \
  --t_list "${T_LIST[@]}"