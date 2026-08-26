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

show_help() {
  cat <<EOF
Usage: bash $0 <workflow> <scenario> [optional args...]"

Options:
  -h, --help      Show this help message and exit

Examples:
  bash $(basename "$0") inverse_convergence 105092
EOF
}

# ---- argument parsing ---------------------------------------

case "$1" in
  -h|--help)
    show_help
    exit 0
    ;;
esac

if [[ $# -lt 2 ]]; then
  error "Usage: bash $0 <workflow> <scenario> [optional args...]"
fi

export DIR="$PWD/workflows/$1"
export SUBDIR="$DIR/scenarios/$2"
shift 2
export EXTRA_ARGS=("$@")

# ---- module environment ---------------------------------------
[[ -n "${PDS_REPO:-}" ]] || error "PDS module not loaded. Run 'module use /work/projects/pds/modules/all && module load PDS' first (see setup_files/easyconfigs/p/PDS/)."
[[ "$PDS_REPO" == "$PWD" ]] || error "PDS_REPO ($PDS_REPO) does not match \$PWD ($PWD). Run 'module use /work/projects/pds/modules/all && module load PDS' from this checkout's root."

export SCENARIO_CONFIG="$SUBDIR/scenario_config.env"
source $SCENARIO_CONFIG
source "$MD_COLLECTION"

for arg in "${EXTRA_ARGS[@]}"; do
  if [[ "$arg" != -* ]]; then
    export "$arg"
  fi
done

# ---- validation ---------------------------------------------

[[ -d "$DIR" ]] || error "Directory does not exist: $DIR"
[[ -d "$SUBDIR" ]] || error "Subdirectory does not exist: $SUBDIR"
[[ -f $SCENARIO_CONFIG ]] || error "Missing scenario_config.env in $SUBDIR"
[[ -f "$DIR/preprocess_data.sh" ]] || error "Missing or non-executable preprocess_data.sh in $DIR"
[[ -f "$DIR/postprocess_data.sh" ]] || error "Missing or non-executable postprocess_data.sh in $DIR"
[[ -f "$DIR/run_simulation.sh" ]] || error "Missing run_simulation.sh in $DIR"

# ---- run the script ----------------------------------------
echo "$(date +%H):$(date +%M):$(date +%S) PREPROCESSING INPUT DATA"
bash "$DIR/preprocess_data.sh" "${EXTRA_ARGS[@]}"
if [[ -f "$DIR/create_runnable_files.sh" ]]; then
  echo "$(date +%H):$(date +%M):$(date +%S) CREATING RUNNABLE YMMSL FILE"
  bash "$DIR/create_runnable_files.sh" "${EXTRA_ARGS[@]}"
fi
echo "$(date +%H):$(date +%M):$(date +%S) RUNNING MUSCLE"
bash "$DIR/run_simulation.sh" "${EXTRA_ARGS[@]}"
echo "$(date +%H):$(date +%M):$(date +%S) PLOTTING"
bash "$DIR/postprocess_data.sh" "${EXTRA_ARGS[@]}"
