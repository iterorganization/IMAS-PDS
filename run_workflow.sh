# ARG 1: Name of workflow inside workflows dir
# ARG 2: Name of scenario inside workflows/<workflow_dir>/scenarios
# Any other arguments are passed to the run_simulation script

#!/usr/bin/env bash
set -euo pipefail

# ---- helpers -------------------------------------------------

error() {
  echo "❌ $1" >&2
  exit 1
}

# ---- argument parsing ---------------------------------------

if [[ $# -lt 2 ]]; then
  error "Usage: $0 <directory> <subdirectory> [optional args...]"
fi

export DIR="$PWD/workflows/$1"
export SUBDIR="$DIR/scenarios/$2"
shift 2
export EXTRA_ARGS=("$@")
export SCENARIO_CONFIG="$SUBDIR/scenario_config.env"
export SCRIPT="$DIR/my_bash_script.sh"

source "$PWD/run/imas_base_env"

source $SCENARIO_CONFIG

# ---- validation ---------------------------------------------

[[ -d "$DIR" ]] || error "Directory does not exist: $DIR"
[[ -d "$SUBDIR" ]] || error "Subdirectory does not exist: $SUBDIR"
[[ -f $SCENARIO_CONFIG ]] || error "Missing scenario_config.env in $SUBDIR"
[[ -f "$DIR/preprocess_data.sh" ]] || error "Missing or non-executable preprocess_data.sh in $DIR"
[[ -f "$DIR/create_runnable_files.sh" ]] || error "Missing or non-executable create_runnable_files.sh in $DIR"
[[ -f "$DIR/run_simulation.sh" ]] || error "Missing or non-executable run_simulation.sh in $DIR"
[[ -f "$DIR/plot_results.sh" ]] || error "Missing or non-executable plot_results.sh in $DIR"
[[ -f "$DIR/.workflow.ymmsl" ]] || error "Missing or non-executable workflow.ymmsl in $DIR"

# ---- run the script ----------------------------------------
echo "$(date +%H):$(date +%M):$(date +%S) PREPROCESSING INPUT DATA"
bash "$DIR/preprocess_data.sh"
echo "$(date +%H):$(date +%M):$(date +%S) CREATING RUNNABLE YMMSL FILE"
bash "$DIR/create_runnable_files.sh"
echo "$(date +%H):$(date +%M):$(date +%S) RUNNING MUSCLE"
bash "$DIR/run_simulation.sh" "${EXTRA_ARGS[@]}"
echo "$(date +%H):$(date +%M):$(date +%S) PLOTTING"
bash "$DIR/plot_results.sh"
