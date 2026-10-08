#!/bin/bash
# Builds plasmaless_controller's initial state (the F_INIT equilibrium + pf_active of
# magnetic_controller and plasmaless) once, at case creation, instead of inside every run.
# It replaces the former in-workflow chain source (nice_out) -> waveform_editor, making
# the same calls (preprocess_initial_state.py) with this directory's waveforms.yaml. Run
# once by bin/pds-create-case, output frozen into $CASE_DIR/preprocess/ (not rebuilt on
# every bin/pds-run-case.sbatch). See that script's header for the PDS_REPO/
# SCENARIOS_REPO/SHOT/CASE_DIR contract.
#
# source.source_uri in settings.ymmsl -> ${CASE_DIR}/preprocess/initial_state
#
# Inputs: the NICE inverse output (nice_out) of a completed metis_nice_inverse_from_dina
# run for this shot, and the source window (source.t_min/t_max) from this case's own
# workflow_settings.ymmsl + scenario_settings.ymmsl (already written into $CASE_DIR by
# bin/pds-create-case when this runs), so the window is defined in one place only.
set -euo pipefail

WF_DIR="$PDS_REPO/workflows/plasmaless_controller"
NICE_OUT="$PDS_REPO/cases/runs/metis_nice_inverse_from_dina_${SHOT}/nice_out"
OUT="$CASE_DIR/preprocess"
mkdir -p "$OUT"

[[ -d "$NICE_OUT" ]] || {
  echo "plasmaless_controller/preprocess.sh: no NICE inverse output $NICE_OUT" \
       "(run metis_nice_inverse_from_dina for shot $SHOT first)" >&2
  exit 1
}

# Frozen copy of the waveform file, its ${SCENARIOS_REPO}/${SHOT} placeholders resolved
# (machine description from pds-scenarios ${SHOT}/data/in_md), kept for provenance.
envsubst '${PDS_REPO} ${SCENARIOS_REPO} ${SHOT} ${CASE_DIR}' \
  < "$WF_DIR/waveforms.yaml" > "$OUT/waveforms.yaml"

# Same module as the waveform_editor program in workflows/lib/easybuild_programs.ymmsl
# (base_env: clean there, hence the purge). If PDS got loaded as an actual module
# (bin/pds-create-case's own auto-load, or the caller's shell), Lmod adopted PDS_REPO via
# its setenv and purge unwinds that -- reassert it after.
_PDS_REPO="$PDS_REPO"
module purge
module load Waveform-Editor/0.3.2.dev154-intel-2025b-pds
export PDS_REPO="$_PDS_REPO"

python -u "$WF_DIR/preprocess_initial_state.py" \
  --source-uri "imas:hdf5?path=$NICE_OUT" \
  --waveforms "$OUT/waveforms.yaml" \
  --out "$OUT/initial_state" \
  "$CASE_DIR/workflow_settings.ymmsl" "$CASE_DIR/scenario_settings.ymmsl"
