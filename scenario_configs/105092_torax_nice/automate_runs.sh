# This file expects to be run inside the parent directory

source ../../run/imas_base_env

echo "$(date +%H):$(date +%M):$(date +%S) PREPROCESSING INPUT DATA"
python ../../scripts/convert_dina_data_to_input.py \
  --source_uri "imas:mdsplus?path=/home/ITER/dubrovm/public/imasdb/iter/3/105092/1" \
  --backup_uri "imas:hdf5?path=/home/ITER/sanderm/public/imasdb/ITER/4/666666/3" \
  --sink_uri "imas:hdf5?path=$(pwd)/tmp/data/105092_in" \
  --n_timeslices 51

echo "$(date +%H):$(date +%M):$(date +%S) CREATING RUNNABLE YMMSL FILE"
# Use sed to replace the matching substrings
basedir="$(dirname "$(dirname "$PWD")")"
files=(
  "self_consistent_transport_torax.ymmsl"
  "magnetically_controlled_torax.ymmsl"
)
for file in "${files[@]}"; do
  sed "s|\[BASEDIR_PLACEHOLDER\]|$basedir|g"  ".$file" > $file
done

echo "$(date +%H):$(date +%M):$(date +%S) RUNNING MUSCLE"
RUNDIR="tmp/m3_runs/run_prescribed_transport-$(date +%F)-$(date +%H%M%S)" 
mkdir -p $RUNDIR
muscle_manager --start-all self_consistent_transport_torax.ymmsl --run-dir $RUNDIR
# muscle_manager --start-all magnetically_controlled_torax.ymmsl --run-dir $RUNDIR

# echo "$(date +%H):$(date +%M):$(date +%S) PLOTTING"
# python ../../scripts/plot_validation.py
