#!/bin/bash
#SBATCH -J inv_conv
#SBATCH -p all
#SBATCH -A iter
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=00:40:00
set -euo pipefail

# SLURM wrapper around bin/pds-run (which writes runs to ../runs/pds_inverse). Submit
# from the repo root, e.g.:
#   sbatch workflows/inverse_convergence/run_job.sbatch 105084   (or run with bash)
#
# Prefer $PDS_REPO (set by `module load PDS`) over $SLURM_SUBMIT_DIR/$PWD:
# SLURM_SUBMIT_DIR is stuck at wherever an enclosing `srun --pty bash` was
# first invoked from for the whole allocation, even after cd-ing elsewhere,
# which silently pointed this at the wrong repo when run interactively.
REPO="${PDS_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
exec "$REPO/bin/pds-run" inverse_convergence "$@"
