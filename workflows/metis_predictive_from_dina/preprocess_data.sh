set -euo pipefail # stop if anything doesn't work

module load IMAS-Python
module load IDStools/2.3.0
module load IMAS-AL-Matlab

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
