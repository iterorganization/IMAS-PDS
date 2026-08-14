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

# IMAS-AL-Matlab has no intel-2025b build (only 5.4.0-intel-2023b-DD-4.0.0),
# so it can't coexist in the same shell as the intel-2025b IMAS-Python/
# IMAS-Core/UDA stack `module load PDS` already loaded above for `imas
# convert` -- purge first, then load it fresh, isolating this MATLAB step
# the same way a `base_env: clean` MUSCLE3 actor would. Confirmed
# empirically: `module purge; module load IMAS-AL-Matlab` from an
# already-PDS-loaded shell puts a working matlab on PATH with no conflicts.
#
# Tried switching to IMAS-MATLAB/5.6.0-intel-2025b-DD-4.1.1 (the 2025b-
# native rename) for toolchain consistency -- reverted: it has no DD-4.0.0
# build (only DD-4.1.0/4.1.1/3.42.2), and the DD bump broke METIS's own
# code with "Unknown IDS name: dataset_description" (confirmed via a real
# run). Not worth chasing since the original mixing issue this comment
# describes is already fully handled below regardless.
module purge
module load IMAS-AL-Matlab/5.4.0-intel-2023b-DD-4.0.0
matlab -batch "[s,t] = unix('which python');pyenv('Version',strtrim(t),'ExecutionMode','InProcess'); addpath(getenv('matlab_path'));cd('tmp');make_metis_from_dina_interpretative;"
