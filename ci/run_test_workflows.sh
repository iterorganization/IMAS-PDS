#!/bin/bash
# Bamboo CI script to install pds and run all tests
# Note: this script should be run from the root of the git repository

# Debuggging:
set -e -o pipefail

set -x

# setup
# bash pds_setup.sh

# bash run_test_files.sh

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

bash run_workflow.sh torax_nice_self_consistent_transport 105084

# # not realistic to cover all scenarios
# run self-consistent torax-nice for low number of timeslices
# run self-consistent metis-nice for low number of timeslices
# run magnetic-controller torax-nice for low number of timeslices
# run magnetic-controller metis-nice for low number of timeslices
