# This file expects to be run inside the parent directory

SHOT_NR=$1
SOURCE_URI=$2
BACKUP_URI=$3
SINK_URI=$4
N_TIMESLICES=$5
shift 5
T_LIST=("$@")

basedir="$(dirname "$(dirname "$PWD")")"

source "$basedir/run/imas_base_env"

echo "$(date +%H):$(date +%M):$(date +%S) PREPROCESSING INPUT DATA"
python $basedir/scenario_configs/torax_nice_utils/convert_dina_data_to_input.py \
  --source_uri $SOURCE_URI \
  --backup_uri $BACKUP_URI \
  --sink_uri $SINK_URI \
  --n_timeslices $N_TIMESLICES

echo "$(date +%H):$(date +%M):$(date +%S) CREATING RUNNABLE YMMSL FILE"
# Use sed to replace the matching substrings
files=(
  "self_consistent_transport_torax.ymmsl"
  "magnetically_controlled_torax.ymmsl"
  "config_torax.py"
  "config_nice.xml"
)
for file in "${files[@]}"; do
  if test -f ".$file"; then
    cp ".$file" $file
  else
    cp "$basedir/scenario_configs/torax_nice_utils/.$file" $file
  fi
  sed -i "s|\[BASEDIR_PLACEHOLDER\]|$basedir|g" $file
  sed -i "s|\[SHOT_NR\]|$SHOT_NR|g" $file
done

echo "$(date +%H):$(date +%M):$(date +%S) RUNNING MUSCLE"
RUNDIR="tmp/m3_runs/run_prescribed_transport-$(date +%F)-$(date +%H%M%S)" 
mkdir -p $RUNDIR
muscle_manager --start-all self_consistent_transport_torax.ymmsl --run-dir $RUNDIR
# muscle_manager --start-all magnetically_controlled_torax.ymmsl --run-dir $RUNDIR

echo "$(date +%H):$(date +%M):$(date +%S) PLOTTING"
python $basedir/scenario_configs/torax_nice_utils/plot_validation.py \
  --shot_nr $SHOT_NR \
  --dina_uri "$PWD/tmp/data/${SHOT_NR}_in" \
  --nice_uri "$PWD/tmp/data/${SHOT_NR}_out_nice" \
  --torax_uri "$PWD/tmp/data/${SHOT_NR}_out_torax" \
  --output_dir "$PWD/tmp" \
  --t_list "${T_LIST[@]}"
