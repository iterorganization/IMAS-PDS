#!/bin/bash
# Builds both METIS's own input dataset and NICE's DINA-derived machine-description input
# from this shot's raw DINA source. Ported from the old
# metis_interpretative_nice_inverse_from_dina/preprocess_data.sh -- run once by
# bin/pds-create-case, output frozen into $CASE_DIR/preprocess/. See that script's header for
# the PDS_REPO/SHOT/CASE_DIR contract.
#
# source_metis.source_uri -> ${CASE_DIR}/preprocess/metis_in
# source_nice.source_uri  -> ${CASE_DIR}/preprocess/dina_in
# metis.metis_psioffset in settings.ymmsl defaults to a fixed 9.0; if this run's own DINA
# equilibrium yields a real value (init_metis_from_dina_ids.m computes and writes
# $OUT/PSI_OFFSET as a side effect of the MATLAB build below), that overrides it via
# $CASE_DIR/preprocess_settings.ymmsl, stacked in by bin/pds-run-case.sbatch -- this is where
# it actually matters, since NICE's inverse solve is what psi_LCFS constrains.
set -euo pipefail

# SOURCE_URI (raw DINA) for METIS. IMAS_VERSION comes from the PDS module already loaded.
source "$PDS_REPO/preprocessing/dina/shots/$SHOT.env"

OUT="$CASE_DIR/preprocess"
mkdir -p "$OUT"

export IMAS_AL_DISABLE_VALIDATE=1

"$PDS_REPO/preprocessing/dina/scenario_input.sh" "$OUT/dina_in"

imas convert "$SOURCE_URI" "$IMAS_VERSION" "imas:hdf5?path=$OUT/dina_update_in"

# IMAS-AL-Matlab has no intel-2025b build, so it can't coexist with the intel-2025b
# IMAS-Python stack `module load PDS` already loaded -- purge and reload fresh for this step.
# If PDS got loaded as an actual module (bin/pds-create-case's own auto-load, or the caller's
# shell), Lmod adopted PDS_REPO via its setenv and purge unwinds that -- reassert it after.
#
# --ignore_cache: the CI user's Lmod spider cache can predate a recent METIS-IRFM/MATLAB
# rebuild, in which case depends_on() can't find a MATLAB family member to resolve
# METIS-IRFM's dependency on and the load hard-fails (set -e kills the script here).
_PDS_REPO="$PDS_REPO"
module purge
module --ignore_cache load METIS-IRFM/2026.08-pds IMAS-AL-Matlab/5.4.0-intel-2023b-DD-4.0.0
export PDS_REPO="$_PDS_REPO"

export metis_dina_source="imas:hdf5?path=$OUT/dina_update_in"
export metis_imas_dataset="imas:hdf5?path=$OUT/metis_in"
matlab -batch "[s,t] = unix('which python');pyenv('Version',strtrim(t),'ExecutionMode','InProcess'); addpath('$PDS_REPO/preprocessing/metis');cd('$OUT');make_metis_from_dina_interpretative;"

if [[ -f "$OUT/PSI_OFFSET" ]]; then
  source "$OUT/PSI_OFFSET"
  printf 'ymmsl_version: v0.2\nsettings:\n  metis.metis_psioffset: %s\n' "$PSI_OFFSET" \
    > "$CASE_DIR/preprocess_settings.ymmsl"
fi
