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
#
# The defaults above suit a convergence run; override for anything smaller:
#   sbatch --time=00:20:00 --cpus-per-task=8 workflows/run_case.sbatch 105084_prescribed
#
# Prefer $PDS_REPO (set by `module load PDS`) over $SLURM_SUBMIT_DIR/$PWD:
# SLURM_SUBMIT_DIR is stuck at wherever an enclosing `srun --pty bash` was
# first invoked from for the whole allocation, even after cd-ing elsewhere,
# which silently pointed this at the wrong repo when run interactively.
REPO="${PDS_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

CASE_NAME="${1:-}"
[[ -n "$CASE_NAME" ]] || { echo "usage: $0 <case>   e.g. 105084_convergence" >&2; exit 1; }

CASE="$REPO/cases/${CASE_NAME%.ymmsl}.ymmsl"
[[ -f "$CASE" ]] || { echo "no case file $CASE" >&2; exit 1; }

export PDS_REPO="$REPO"
: "${SCENARIOS_REPO:=$(cd "$REPO/../pds-scenarios" && pwd)}"
export SCENARIOS_REPO
export YMMSL_PATH="$REPO/workflows"

RUN_DIR="$REPO/run/out/${CASE_NAME%.ymmsl}"
mkdir -p "$RUN_DIR"
exec muscle_manager --start-all --run-dir "$RUN_DIR" "$CASE"
