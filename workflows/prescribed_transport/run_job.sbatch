#!/bin/bash
#SBATCH -J presc_transport
#SBATCH -p all
#SBATCH -A iter
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=00:20:00
set -euo pipefail

# SLURM wrapper around a case file. Submit from the repo root, e.g.:
#   sbatch workflows/prescribed_transport/run_job.sbatch 105084   (or run with bash)
#
# Takes a shot number and runs cases/<shot>_prescribed.ymmsl. The case is
# self-contained -- it imports this workflow, so there is one file on the
# command line and no generated scenario directory.
#
# Prefer $PDS_REPO (set by `module load PDS`) over $SLURM_SUBMIT_DIR/$PWD:
REPO="${PDS_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

SHOT="${1:-${SHOT_NR:-}}"
[[ -n "$SHOT" ]] || { echo "usage: $0 <shot>" >&2; exit 1; }

CASE="$REPO/cases/${SHOT}_prescribed.ymmsl"
[[ -f "$CASE" ]] || { echo "no case file $CASE" >&2; exit 1; }

# The case names ${SCENARIOS_REPO} and ${PDS_REPO}; muscle_manager expands both
# (see ci/patches/muscle3-manager-env-vars-and-input-copies.patch).
export PDS_REPO="$REPO"
: "${SCENARIOS_REPO:=$(cd "$REPO/../pds-scenarios" && pwd)}"
export SCENARIOS_REPO
export YMMSL_PATH="$REPO/workflows"

RUN_DIR="$REPO/run/out/${SHOT}_prescribed"
mkdir -p "$RUN_DIR"
exec muscle_manager --start-all --run-dir "$RUN_DIR" "$CASE"
