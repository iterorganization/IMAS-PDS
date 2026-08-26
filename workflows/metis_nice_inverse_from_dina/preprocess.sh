#!/bin/bash
# Builds both METIS's own input dataset and NICE's DINA-derived machine-description input
# from this shot's raw DINA source. Ported from the old
# metis_interpretative_nice_inverse_from_dina/preprocess_data.sh -- run once by
# bin/pds-create-case, output frozen into $CASE_DIR/preprocess/. See that script's header for
# the PDS_REPO/SCENARIOS_REPO/SHOT/CASE_DIR contract.
#
# source_metis.source_uri -> ${CASE_DIR}/preprocess/metis_in
# source_nice.source_uri  -> ${CASE_DIR}/preprocess/dina_in
# metis.metis_psioffset in settings.ymmsl defaults to a fixed 9.0; if this run's own DINA
# equilibrium yields a real value (init_metis_from_dina_ids.m computes and writes
# $OUT/PSI_OFFSET as a side effect of the MATLAB build below), that overrides it via
# $CASE_DIR/preprocess_settings.ymmsl, stacked in by bin/pds-run-case.sbatch -- this is where
# it actually matters, since NICE's inverse solve is what psi_LCFS constrains.
set -euo pipefail

# SOURCE_URI/SUMMARY_URI/MD_*/N_TIMESLICES (raw DINA + standard machine description).
# source.env is written to be sourced by pds-scenarios' own tools/prepare, which sets $TOOLS
# first (its own tools/ dir, for MD_IRON_CORE) -- replicate that here rather than pulling in
# tools/prepare itself. IMAS_VERSION comes from the PDS module already loaded.
export TOOLS="$SCENARIOS_REPO/tools"
source "$SCENARIOS_REPO/$SHOT/source.env"

OUT="$CASE_DIR/preprocess"
mkdir -p "$OUT"

export IMAS_AL_DISABLE_VALIDATE=1

python "$PDS_REPO/workflows/utils/convert_dina_data_to_input.py" \
  --source_uri "$SOURCE_URI" \
  --summary_uri "${SUMMARY_URI:-$SOURCE_URI}" \
  --md_pf_active_uri "$MD_PF_ACTIVE" \
  --md_pf_passive_uri "$MD_PF_PASSIVE" \
  --md_wall_uri "$MD_WALL" \
  --md_iron_core_uri "$MD_IRON_CORE" \
  --sink_uri "imas:hdf5?path=$OUT/dina_in" \
  --n_timeslices "${N_TIMESLICES:-51}"

imas convert "$SOURCE_URI" "$IMAS_VERSION" "imas:hdf5?path=$OUT/dina_update_in"

# IMAS-AL-Matlab has no intel-2025b build, so it can't coexist with the intel-2025b
# IMAS-Python stack `module load PDS` already loaded -- purge and reload fresh for this step.
# If PDS got loaded as an actual module (bin/pds-create-case's own auto-load, or the caller's
# shell), Lmod adopted PDS_REPO via its setenv and purge unwinds that -- reassert it after.
_PDS_REPO="$PDS_REPO"
module purge
module load METIS-IRFM/2026.08-pds IMAS-AL-Matlab/5.4.0-intel-2023b-DD-4.0.0
export PDS_REPO="$_PDS_REPO"

export metis_dina_source="imas:hdf5?path=$OUT/dina_update_in"
export metis_imas_dataset="imas:hdf5?path=$OUT/metis_in"
matlab -batch "[s,t] = unix('which python');pyenv('Version',strtrim(t),'ExecutionMode','InProcess'); addpath('$PDS_REPO/workflows/metis_nice_utils');cd('$OUT');make_metis_from_dina_interpretative;"

if [[ -f "$OUT/PSI_OFFSET" ]]; then
  source "$OUT/PSI_OFFSET"
  printf 'ymmsl_version: v0.2\nsettings:\n  metis.metis_psioffset: %s\n' "$PSI_OFFSET" \
    > "$CASE_DIR/preprocess_settings.ymmsl"
fi
