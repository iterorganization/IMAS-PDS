# This file expects to be run inside the parent directory

SHOT_NR="105099"
SOURCE_URI="imas:mdsplus?path=/home/ITER/dubrovm/public/imasdb/iter/3/105099/2"
BACKUP_URI="imas:hdf5?path=/home/ITER/sanderm/public/imasdb/ITER/4/666666/3"
SINK_URI="imas:hdf5?path=$(pwd)/tmp/data/${SHOT_NR}_dina_in"
SINK_UPDATE_URI="imas:hdf5?path=$(pwd)/tmp/data/${SHOT_NR}_dina_update_in"
SINK_METIS_URI="imas:hdf5?path=$(pwd)/tmp/data/${SHOT_NR}_metis_in"
N_TIMESLICES=51
T_LIST=(20 35 60)

basedir="$(dirname "$(dirname "$PWD")")"

bash "$basedir/scenario_configs/metis_nice_utils/automate_runs_metis_predictive_nice.sh" \
  "$SHOT_NR" \
  "$SOURCE_URI" \
  "$BACKUP_URI" \
  "$SINK_URI" \
  "$SINK_UPDATE_URI" \
  "$SINK_METIS_URI" \
  "$N_TIMESLICES" \
  "${T_LIST[@]}"
