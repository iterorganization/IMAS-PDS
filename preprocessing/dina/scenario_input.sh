#!/bin/bash
# Builds a workflow's PDS input from the shot's DINA run (preprocessing/dina/shots/<shot>.env)
# and the ITER machine description (preprocessing/machine_description/iter.env):
#
#   scenario_input.sh <out-dir> [md-out-dir] [n_timeslices]
#
# <out-dir> gets equilibrium, core_profiles, core_sources and the DINA coil currents at
# n_timeslices (default 41) timeslices. The machine description goes into <md-out-dir>, or
# into <out-dir> itself if that is omitted or the shot sets MD_LAYOUT=combined. Needs PDS_REPO
# and SHOT, as set for preprocess.sh.
set -euo pipefail

OUT="$1"
MD_OUT="${2:-}"

# Variant shots (e.g. 105084_literal) use their base shot's source.
SHOT_ENV="$PDS_REPO/preprocessing/dina/shots/$SHOT.env"
[[ -f "$SHOT_ENV" ]] || SHOT_ENV="$PDS_REPO/preprocessing/dina/shots/${SHOT%%_*}.env"
source "$SHOT_ENV"
source "$PDS_REPO/preprocessing/machine_description/iter.env"
if [[ "${MD_LAYOUT:-separate}" == combined ]]; then
  MD_OUT=""
fi

export PYTHONPATH="$PDS_REPO${PYTHONPATH:+:$PYTHONPATH}"
export IMAS_LOGLEVEL="${IMAS_LOGLEVEL:-WARNING}"
export HDF5_USE_FILE_LOCKING=FALSE

# The converter appends, so start from empty.
rm -rf "$OUT" ${MD_OUT:+"$MD_OUT"}
mkdir -p "$OUT" ${MD_OUT:+"$MD_OUT"}
python "$PDS_REPO/preprocessing/dina/convert_dina_data_to_input.py" \
  --source_uri "$SOURCE_URI" \
  --summary_uri "$SOURCE_URI" \
  --md_pf_active_uri "$MD_PF_ACTIVE" \
  --md_pf_passive_uri "$MD_PF_PASSIVE" \
  --md_wall_uri "$MD_WALL" \
  --sink_uri "imas:hdf5?path=$OUT" \
  ${MD_OUT:+--md_sink_uri "imas:hdf5?path=$MD_OUT"} \
  --n_timeslices "${3:-41}"

# Opening an entry, even read-only, rewrites its master.h5 unless the file is read-only, and
# several actors of one run read these entries at once, racing on that write.
chmod a-w "$OUT"/*.h5 ${MD_OUT:+"$MD_OUT"/*.h5}
