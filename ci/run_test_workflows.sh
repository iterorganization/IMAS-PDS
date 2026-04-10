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
mkdir TORAX-MUSCLE3
cd TORAX-MUSCLE3
module load Python
python -m venv ./venv
source ./venv/bin/activate
pip install --upgrade pip setuptools
pip install torax-muscle3 "muscle3==0.8.0"
deactivate
module purge
cd ../..


# RUN TEST FILES
module load MUSCLE3

# bash run_test_files.sh
muscle_manager --start-all ymmsl_files/test_sink_source_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_accumulator_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_olc_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_waveform_editor.ymmsl
muscle_manager --start-all ymmsl_files/test_visualization_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_torax_actor.ymmsl
# muscle_manager --start-all ymmsl_files/test_metis_actor.ymmsl
# muscle_manager --start-all ymmsl_files/test_nice_actor.ymmsl

# RUN WORKFLOWS
bash run_workflow.sh torax_nice_self_consistent_transport 105084 RERUN_N_TIMES=1 N_TIMESLICES=10

# # WAIT FOR NICE_EVO TO BE PART OF NICE EASYBUILD MODULE. 
# # EXPECT CRASH, HOW TO HANDLE?
# bash run_workflow.sh torax_nice_self_controller 105084
# bash run_workflow.sh torax_nice_self_rd_controller 105084

# # WAIT FOR METIS EASYBUILD MODULE
# bash run_workflow.sh metis_interpretative_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_predictive_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_interpretative_nicne_inverse_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_predictive_nice_inverse_from_dina 105084 N_TIMESLICES=10



