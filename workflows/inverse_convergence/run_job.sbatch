#!/bin/bash
#SBATCH -J inv_conv
#SBATCH -p all
#SBATCH -A iter
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=00:40:00
set -euo pipefail

# SLURM wrapper around bin/pds-inverse. The manager writes its run_<model>_<timestamp>/ dir
# into the current directory, so cd into a (gitignored) runs area first -- point m3dash at
# run/tmp to discover them. Submit from the repo root, e.g.:
#   sbatch workflows/inverse_convergence/run_job.sbatch 105084   (or run with bash)
REPO="${SLURM_SUBMIT_DIR:-$PWD}"
mkdir -p "$REPO/run/tmp/m3_runs"
cd "$REPO/run/tmp/m3_runs"
exec "$REPO/bin/pds-inverse" "$@"
