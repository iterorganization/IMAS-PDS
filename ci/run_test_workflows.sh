#!/bin/bash
# Bamboo CI script to install pds and run all tests
# Note: this script should be run from the root of the git repository

# Debuggging:
set -e -o pipefail

set -x

# SETUP
source /etc/profile.d/modules.sh
module purge

# bash pds_setup.sh
bash setup_files/setup_test_files.sh

cd run/
bash ../setup_files/setup_muscle3.sh
bash ../setup_files/setup_imas_muscle3.sh
bash ../setup_files/setup_waveform_editor.sh "https://github.com/iterorganization/Waveform-Editor.git" feature/reference-tendency-old
bash ../setup_files/setup_nice.sh "https://gitlab.inria.fr/blfauger/nice.git" bugfix/rejection_logic
bash ../setup_files/setup_torax.sh
# imas-validator 1.0.0 (latest release) is incompatible with imas-python 2.3
# (removed has_imas attribute); the olc actor needs the develop fix.
./IMAS-MUSCLE3/venv/bin/pip install "git+https://github.com/iterorganization/imas-validator.git@develop"
cd ..


# RUN TEST FILES
# All actorn run on muscle3 0.10 so the manager also needs to run on 0.10.
MANAGER="$PWD/run/IMAS-MUSCLE3/venv/bin/muscle_manager"

# Bamboo wipes the build dir immediately on failure, so a bare exit code tells
# us nothing about *why* an actor died. Dump every instance's stdout/stderr
# into the (retained) Bamboo console log before propagating the failure.
run_manager_test() {
  local status=0
  "$MANAGER" --start-all "$1" || status=$?
  if [[ $status -ne 0 ]]; then
    local latest
    latest="$(ls -td run_test_*/ 2>/dev/null | head -1)"
    if [[ -n "$latest" ]]; then
      echo "===== $1 failed -- dumping instance logs from $latest ====="
      for inst_dir in "$latest"instances/*/; do
        echo "--- ${inst_dir}stdout.txt ---"
        cat "${inst_dir}stdout.txt" 2>/dev/null
        echo "--- ${inst_dir}stderr.txt ---"
        cat "${inst_dir}stderr.txt" 2>/dev/null
      done
    fi
  fi
  return "$status"
}

# bash run_test_files.sh
run_manager_test ymmsl_files/test_sink_source_actor.ymmsl
run_manager_test ymmsl_files/test_accumulator_actor.ymmsl
run_manager_test ymmsl_files/test_olc_actor.ymmsl
run_manager_test ymmsl_files/test_waveform_editor.ymmsl
run_manager_test ymmsl_files/test_visualization_actor.ymmsl
run_manager_test ymmsl_files/test_torax_actor.ymmsl
run_manager_test ymmsl_files/test_nice_actor.ymmsl
# run_manager_test ymmsl_files/test_metis_actor.ymmsl

# RUN WORKFLOWS
bash run_workflow.sh prescribed_transport 105084
bash run_workflow.sh inverse_convergence 105084
# # EXPECT CRASH, HOW TO HANDLE?
# bash run_workflow.sh  torax_nice_self_rd_controller 105084

# # WAIT FOR METIS EASYBUILD MODULE
# bash run_workflow.sh metis_interpretative_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_predictive_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_interpretative_nicne_inverse_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_predictive_nice_inverse_from_dina 105084 N_TIMESLICES=10



