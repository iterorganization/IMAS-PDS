#!/bin/bash
# Bamboo CI script to install pds and run all tests
# Note: this script should be run from the root of the git repository

# Debuggging:
set -e -o pipefail

set -x

# setup
# bash pds_setup.sh

# bash run_test_files.sh

source /etc/profile.d/modules.sh
cd run/
mkdir TORAX-MUSCLE3
cd TORAX-MUSCLE3
module load Python
python -m venv ./venv
source ./venv/bin/activate
pip install torax-muscle3
deactivate
module purge
cd ../..

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
