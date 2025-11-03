# This file expects to be run inside the parent directory

source ../../run/imas_base_env

echo "$(date +%H):$(date +%M):$(date +%S) PREPROCESSING INPUT DATA"
python ../torax_nice_utils/convert_dina_data_to_input.py \
  --source_uri "imas:hdf5?path=/work/imas/shared/imasdb/ITER/3/105084/1" \
  --backup_uri "imas:hdf5?path=/home/ITER/sanderm/public/imasdb/ITER/4/666666/3" \
  --sink_uri "imas:hdf5?path=$(pwd)/tmp/data/105084_nice_in" \
  --n_timeslices 51

imas convert "imas:mdsplus?path=/work/imas/shared/imasdb/ITER/3/105084/1" $IMAS_VERSION "imas:hdf5?path=$(pwd)/tmp/data/105084_from_dina_in"

# make METIS dataset
echo "$(date +%H):$(date +%M):$(date +%S) Making METIS dataset"
matlab -batch "[s,t] = unix('which python');pyenv('Version',strtrim(t),'ExecutionMode','InProcess'); addpath(pwd);cd('tmp');make_metis_from_dina_105084_interpretative;"

echo "$(date +%H):$(date +%M):$(date +%S) CREATING RUNNABLE YMMSL FILE"
  # Use sed to replace the matching substrings
  file="metis_nice_inverse_from_dina_interpretative_105084.ymmsl"
  basedir="$(dirname "$(dirname "$PWD")")"
  echo basedir= $basedir
  sed "s|\[BASEDIR_PLACEHOLDER\]|$basedir|g"  ".$file" > $file

echo "$(date +%H):$(date +%M):$(date +%S) RUNNING MUSCLE"
RUNDIR="tmp/m3_runs/run_prescribed_transport-$(date +%F)-$(date +%H%M%S)" 
mkdir -p $RUNDIR
muscle_manager --start-all metis_nice_inverse_from_dina_interpretative_105084.ymmsl --run-dir $RUNDIR

echo "$(date +%H):$(date +%M):$(date +%S) PLOTTING"
python ../../scripts/plot_validation.py
