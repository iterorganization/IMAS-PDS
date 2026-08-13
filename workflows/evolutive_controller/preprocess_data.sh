set -euo pipefail # stop if anything doesn't work

module load IMAS-Python
module load IDStools/2.3.0

SUMMARY_URI=$SOURCE_URI

export IMAS_LOGLEVEL=WARNING

python $PWD/workflows/utils/convert_dina_data_to_input.py \
  --source_uri $SOURCE_URI \
  --summary_uri $SUMMARY_URI \
  --md_pf_active_uri $MD_PF_ACTIVE \
  --md_pf_passive_uri $MD_PF_PASSIVE \
  --md_wall_uri $MD_WALL \
  --md_iron_core_uri $MD_IRON_CORE \
  --sink_uri $SINK_URI \
  --md_sink_uri $MD_SINK_URI \
  --n_timeslices $N_TIMESLICES

# until IMAS-AL bug is fixed where hdf5 backend does not respect read mode
cp -r "$SUBDIR/tmp/data/${SHOT_NR}_in" "$SUBDIR/tmp/data/${SHOT_NR}_in_waveform_editor"
cp -r "$SUBDIR/tmp/data/${SHOT_NR}_in_md" "$SUBDIR/tmp/data/${SHOT_NR}_in_md_waveform_editor"

# `source` (-> waveform_editor's `eq` port) needs a NICE-reconstructed equilibrium (r_inboard/r_outboard/
# gm1-9/dvolume_dpsi/j_phi/...), which raw DINA data never has (see workflow.ymmsl). Seed it
# from a completed inverse_convergence run for the same shot, unless one is already staged here.
SEED_OUT_NICE="$PWD/workflows/inverse_convergence/scenarios/${SHOT_NR}/tmp/data/${SHOT_NR}_out_nice"
DEST_OUT_NICE="$SUBDIR/tmp/data/${SHOT_NR}_out_nice"
if [[ ! -e "$DEST_OUT_NICE" ]]; then
  if [[ -e "$SEED_OUT_NICE" ]]; then
    cp -r "$SEED_OUT_NICE" "$DEST_OUT_NICE"
  else
    echo "evolutive_controller: no seed equilibrium at $DEST_OUT_NICE and no" >&2
    echo "companion inverse_convergence output at $SEED_OUT_NICE to copy it from. Run" >&2
    echo "'bash run_workflow.sh inverse_convergence ${SHOT_NR}' first, or place a converged" >&2
    echo "NICE-inverse equilibrium+pf_active snapshot at $DEST_OUT_NICE yourself." >&2
    exit 1
  fi
fi