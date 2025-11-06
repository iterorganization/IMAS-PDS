# This file expects to be run inside the parent directory

SHOT_NR="105073"
SOURCE_URI="imas:mdsplus?path=/home/ITER/dubrovm/public/imasdb/iter/3/105073/6"
BACKUP_URI="imas:hdf5?path=/home/ITER/sanderm/public/imasdb/ITER/4/666666/3"
SINK_URI="imas:hdf5?path=$(pwd)/tmp/data/${SHOT_NR}_in"
N_TIMESLICES=41
T_LIST=(25 100 175)

basedir="$(dirname "$(dirname "$PWD")")"

bash "$basedir/scenario_configs/torax_nice_utils/automate_runs_torax_nice.sh" \
  "$SHOT_NR" \
  "$SOURCE_URI" \
  "$BACKUP_URI" \
  "$SINK_URI" \
  "$N_TIMESLICES" \
  "${T_LIST[@]}"
