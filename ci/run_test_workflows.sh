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

run_workflow_clean prescribed_transport 105084
run_workflow_clean inverse_convergence 105084
run_workflow_clean evolutive_controller 105084
run_workflow_clean metis_interpretative_from_dina 105084 N_TIMESLICES=10
run_workflow_clean metis_predictive_from_dina 105084 N_TIMESLICES=10

# TODO: metis_interpretative_nice_inverse_from_dina /
# metis_predictive_nice_inverse_from_dina -- need `tmp/PSI_OFFSET`
# run_workflow_clean metis_interpretative_nice_inverse_from_dina 105084 N_TIMESLICES=10
# run_workflow_clean metis_predictive_nice_inverse_from_dina 105084 N_TIMESLICES=10
