set -euo pipefail # stop if anything doesn't work

# The outer Picard convergence runs INSIDE MUSCLE3 (the loop driver iterates until the
# coil-current change is below tolerance), so there is no shell RERUN loop. Run the venv
# manager directly (do NOT `module load MUSCLE3` -- it shadows the venv with an old
# muscle3/ymmsl). The workflow structure and the scenario settings are stacked.
MANAGER="$PWD/../opt/venv-m3091-actors/bin/muscle_manager"

RUNDIR="$SUBDIR/tmp/m3_runs/run-$(date +%F)-$(date +%H%M%S)"
mkdir -p "$RUNDIR"
echo "Using running directory: $RUNDIR"
"$MANAGER" --start-all "$SUBDIR/workflow.ymmsl" "$SUBDIR/settings.ymmsl" --run-dir "$RUNDIR"
