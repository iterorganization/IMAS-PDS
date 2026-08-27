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
#
# If the case has an env.sh (bin/pds-create-case copies it in from workflows/<workflow>/env.sh,
# if that exists -- see its header), it's sourced right before muscle_manager starts, so an
# imported implementation with no env: override of its own (base_env: MANAGER) still gets a
# run-wide variable it needs -- e.g. workflows/metis_from_dina/env.sh.
#
# If the case has a postprocess.sh (bin/pds-create-case copies it in from
# workflows/<workflow>/postprocess.sh, if that exists -- see its header), it runs once after
# muscle_manager finishes (e.g. validation plots against the run's own output -- see
# workflows/metis_from_dina/postprocess.sh). It gets PDS_REPO/SCENARIOS_REPO/SHOT/CASE_DIR/
# RUN_DIR/PYTHON (the same interpreter muscle_manager itself resolved to -- use "$PYTHON"
# rather than a bare `python`) and should write into $RUN_DIR/ (preprocessing, if any,
# already ran once at bin/pds-create-case time -- see that script's header).

CASE_ARG="${1:-}"
[[ -n "$CASE_ARG" ]] || { echo "usage: $0 <case-dir> [overlay.ymmsl ...]" >&2; exit 1; }
shift
OVERLAYS=("$@")

PDS_REPO="${PDS_REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
export PDS_REPO
export SCENARIOS_REPO="${SCENARIOS_REPO:-/work/projects/pds/pds-scenarios}"

CASE_DIR="$CASE_ARG"
[[ -d "$CASE_DIR" ]] || CASE_DIR="$PDS_REPO/$CASE_ARG"
[[ -d "$CASE_DIR" ]] || { echo "$0: no case dir $CASE_ARG" >&2; exit 1; }
export CASE_DIR

export YMMSL_PATH="$PDS_REPO/workflows${YMMSL_PATH:+:$YMMSL_PATH}"

if [[ -z "${MANAGER:-}" ]]; then
  : "${PDS_MODULEPATH:=/work/projects/pds/modules/all}"
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

# muscle_manager's own shebang is `#!/usr/bin/env python`, i.e. it trusts this exact PATH
# lookup too -- pin postprocess.sh to the same interpreter instead of re-doing a bare `python`
# PATH lookup itself later, after who knows what else has run in between.
PYTHON="$(command -v python3 2>/dev/null || command -v python)"
export PYTHON

RUN_DIR="$PDS_REPO/cases/runs/$(basename "$CASE_DIR")"
# A leftover instances/ dir from a previous run of this case makes muscle_manager fail with
# "Instance already has a directory", so start from a clean run dir each time.
rm -rf "$RUN_DIR"
mkdir -p "$RUN_DIR"
export RUN_DIR

stack=()
for f in workflow.ymmsl workflow_settings.ymmsl scenario_settings.ymmsl preprocess_settings.ymmsl; do
  [[ -f "$CASE_DIR/$f" ]] && stack+=("$CASE_DIR/$f")
done

[[ -f "$CASE_DIR/env.sh" ]] && source "$CASE_DIR/env.sh"

"$MANAGER" --start-all --run-dir "$RUN_DIR" "${stack[@]}" "${OVERLAYS[@]}"

POSTPROCESS="$CASE_DIR/postprocess.sh"
if [[ -x "$POSTPROCESS" ]]; then
  [[ -f "$CASE_DIR/case.env" ]] && source "$CASE_DIR/case.env"
  export SHOT
  "$POSTPROCESS"
fi
