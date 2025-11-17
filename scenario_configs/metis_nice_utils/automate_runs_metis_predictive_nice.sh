# This file expects to be run inside the parent directory

SHOT_NR=$1
SOURCE_URI=$2
BACKUP_URI=$3
SINK_URI=$4
SINK_UPDATE_URI=$5
SINK_METIS_URI=$6
N_TIMESLICES=$7

shift 7
T_LIST=("$@")

echo "Inputs:"
echo "SHOT_NR=" $SHOT_NR
echo "SOURCE_URI=" $SOURCE_URI
echo "BACKUP_URI=" $BACKUP_URI
echo "SINK_URI=" $SINK_URI
echo "SINK_UPDATE_URI=" $SINK_UPDATE_URI
echo "SINK_METIS_URI=" $SINK_METIS_URI
echo "N_TIMESLICES=" $N_TIMESLICES
echo "T_LIST=" "${T_LIST[@]}"

basedir="$(dirname "$(dirname "$PWD")")"
export matlab_path=$basedir/scenario_configs/metis_nice_utils
source "$basedir/run/imas_base_env"
export IMAS_AL_DISABLE_VALIDATE=1 

echo "$(date +%H):$(date +%M):$(date +%S) PREPROCESSING INPUT DATA"
python $basedir/scenario_configs/metis_nice_utils/convert_dina_data_to_input.py \
  --source_uri $SOURCE_URI \
  --backup_uri $BACKUP_URI \
  --sink_uri $SINK_URI \
  --n_timeslices $N_TIMESLICES

imas convert $SOURCE_URI $IMAS_VERSION $SINK_UPDATE_URI

# make METIS dataset
export metis_dina_source=$SINK_UPDATE_URI
export metis_imas_dataset=$SINK_METIS_URI
echo "$(date +%H):$(date +%M):$(date +%S) Making METIS dataset"
matlab -batch "[s,t] = unix('which python');pyenv('Version',strtrim(t),'ExecutionMode','InProcess'); addpath(getenv('matlab_path'));cd('tmp');make_metis_from_dina_interpretative;"


echo "$(date +%H):$(date +%M):$(date +%S) CREATING RUNNABLE YMMSL FILE"
# Use sed to replace the matching substrings
files=(
  "metis_nice_inverse_from_dina_predictive.ymmsl"
  "param.xml"
)
for file in "${files[@]}"; do
  if test -f ".$file"; then
    cp ".$file" $file
  else
    cp "$basedir/scenario_configs/metis_nice_utils/.$file" $file
  fi
  sed -i "s|\[BASEDIR_PLACEHOLDER\]|$basedir|g" $file
  sed -i "s|\[SHOT_NR\]|$SHOT_NR|g" $file
done

echo "$(date +%H):$(date +%M):$(date +%S) RUNNING MUSCLE"
RUNDIR="tmp/m3_runs/run_metis_nice_inverse-$(date +%F)-$(date +%H%M%S)" 
mkdir -p $RUNDIR
muscle_manager --start-all metis_nice_inverse_from_dina_predictive.ymmsl --run-dir $RUNDIR

echo "$(date +%H):$(date +%M):$(date +%S) PLOTTING"
python $basedir/scenario_configs/metis_nice_utils/plot_validation_metis_nice.py \
  --shot_nr $SHOT_NR \
  --dina_uri "$PWD/tmp/data/${SHOT_NR}_dina_in" \
  --nice_uri "$PWD/tmp/data/${SHOT_NR}_nice_out" \
  --metis_uri "$PWD/tmp/data/${SHOT_NR}_metis_out" \
  --output_dir "$PWD/tmp" \
  --t_list "${T_LIST[@]}"
