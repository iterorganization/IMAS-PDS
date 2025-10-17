# This file expects to be run inside the parent directory

SHOT_NR="105084"
SOURCE_URI="imas:hdf5?path=/work/imas/shared/imasdb/ITER/3/105084/1"
BACKUP_URI="imas:hdf5?path=/home/ITER/sanderm/public/imasdb/ITER/4/666666/3"
SINK_URI="imas:hdf5?path=$(pwd)/tmp/data/${SHOT_NR}_in"
N_TIMESLICES=51

basedir="$(dirname "$(dirname "$PWD")")"

bash "$basedir/scenario_configs/torax_nice_utils/automate_runs_torax_nice.sh" \
  "$SHOT_NR" \
  "$SOURCE_URI" \
  "$BACKUP_URI" \
  "$SINK_URI" \
  "$N_TIMESLICES"
