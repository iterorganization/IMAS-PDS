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

# Load the PDS module stack unless the caller already has one, so a submitted job does not
# depend on the submitting shell. $PDS_MODULEPATH must hold YOUR module tree: the actors
# resolve via the $EBROOT* it sets, and the manager must be a patched build (see below).
if [[ -z "${MANAGER:-}" ]] && ! command -v muscle_manager >/dev/null 2>&1; then
  if ! command -v module >/dev/null 2>&1; then
    LMOD_INIT="/usr/share/lmod/lmod/init/bash"
    # shellcheck source=/usr/share/lmod/lmod/init/bash
    [[ -f "$LMOD_INIT" ]] && source "$LMOD_INIT"
  fi
  [[ -n "${PDS_MODULEPATH:-}" ]] || { echo "set PDS_MODULEPATH to your module tree, or load PDS before submitting" >&2; exit 1; }
  module use "$PDS_MODULEPATH"
  module load PDS
fi
MANAGER="${MANAGER:-$(command -v muscle_manager)}"
[[ -n "$MANAGER" ]] || { echo "no muscle_manager on PATH" >&2; exit 1; }

# Cases name ${PDS_REPO} and ${SCENARIOS_REPO}; stock muscle3 passes setting values through
# verbatim, so an unpatched manager hands the actors a literal "${SCENARIOS_REPO}/...".
MANAGER_PY="$(dirname "$MANAGER")/python"
[[ -x "$MANAGER_PY" ]] || MANAGER_PY="$(command -v python3 || true)"
if [[ -x "$MANAGER_PY" ]]; then
  MUSCLE3_MOD="$("$MANAGER_PY" -c 'import muscle3,os;print(os.path.join(os.path.dirname(muscle3.__file__),"muscle_manager.py"))' 2>/dev/null || true)"
  if [[ -f "$MUSCLE3_MOD" ]] && ! grep -q expand_settings "$MUSCLE3_MOD"; then
    echo "ERROR: $MANAGER is not patched -- \${SCENARIOS_REPO} will not expand." >&2
    echo "       Run setup_files/apply_patches.sh against that install." >&2
    exit 1
  fi
fi

RUN_DIR="$REPO/run/out/${CASE_NAME%.ymmsl}"
mkdir -p "$RUN_DIR"
exec "$MANAGER" --start-all --run-dir "$RUN_DIR" "$CASE"
