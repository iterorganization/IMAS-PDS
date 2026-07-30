#!/bin/bash
#SBATCH -J torax_nice_self_rd
#SBATCH -p all
#SBATCH -A iter
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=00:40:00
set -euo pipefail

# SLURM wrapper around bin/pds-run (which writes runs to scenarios/<shot>/tmp/runs). Submit
# from the repo root, e.g.:
#   sbatch workflows/torax_nice_self_rd_controller/run_job.sbatch 105084   (or run with bash)
REPO="${SLURM_SUBMIT_DIR:-$PWD}"
exec "$REPO/bin/pds-run" torax_nice_self_rd_controller "$@"