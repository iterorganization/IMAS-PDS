set -euo pipefail # stop if anything doesn't work

T_LIST=("$@")

echo "Inputs:"
echo "SHOT_NR=" $SHOT_NR
echo "SOURCE_URI=" $SOURCE_URI
echo "SINK_URI=" $SINK_URI
echo "SINK_UPDATE_URI=" $SINK_UPDATE_URI
echo "SINK_METIS_URI=" $SINK_METIS_URI
echo "N_TIMESLICES=" $N_TIMESLICES
echo "T_LIST=" "${T_LIST[@]}"

export matlab_path="$PWD/workflows/metis_alone_utils"
export IMAS_AL_DISABLE_VALIDATE=1 

imas convert $SOURCE_URI $IMAS_VERSION $SINK_UPDATE_URI

# make METIS dataset
export metis_dina_source=$SINK_UPDATE_URI
export metis_imas_dataset=$SINK_METIS_URI
echo "$(date +%H):$(date +%M):$(date +%S) Making METIS dataset"
mkdir -p tmp

# IMAS-AL-Matlab has no intel-2025b build, so it can't coexist with the
# intel-2025b IMAS-Python stack `module load PDS` already loaded -- purge
# and reload fresh for this MATLAB step.
#
# Tried IMAS-MATLAB/5.6.0-intel-2025b-DD-4.1.1 instead, for toolchain
# consistency -- reverted: no DD-4.0.0 build, and the DD bump broke METIS's
# own "Unknown IDS name: dataset_description" lookup.
module purge
module load METIS-IRFM/2026.08-pds IMAS-AL-Matlab/5.4.0-intel-2023b-DD-4.0.0
matlab -batch "[s,t] = unix('which python');pyenv('Version',strtrim(t),'ExecutionMode','InProcess'); addpath(getenv('matlab_path'));cd('tmp');make_metis_from_dina_interpretative;"
