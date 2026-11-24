#!/bin/bash
# Validation plots: reference vs NICE output for R, Z, Ip, PF coil current, plus NICE and
# TORAX profiles, each against its own psi grid. Run by
# bin/pds-run-case.sbatch after muscle_manager finishes -- see that script's header for the
# PDS_REPO/SHOT/CASE_DIR/RUN_DIR/PYTHON contract.
#
# reconstruction_path mirrors settings.ymmsl's source.source_uri (the inverse_convergence run
# this case's F_INIT reference equilibrium is read from).
#
# Options, e.g. when re-running this script by hand from a run directory (--max_slices and
# --interactive apply to the time-slider figures of both plotting scripts, --compare to the
# gyrokinetics plots):
#   --max_slices N        number of evenly spaced times on the time slider (default: 3);
#                         each run's first, middle and last time slice are always shown
#   --interactive         open a matplotlib window with the slider instead of writing the HTML
#   --compare CASE ...    also plot these cases, overlaid on this run. Each CASE is a case
#                         name (e.g. evolutive_controller_105073_evolcur_psigeo), a case
#                         directory (cases/<case>), or a run directory (cases/runs/<run>);
#                         a case means its latest run. Can be repeated.
# Each run's NICE equilibrium (out_nice, if present) is overlaid on its TORAX output
# (out_torax), dotted.
#
# Plots go to $RUN_DIR/plots. RUN_DIR is taken from the environment when set (as
# bin/pds-run-case.sbatch does), otherwise it is the directory this script is in.
set -euo pipefail # stop if anything doesn't work

# Run directory (with out_torax) for a case name, case directory or run directory
resolve_run() {
  local arg=$1 name runs candidates
  if [[ -d "$arg/out_torax" ]]; then
    realpath "$arg"
    return
  fi
  name=$(basename "$arg")
  runs=$PDS_REPO/cases/runs
  # cases/runs/<case> is a symlink to the latest run, or a directory holding the case's runs
  if [[ -d "$runs/$name/out_torax" ]]; then
    realpath "$runs/$name"
    return
  fi
  local stamp="[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9]"
  candidates=$(
    for d in "$runs/${name}_"$stamp "$runs/$name/${name}_"$stamp; do
      [[ -d "$d/out_torax" ]] && echo "$(basename "$d") $d"
    done | sort | tail -n 1 | cut -d' ' -f2-
  )  # latest by the timestamp in the run name
  if [[ -z "$candidates" ]]; then
    echo "postprocess.sh: no run with out_torax found for '$arg'" >&2
    return 1
  fi
  realpath "$candidates"
}

MAX_SLICES=3
INTERACTIVE=()
COMPARE_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --max_slices) MAX_SLICES="$2"; shift 2 ;;
    --max_slices=*) MAX_SLICES="${1#*=}"; shift ;;
    --interactive) INTERACTIVE=(--interactive); shift ;;
    --compare=*) COMPARE_ARGS+=("${1#*=}"); shift ;;
    --compare)
      shift
      [[ $# -gt 0 && "$1" != --* ]] || { echo "postprocess.sh: --compare needs at least one case" >&2; exit 1; }
      while [[ $# -gt 0 && "$1" != --* ]]; do COMPARE_ARGS+=("$1"); shift; done
      ;;
    *) echo "postprocess.sh: unknown option $1 (use --max_slices N, --interactive, --compare CASE ...)" >&2; exit 1 ;;
  esac
done

COMPARE_RUNS=()
for arg in "${COMPARE_ARGS[@]}"; do
  run=$(resolve_run "$arg")
  echo "Comparing with $run"
  COMPARE_RUNS+=("$run")
done

# Reconstruct which case matches this run
RUN_DIR=${RUN_DIR:-$( cd "$( echo "${BASH_SOURCE[0]%/*}" )"; pwd )}
export RUN_DIR
CASE_ROOT=$(basename ${RUN_DIR%_[[:digit:]]*_[[:digit:]]*})
CASE_DIR=$PDS_REPO/cases/$CASE_ROOT
pushd $CASE_DIR
source case.env
popd

# Set runtime variables
PYTHON=${PYTHON:-python}

mkdir -p "$RUN_DIR/plots"

"$PYTHON" "$PDS_REPO/postprocessing/evolutive_controller/plot_validation_evolutive_controller.py" \
  --shot_nr "$SHOT" \
  --reconstruction_path "$RUN_DIR/out_nice" \
  --run_path "$RUN_DIR" \
  --output_dir "$RUN_DIR/plots" \
  --max_slices "$MAX_SLICES" \
  "${INTERACTIVE[@]}"

"$PYTHON" "$PDS_REPO/postprocessing/evolutive_controller/plot_gyrokinetics.py" \
  --shot_nr "$SHOT" \
  --run_path "$RUN_DIR" "${COMPARE_RUNS[@]}" \
  --output_dir "$RUN_DIR/plots" \
  --max_slices "$MAX_SLICES" \
  "${INTERACTIVE[@]}"
