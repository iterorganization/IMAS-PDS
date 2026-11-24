#!/bin/bash
# Postprocessing plots for an evolutive_controller run, written to $RUN_DIR/plots:
#   - validation (plot_validation_evolutive_controller.py): reference vs NICE output for
#     R, Z, Ip and PF coil currents, plus NICE and TORAX profiles vs psi_norm;
#   - gyrokinetics (plot_gyrokinetics.py): TORAX profiles relevant for gyrokinetics,
#     with each run's NICE equilibrium (out_nice, if present) overlaid dotted.
# The profile plots have a time slider: a PNG per slider time plus a scrollable HTML page.
#
# Run by bin/pds-run-case.sbatch after muscle_manager finishes -- see that script's header
# for the PDS_REPO/SHOT/CASE_DIR/RUN_DIR/PYTHON contract. RUN_DIR is taken from the
# environment when set, otherwise it is the directory this script is in, so it can be
# re-run by hand from a run directory:
#
#   cases/runs/<run>/postprocess.sh [--max_slices N] [--interactive] [--compare CASE ...]
#
#   --max_slices N      number of evenly spaced times on the time sliders (default: 3);
#                       each run's first, middle and last time slice are always shown
#   --interactive       open matplotlib windows instead of writing the plots
#   --compare CASE ...  overlay these cases on this run in the gyrokinetics plots. Each
#                       CASE is a case name (e.g. evolutive_controller_105073_evolcur_psigeo),
#                       a case directory (cases/<case>) or a run directory
#                       (cases/runs/<run>); a case means its latest run. Can be repeated.
#
# The validation plots' reconstruction_path mirrors settings.ymmsl's source.source_uri
# (the inverse_convergence run this case's F_INIT reference equilibrium is read from).
set -euo pipefail # stop if anything doesn't work
: "${PDS_REPO:?must point at the IMAS-PDS checkout}"

die() {
  echo "postprocess.sh: $*" >&2
  exit 1
}

# Run directories are named <case>_<YYYYMMDD>_<HHMMSS> (same convention as case_dir() in
# plot_validation_evolutive_controller.py)
STAMP_GLOB="[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9]"
STAMP_REGEX="_[0-9]{8}_[0-9]{6}$"

# Case name of a run directory: its name without the timestamp
case_name() {
  local name
  name=$(basename "$1")
  if [[ $name =~ $STAMP_REGEX ]]; then
    name=${name%"${BASH_REMATCH[0]}"}
  fi
  echo "$name"
}

# Run directory (one with out_torax) for a case name, case directory or run directory
resolve_run() {
  local arg=$1 name runs latest
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
  # Otherwise the latest of cases/runs/[<case>/]<case>_<date>_<time>, by that timestamp
  latest=$(
    for dir in "$runs/${name}_"$STAMP_GLOB "$runs/$name/${name}_"$STAMP_GLOB; do
      [[ -d "$dir/out_torax" ]] && echo "$(basename "$dir") $dir"
    done | sort | tail -n 1 | cut -d' ' -f2-
  )
  [[ -n "$latest" ]] || die "no run with out_torax found for '$arg'"
  realpath "$latest"
}

# ---- Options
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
      [[ $# -gt 0 && "$1" != --* ]] || die "--compare needs at least one case"
      while [[ $# -gt 0 && "$1" != --* ]]; do COMPARE_ARGS+=("$1"); shift; done
      ;;
    *) die "unknown option $1 (use --max_slices N, --interactive, --compare CASE ...)" ;;
  esac
done

COMPARE_RUNS=()
for arg in "${COMPARE_ARGS[@]}"; do
  run=$(resolve_run "$arg")
  echo "Comparing with $run"
  COMPARE_RUNS+=("$run")
done

# ---- This run and its case
RUN_DIR=${RUN_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
export RUN_DIR
CASE_DIR=$PDS_REPO/cases/$(case_name "$RUN_DIR")
pushd "$CASE_DIR" >/dev/null
source case.env # sets SHOT
popd >/dev/null

PYTHON=${PYTHON:-python}
SCRIPTS=$PDS_REPO/postprocessing/evolutive_controller
SLIDER_ARGS=(--output_dir "$RUN_DIR/plots" --max_slices "$MAX_SLICES" "${INTERACTIVE[@]}")

# ---- Plots
"$PYTHON" "$SCRIPTS/plot_validation_evolutive_controller.py" \
  --shot_nr "$SHOT" \
  --run_path "$RUN_DIR" \
  --reconstruction_path "$RUN_DIR/out_nice" \
  "${SLIDER_ARGS[@]}"

"$PYTHON" "$SCRIPTS/plot_gyrokinetics.py" \
  --shot_nr "$SHOT" \
  --run_path "$RUN_DIR" "${COMPARE_RUNS[@]}" \
  "${SLIDER_ARGS[@]}"
