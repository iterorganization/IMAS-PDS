#!/bin/bash
#SBATCH -J presc_transport
#SBATCH -p all
#SBATCH -A iter
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=00:20:00
set -euo pipefail

# SLURM wrapper around bin/pds-run (which writes runs to
# scenarios/<shot>/tmp/runs). Submit from the repo root, e.g.:
#   sbatch workflows/prescribed_transport/run_job.sbatch 105073   (or run with bash)
REPO="${SLURM_SUBMIT_DIR:-$PWD}"
exec "$REPO/bin/pds-run" prescribed_transport "$@"
