set -euo pipefail # stop if anything doesn't work

module load MUSCLE3

RUNDIR="$SUBDIR/tmp/m3_runs/run-$(date +%F)-$(date +%H%M%S)" 
mkdir -p $RUNDIR
muscle_manager --start-all "$SUBDIR/workflow.ymmsl" --run-dir $RUNDIR

for ((i=0; i<$RERUN_N_TIMES; i++)); do
    bash "$DIR/preprocess_data.sh" --rerun
    bash "$DIR/create_runnable_files.sh" --rerun
    RUNDIR="$SUBDIR/tmp/m3_runs/run-$(date +%F)-$(date +%H%M%S)" 
    mkdir -p $RUNDIR
    muscle_manager --start-all "$SUBDIR/workflow.ymmsl" --run-dir $RUNDIR
done
