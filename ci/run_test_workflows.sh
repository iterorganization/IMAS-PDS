#!/bin/bash
# Bamboo CI script to install pds and run all tests
# Note: this script should be run from the root of the git repository

# Debuggging:
set -e -o pipefail

set -x

# setup
bash pds_setup.sh

bash run_test_files.sh

# not realistic to cover all scenarios

cd scenario_configs/105092_torax_nice
bash automate_runs.sh
cd ../105092_metis_interpretative_nice_inverse_from_dina
bash automate_runs.sh
cd ..

# run self-consistent torax-nice for low number of timeslices
# run self-consistent metis-nice for low number of timeslices
# run magnetic-controller torax-nice for low number of timeslices
# run magnetic-controller metis-nice for low number of timeslices
