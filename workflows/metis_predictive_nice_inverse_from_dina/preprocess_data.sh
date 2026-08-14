set -euo pipefail # stop if anything doesn't work

echo "Inputs:"
echo "SHOT_NR=" $SHOT_NR
echo "SOURCE_URI=" $SOURCE_URI
echo "SINK_URI=" $SINK_URI
echo "SINK_UPDATE_URI=" $SINK_UPDATE_URI
echo "SINK_METIS_URI=" $SINK_METIS_URI
echo "N_TIMESLICES=" $N_TIMESLICES
echo "T_LIST=" "${T_LIST[@]}"

export matlab_path="$PWD/workflows/metis_nice_utils"
export IMAS_AL_DISABLE_VALIDATE=1

SUMMARY_URI=$SOURCE_URI
python $PWD/workflows/utils/convert_dina_data_to_input.py \
  --source_uri $SOURCE_URI \
  --summary_uri $SUMMARY_URI \
  --md_pf_active_uri $MD_PF_ACTIVE \
  --md_pf_passive_uri $MD_PF_PASSIVE \
  --md_wall_uri $MD_WALL \
  --md_iron_core_uri $MD_IRON_CORE \
  --sink_uri $SINK_URI \
  --n_timeslices $N_TIMESLICES

imas convert $SOURCE_URI $IMAS_VERSION $SINK_UPDATE_URI

# make METIS dataset
export metis_dina_source=$SINK_UPDATE_URI
export metis_imas_dataset=$SINK_METIS_URI
echo "$(date +%H):$(date +%M):$(date +%S) Making METIS dataset"
mkdir -p tmp

module purge
module load IMAS-AL-Matlab/5.4.0-intel-2023b-DD-4.0.0
matlab -batch "[s,t] = unix('which python');pyenv('Version',strtrim(t),'ExecutionMode','InProcess'); addpath(getenv('matlab_path'));cd('tmp');make_metis_from_dina_interpretative;"
