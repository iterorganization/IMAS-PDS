#!/bin/bash
#SBATCH -J inv_conv
#SBATCH -p all
#SBATCH -A iter
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=00:40:00
set -euo pipefail

# SLURM wrapper around bin/pds-inverse (which writes runs to ~/runs/pds_inverse). Submit
# from the repo root, e.g.:
#   sbatch workflows/inverse_convergence/run_job.sbatch 105084   (or run with bash)
REPO="${SLURM_SUBMIT_DIR:-$PWD}"
exec "$REPO/bin/pds-inverse" "$@"
