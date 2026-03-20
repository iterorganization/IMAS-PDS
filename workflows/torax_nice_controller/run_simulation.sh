set -euo pipefail # stop if anything doesn't work

module load MUSCLE3

RUNDIR="$SUBDIR/tmp/m3_runs/run-$(date +%F)-$(date +%H%M%S)" 
mkdir -p $RUNDIR
muscle_manager --start-all "$SUBDIR/workflow.ymmsl" --run-dir $RUNDIR
