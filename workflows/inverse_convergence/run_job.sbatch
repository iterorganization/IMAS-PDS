#!/bin/bash
#SBATCH -J inv_convergence
#SBATCH -p all
#SBATCH -A iter
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
set -euo pipefail

# SLURM wrapper around a case file. Submit from the repo root, e.g.:
#   sbatch workflows/inverse_convergence/run_job.sbatch 105084   (or run with bash)
#
# Prefer $PDS_REPO (set by `module load PDS`) over $SLURM_SUBMIT_DIR/$PWD:
REPO="${PDS_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

SHOT="${1:-${SHOT_NR:-}}"
[[ -n "$SHOT" ]] || { echo "usage: $0 <shot>" >&2; exit 1; }

CASE="$REPO/cases/${SHOT}_convergence.ymmsl"
[[ -f "$CASE" ]] || { echo "no case file $CASE" >&2; exit 1; }

export PDS_REPO="$REPO"
: "${SCENARIOS_REPO:=$(cd "$REPO/../pds-scenarios" && pwd)}"
export SCENARIOS_REPO
export YMMSL_PATH="$REPO/workflows"

RUN_DIR="$REPO/run/out/${SHOT}_convergence"
mkdir -p "$RUN_DIR"
exec muscle_manager --start-all --run-dir "$RUN_DIR" "$CASE"
