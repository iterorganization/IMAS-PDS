set -euo pipefail # stop if anything doesn't work

export matlab_path="$PWD/workflows/metis_alone_utils"
export IMAS_AL_DISABLE_VALIDATE=1 
RUNDIR="$SUBDIR/tmp/m3_runs/run-$(date +%F)-$(date +%H%M%S)" 
mkdir -p $RUNDIR
muscle_manager --start-all "$SUBDIR/workflow.ymmsl" --run-dir $RUNDIR
