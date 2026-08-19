set -euo pipefail # stop if anything doesn't work

mkdir -p "$SUBDIR/lib"
envsubst '${PDS_REPO}' < "$PDS_REPO/workflows/lib/local_programs.ymmsl" \
  > "$SUBDIR/lib/local_programs.ymmsl"
export YMMSL_PATH="$SUBDIR:$PDS_REPO/workflows${YMMSL_PATH:+:$YMMSL_PATH}"

RUNDIR="$SUBDIR/tmp/m3_runs/run-$(date +%F)-$(date +%H%M%S)"
mkdir -p $RUNDIR
muscle_manager --start-all "$SUBDIR/workflow.ymmsl" --run-dir $RUNDIR
