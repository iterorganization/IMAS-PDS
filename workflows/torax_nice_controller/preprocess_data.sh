set -euo pipefail # stop if anything doesn't work

module load IMAS-Python
module load IDStools/2.3.0

SUMMARY_URI=$SOURCE_URI

python $PWD/workflows/torax_nice_utils/convert_dina_data_to_input.py \
  --source_uri $SOURCE_URI \
  --summary_uri $SUMMARY_URI \
  --backup_uri $BACKUP_URI \
  --sink_uri $SINK_URI \
  --n_timeslices $N_TIMESLICES

NICE_INPUT_PATH="$PWD/workflows/torax_nice_self_consistent_transport/scenarios/$SHOT_NR/tmp/data/${SHOT_NR}_out_nice"
NEW_INPUT_PATH="$SUBDIR/tmp/data/${SHOT_NR}_out_nice"
if [[ -d "$NICE_INPUT_PATH" ]]; then
  rm -rf "$NEW_INPUT_PATH"
  cp -r "$NICE_INPUT_PATH" "$NEW_INPUT_PATH"
else
  echo "Warning: data should exist at ${NICE_INPUT_PATH}, run corresponding workflow before this one"
  exit 1
fi
