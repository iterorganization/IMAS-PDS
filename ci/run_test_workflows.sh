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
bash ../setup_files/setup_waveform_editor.sh
bash ../setup_files/setup_muscle3.sh
bash ../setup_files/setup_nice.sh
# setup_torax.sh defaults to the main branch; CI tests develop.
bash ../setup_files/setup_torax.sh "https://github.com/iterorganization/TORAX-MUSCLE3.git" develop
bash ../setup_files/setup_imas_muscle3.sh
# imas-validator 1.0.0 (latest release) is incompatible with imas-python 2.3
# (removed has_imas attribute); the olc actor needs the develop fix.
./IMAS-MUSCLE3/venv/bin/pip install "git+https://github.com/iterorganization/imas-validator.git@develop"
cd ..


# RUN TEST FILES
# All actors run from the repo-local muscle3 0.10 stack (the venvs and the
# source-built NICE binaries set up above), so the manager must be 0.10 too:
# the site MUSCLE3 module (0.8.0) cannot talk to 0.10 actors or vice versa.
MANAGER="$PWD/run/IMAS-MUSCLE3/venv/bin/muscle_manager"

# bash run_test_files.sh
"$MANAGER" --start-all ymmsl_files/test_sink_source_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_accumulator_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_olc_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_waveform_editor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_visualization_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_torax_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_nice_actor.ymmsl
# "$MANAGER" --start-all ymmsl_files/test_metis_actor.ymmsl

# RUN WORKFLOWS
bash run_workflow.sh inverse_convergence 105084

# # WAIT FOR NICE_EVO TO BE PART OF NICE EASYBUILD MODULE. 
# # EXPECT CRASH, HOW TO HANDLE?
# bash run_workflow.sh torax_nice_self_controller 105084
# bash run_workflow.sh torax_nice_self_rd_controller 105084

# # WAIT FOR METIS EASYBUILD MODULE
# bash run_workflow.sh metis_interpretative_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_predictive_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_interpretative_nicne_inverse_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_predictive_nice_inverse_from_dina 105084 N_TIMESLICES=10



