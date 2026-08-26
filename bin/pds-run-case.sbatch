#!/bin/bash
#SBATCH -J pds_case
#SBATCH -p all
#SBATCH -A iter
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
set -euo pipefail

# SLURM wrapper that runs a case folder created by bin/pds-create-case. Submit from the
# repo root, e.g.:
#
#   bin/pds-create-case inverse_convergence 105084
#   sbatch bin/pds-run-case.sbatch cases/inverse_convergence_105084
#
# Override resources for a smaller run:
#
#   sbatch --time=00:20:00 --cpus-per-task=8 bin/pds-run-case.sbatch cases/prescribed_transport_105084
#
# Extra arguments are passed to muscle_manager as overlay yMMSL files, stacked after the
# case (the last value given for a key wins):
#
#   sbatch bin/pds-run-case.sbatch cases/inverse_convergence_105084 ./cold-start.ymmsl

CASE_ARG="${1:-}"
[[ -n "$CASE_ARG" ]] || { echo "usage: $0 <case-dir> [overlay.ymmsl ...]" >&2; exit 1; }
shift
OVERLAYS=("$@")

PDS_REPO="${PDS_REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
export PDS_REPO

CASE_DIR="$CASE_ARG"
[[ -d "$CASE_DIR" ]] || CASE_DIR="$PDS_REPO/$CASE_ARG"
[[ -d "$CASE_DIR" ]] || { echo "$0: no case dir $CASE_ARG" >&2; exit 1; }

export YMMSL_PATH="$PDS_REPO/workflows${YMMSL_PATH:+:$YMMSL_PATH}"

if [[ -z "${MANAGER:-}" ]]; then
  : "${PDS_MODULEPATH:=/home/ITER/blokhus/public/modules/all}"
  if [[ -z "${EBROOTIMASMINMUSCLE3:-}" ]]; then
    LMOD_INIT="/usr/share/lmod/lmod/init/bash"
    if [[ -f "$LMOD_INIT" ]]; then
      source "$LMOD_INIT"
      module use "$PDS_MODULEPATH" 2>/dev/null || true
      module load IMAS-MUSCLE3/1.0.0-intel-2025b-pds 2>/dev/null || true
    fi
  fi
  : "${EBROOTIMASMINMUSCLE3:?$0: IMAS-MUSCLE3/1.0.0-intel-2025b-pds not loaded and could not be loaded automatically -- run 'module use $PDS_MODULEPATH && module load PDS' first}"
  MANAGER="$(command -v muscle_manager)"
  : "${MANAGER:?$0: muscle_manager not on PATH even though IMAS-MUSCLE3 is loaded -- its MUSCLE3 dependency is missing}"
fi

stack=()
for f in workflow.ymmsl workflow_settings.ymmsl scenario_settings.ymmsl; do
  [[ -f "$CASE_DIR/$f" ]] && stack+=("$CASE_DIR/$f")
done

RUN_DIR="$PDS_REPO/run/out/$(basename "$CASE_DIR")"
# A leftover instances/ dir from a previous run of this case makes muscle_manager fail with
# "Instance already has a directory", so start from a clean run dir each time.
rm -rf "$RUN_DIR"
mkdir -p "$RUN_DIR"
exec "$MANAGER" --start-all --run-dir "$RUN_DIR" "${stack[@]}" "${OVERLAYS[@]}"
