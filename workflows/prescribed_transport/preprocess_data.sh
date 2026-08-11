set -euo pipefail # stop if anything doesn't work

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

cp -r "$SUBDIR/tmp/data/${SHOT_NR}_in" "$SUBDIR/tmp/data/${SHOT_NR}_in_waveform_editor"
cp -r "$SUBDIR/tmp/data/${SHOT_NR}_in_md" "$SUBDIR/tmp/data/${SHOT_NR}_in_md_waveform_editor"
