set -euo pipefail # stop if anything doesn't work

module load IMAS-Python
module load IDStools/2.3.0

SUMMARY_URI=$SOURCE_URI

python $PWD/workflows/utils/convert_dina_data_to_input.py \
  --source_uri $SOURCE_URI \
  --summary_uri $SUMMARY_URI \
  --md_pf_active_uri $MD_PF_ACTIVE \
  --md_pf_passive_uri $MD_PF_PASSIVE \
  --md_wall_uri $MD_WALL \
  --md_iron_core_uri $MD_IRON_CORE \
  --sink_uri $SINK_URI \
  --n_timeslices $N_TIMESLICES


NICE_INPUT_PATH="$PWD/workflows/torax_nice_self_consistent_transport/scenarios/$SHOT_NR/tmp/data/${SHOT_NR}_out_nice"
NEW_INPUT_PATH="$SUBDIR/tmp/data/${SHOT_NR}_out_nice"
NEW_INPUT_PATH2="$SUBDIR/tmp/data/${SHOT_NR}_out_nice2"
if [[ -d "$NICE_INPUT_PATH" ]]; then
  rm -rf "$NEW_INPUT_PATH"
  rm -rf "$NEW_INPUT_PATH2"
  cp -r "$NICE_INPUT_PATH" "$NEW_INPUT_PATH"
  cp -r "$NICE_INPUT_PATH" "$NEW_INPUT_PATH2"
else
  echo "Warning: data should exist at ${NICE_INPUT_PATH}, run corresponding workflow before this one"
  exit 1
fi
