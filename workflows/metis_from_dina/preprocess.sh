#!/bin/bash
# Builds METIS's own input dataset from this shot's raw DINA source (METIS's IMAS DD layout
# is workflow-specific, so nothing pre-bakes it into pds-scenarios). Ported from the old
# metis_interpretative_from_dina/preprocess_data.sh + create_runnable_files.sh -- run once by
# bin/pds-create-case, its output frozen into $CASE_DIR/preprocess/ (not rebuilt on every
# bin/pds-run-case.sbatch). See that script's header for the PDS_REPO/SCENARIOS_REPO/SHOT/
# CASE_DIR contract.
#
# source_metis.source_uri in settings.ymmsl points at ${CASE_DIR}/preprocess/metis_in.
# metis.metis_psioffset in settings.ymmsl defaults to a fixed 9.0; if this run's own DINA
# equilibrium yields a real value (init_metis_from_dina_ids.m computes and writes
# $OUT/PSI_OFFSET as a side effect of the MATLAB build below), that overrides it via
# $CASE_DIR/preprocess_settings.ymmsl, stacked in by bin/pds-run-case.sbatch.
set -euo pipefail

# SOURCE_URI (raw DINA). source.env is written to be sourced by pds-scenarios' own
# tools/prepare, which sets $TOOLS first (its own tools/ dir, for MD_IRON_CORE) -- replicate
# that here rather than pulling in tools/prepare itself. IMAS_VERSION comes from the PDS
# module already loaded.
export TOOLS="$SCENARIOS_REPO/tools"
source "$SCENARIOS_REPO/$SHOT/source.env"

OUT="$CASE_DIR/preprocess"
mkdir -p "$OUT"

export IMAS_AL_DISABLE_VALIDATE=1

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
matlab -batch "[s,t] = unix('which python');pyenv('Version',strtrim(t),'ExecutionMode','InProcess'); addpath('$PDS_REPO/workflows/metis_alone_utils');cd('$OUT');make_metis_from_dina_interpretative;"

if [[ -f "$OUT/PSI_OFFSET" ]]; then
  source "$OUT/PSI_OFFSET"
  printf 'ymmsl_version: v0.2\nsettings:\n  metis.metis_psioffset: %s\n' "$PSI_OFFSET" \
    > "$CASE_DIR/preprocess_settings.ymmsl"
fi
