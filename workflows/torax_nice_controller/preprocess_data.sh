set -euo pipefail # stop if anything doesn't work

python $PWD/workflows/torax_nice_utils/convert_dina_data_to_input.py \
  --source_uri $SOURCE_URI \
  --backup_uri $BACKUP_URI \
  --sink_uri $SINK_URI \
  --n_timeslices $N_TIMESLICES
