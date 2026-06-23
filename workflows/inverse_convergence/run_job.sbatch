#!/bin/bash
#SBATCH -J inv_conv
#SBATCH -p all
#SBATCH -A iter
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=00:40:00
set -euo pipefail

# SLURM wrapper around bin/pds-inverse (the outer Picard convergence runs inside MUSCLE3, so
# there is no shell rerun loop). Submit from the repo root, e.g.:
#   sbatch workflows/inverse_convergence/run_job.sbatch 105084   (or run with bash)
REPO="${SLURM_SUBMIT_DIR:-$PWD}"
exec "$REPO/bin/pds-inverse" "$@"
