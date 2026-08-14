#!/bin/bash
# Bamboo CI script to install pds and run all tests
# Note: this script should be run from the root of the git repository

# Debuggging:
set -e -o pipefail

set -x

source "$(dirname "${BASH_SOURCE[0]}")/../setup_files/ensure_uv.sh"

# SETUP
source /etc/profile.d/modules.sh
module purge

bash setup_files/setup_test_files.sh

module use "/home/ITER/blokhus/public/modules/all"
module --ignore_cache load PDS

# RUN TEST FILES
muscle_manager --start-all ymmsl_files/test_sink_source_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_accumulator_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_olc_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_waveform_editor.ymmsl
muscle_manager --start-all ymmsl_files/test_torax_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_nice_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_metis_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_chease_actor.ymmsl

# RUN WORKFLOWS
export HDF5_USE_FILE_LOCKING=FALSE  # avoid spurious HDF5 locking failures on networked storage

run_workflow_clean() {
  local workflow="$1" scenario="$2"
  shift 2
  rm -rf "workflows/$workflow/scenarios/$scenario/tmp"
  bash run_workflow.sh "$workflow" "$scenario" "$@"
}

# prescribed_transport and inverse_convergence no longer have a legacy scenarios/
# directory: they are driven by cases/ instead, and both were verified bit-exact against
# the pre-migration definitions before that layer was removed. They need a prepared
# pds-scenarios checkout, so they are skipped when SCENARIOS_REPO is not set.
#
# They also need a PATCHED muscle_manager: the cases name ${PDS_REPO}/${SCENARIOS_REPO} and
# stock muscle3 passes setting values through verbatim (see ci/patches/). CI now loads a
# prebuilt shared PDS-IMAS-MUSCLE3 rather than building into run/, and
# setup_files/apply_patches.sh refuses to modify a read-only shared install -- so check
# rather than run something that would fail confusingly.
MANAGER_PY="$(dirname "$MANAGER")/python"
if [[ ! -d "${SCENARIOS_REPO:-}/105084/data/in" ]]; then
  echo "SKIP: cases/105084_* need SCENARIOS_REPO pointing at a prepared pds-scenarios" >&2
elif ! "$MANAGER_PY" -c 'import muscle3,os,sys; sys.exit(0 if "expand_settings" in open(os.path.join(os.path.dirname(muscle3.__file__),"muscle_manager.py")).read() else 1)' 2>/dev/null; then
  echo "SKIP: cases/105084_* need a patched muscle_manager (ci/patches/); $MANAGER is stock" >&2
else
  "$MANAGER" --start-all cases/105084_prescribed.ymmsl
  "$MANAGER" --start-all cases/105084_convergence.ymmsl
fi

run_workflow_clean evolutive_controller 105084
run_workflow_clean metis_interpretative_from_dina 105084 N_TIMESLICES=10
run_workflow_clean metis_predictive_from_dina 105084 N_TIMESLICES=10

# TODO: metis_interpretative_nice_inverse_from_dina /
# metis_predictive_nice_inverse_from_dina -- need `tmp/PSI_OFFSET`
# run_workflow_clean metis_interpretative_nice_inverse_from_dina 105084 N_TIMESLICES=10
# run_workflow_clean metis_predictive_nice_inverse_from_dina 105084 N_TIMESLICES=10
