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
  bash $(basename "$0") torax_nice_self_consistent_transport 105092
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

# Ensure the PDS module stack (setup_files/PDS.lua) is loaded, so this script
# is self-contained regardless of what the caller already has loaded --
# workflows/lib/local_programs.ymmsl's actors resolve via the $EBROOT* vars
# this module sets. Run from this checkout's root (required below anyway),
# so PDS.lua's own PWD-detection picks this checkout as PDS_REPO.
# PDS_MODULEPATH points at wherever PDS.lua was deployed; override it if
# yours differs from the default shared location.
if ! command -v module >/dev/null 2>&1; then
  LMOD_INIT="/usr/share/lmod/lmod/init/bash"
  # shellcheck source=/usr/share/lmod/lmod/init/bash
  [[ -f "$LMOD_INIT" ]] && source "$LMOD_INIT"
fi
: "${PDS_MODULEPATH:=/home/ITER/blokhus/public/modules}"
module use "$PDS_MODULEPATH"
module load PDS

export SCENARIO_CONFIG="$SUBDIR/scenario_config.env"
source "$PWD/run/imas_base_env"
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
# A workflow runs either via a self-contained job script (run_job.sbatch, the de-templated
# style) or the older create_runnable_files.sh + run_simulation.sh pair.
[[ -f "$DIR/run_job.sbatch" || -f "$DIR/run_simulation.sh" ]] || \
  error "Missing run_job.sbatch or run_simulation.sh in $DIR"

# ---- run the script ----------------------------------------
echo "$(date +%H):$(date +%M):$(date +%S) PREPROCESSING INPUT DATA"
bash "$DIR/preprocess_data.sh" "${EXTRA_ARGS[@]}"
if [[ -f "$DIR/create_runnable_files.sh" ]]; then
  echo "$(date +%H):$(date +%M):$(date +%S) CREATING RUNNABLE YMMSL FILE"
  bash "$DIR/create_runnable_files.sh" "${EXTRA_ARGS[@]}"
fi
echo "$(date +%H):$(date +%M):$(date +%S) RUNNING MUSCLE"
if [[ -f "$DIR/run_job.sbatch" ]]; then
  # run_job.sbatch is self-contained: it exports PDS_REPO, generates the scenario paths
  # overlay, and stacks workflow.ymmsl + settings.ymmsl + paths.ymmsl. Runnable with bash
  # (the #SBATCH directives are comments) or via sbatch. It reads the shot from SHOT_NR.
  bash "$DIR/run_job.sbatch"
else
  bash "$DIR/run_simulation.sh" "${EXTRA_ARGS[@]}"
fi
echo "$(date +%H):$(date +%M):$(date +%S) PLOTTING"
bash "$DIR/postprocess_data.sh" "${EXTRA_ARGS[@]}"
