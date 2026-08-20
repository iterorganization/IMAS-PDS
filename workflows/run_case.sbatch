#!/bin/bash
#SBATCH -J pds_case
#SBATCH -p all
#SBATCH -A iter
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
set -euo pipefail

# SLURM wrapper around a case file. Submit from the repo root, e.g.:
#   sbatch workflows/run_case.sbatch 105084_convergence      (or run with bash)
#   sbatch workflows/run_case.sbatch 105084_convergence /tmp/window.ymmsl
#
# The defaults above suit a convergence run; override for anything smaller:
#   sbatch --time=00:20:00 --cpus-per-task=8 workflows/run_case.sbatch 105084_prescribed
#
CASE_NAME="${1:-}"
[[ -n "$CASE_NAME" ]] || { echo "usage: $0 <case> [override.ymmsl ...]" >&2; exit 1; }
shift

OVERLAYS=("$@")

export PDS_REPO="/home/ITER/dejongy/projects/pds"

if [[-f $CASE_NAME ]]; then
  CASE="$CASE_NAME"
else
  CASE="$PDS_REPO/cases/${CASE_NAME%.ymmsl}.ymmsl"
fi

[[ -f "$CASE" ]] || { echo "no case file $CASE" >&2; exit 1; }

export YMMSL_PATH="$PDS_REPO/workflows"

RUN_DIR="$PDS_REPO/run/out/${CASE_NAME%.ymmsl}"
mkdir -p "$RUN_DIR"
exec muscle_manager --start-all --run-dir "$RUN_DIR" "$CASE" "${OVERLAYS[@]}"
