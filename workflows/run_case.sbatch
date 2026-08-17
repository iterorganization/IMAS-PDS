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
#   sbatch workflows/run_case.sbatch 105084_convergence /tmp/window.ymmsl
#
# The defaults above suit a convergence run; override for anything smaller:
#   sbatch --time=00:20:00 --cpus-per-task=8 workflows/run_case.sbatch 105084_prescribed
#
CASE_NAME="${1:-}"
[[ -n "$CASE_NAME" ]] || { echo "usage: $0 <case> [override.ymmsl ...]" >&2; exit 1; }
shift
# Any further arguments are stacked after the case, last value for a key winning.
OVERLAYS=("$@")

# Export the checkout BEFORE loading the module, so PDS.lua wires itself to this one rather
# than falling back to the clone it was built from (a shared module tree would otherwise run
# its owner's code and write into their checkout).
#
# Falls back to the submit directory, not ${BASH_SOURCE[0]}: SLURM copies the batch script
# into its spool directory, so the script's own path is not the repo.
REPO="${PDS_REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
[[ -f "$REPO/workflows/lib/programs.ymmsl" ]] || {
  echo "PDS_REPO=$REPO is not a PDS checkout; export PDS_REPO or submit from the repo root" >&2
  exit 1; }
export PDS_REPO="$REPO"

# Load the PDS module stack unless the caller already has one, so a submitted job does not
# depend on the submitting shell. Prefer submitting with --export=NONE so it never does.
if [[ -z "${MANAGER:-}" ]] && ! command -v muscle_manager >/dev/null 2>&1; then
  if ! command -v module >/dev/null 2>&1; then
    LMOD_INIT="/usr/share/lmod/lmod/init/bash"
    # shellcheck source=/usr/share/lmod/lmod/init/bash
    [[ -f "$LMOD_INIT" ]] && source "$LMOD_INIT"
  fi
  command -v module >/dev/null 2>&1 || { echo "no Lmod available, and no muscle_manager on PATH" >&2; exit 1; }
  loaded=0
  for mp in "${PDS_MODULEPATH:-}" "$HOME/public/modules"; do
    [[ -n "$mp" && -d "$mp/PDS" ]] || continue
    module use "$mp"
    if module load PDS 2>/dev/null; then loaded=1; break; fi
  done
  [[ $loaded -eq 1 ]] || { echo "could not load the PDS module; set PDS_MODULEPATH to your module tree" >&2; exit 1; }
fi

CASE="$REPO/cases/${CASE_NAME%.ymmsl}.ymmsl"
[[ -f "$CASE" ]] || { echo "no case file $CASE" >&2; exit 1; }

: "${SCENARIOS_REPO:=$(cd "$REPO/../pds-scenarios" && pwd)}"
export SCENARIOS_REPO
export YMMSL_PATH="$REPO/workflows"
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
exec "$MANAGER" --start-all --run-dir "$RUN_DIR" "$CASE" "${OVERLAYS[@]}"
