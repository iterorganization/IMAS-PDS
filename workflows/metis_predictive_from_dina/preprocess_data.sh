set -euo pipefail # stop if anything doesn't work

# NOTE: IMAS-AL-Matlab has no 2025b build at all yet (newest is
# 5.4.0-intel-2023b-DD-4.0.0) -- this workflow's Matlab IDS access is an
# unresolved gap, not something PDS.lua/module load PDS currently covers
# (ci/run_test_workflows.sh already treats METIS *_from_dina workflows as
# blocked pending a proper module, see its "WAIT FOR METIS EASYBUILD MODULE"
# comment).

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
matlab -batch "[s,t] = unix('which python');pyenv('Version',strtrim(t),'ExecutionMode','InProcess'); addpath(getenv('matlab_path'));cd('tmp');make_metis_from_dina_interpretative;"
