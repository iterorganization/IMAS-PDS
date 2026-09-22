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

# --ignore_cache: Lmod's module cache doesn't necessarily know about a path added via
# `module use` at runtime (especially on a CI agent that has never seen this path), and
# reports it as "unknown" otherwise.
module use "/work/projects/pds/modules/all"
module --ignore_cache load PDS

export HDF5_USE_FILE_LOCKING=FALSE  # avoid spurious HDF5 locking failures on networked storage

export SBATCH_PARTITION=sun_debug,vega_debug,sirius_debug
export SLURM_PARTITION=sun_debug,vega_debug,sirius_debug

# Single-actor smoke tests: catch a broken actor environment in seconds. Without an
# explicit --run-dir the manager creates run_<model>_<timestamp> in the CI workspace and
# nothing ever prunes them, so these land in cases/runs/ same as the case runs below.
run_actor_test_clean() {
  local test_name="$1"
  rm -rf "cases/runs/$test_name"
  mkdir -p "cases/runs/$test_name"
  muscle_manager --start-all --run-dir "cases/runs/$test_name" "ymmsl_files/$test_name.ymmsl"
}

run_case_clean() {
  local workflow="$1" shot="$2"
  local case_dir="cases/${workflow}_${shot}"
  bin/pds-create-case "$workflow" "$shot"
  bash bin/pds-run-case.sbatch "$case_dir"
}

# RUN TEST FILES

run_actor_test_clean test_sink_source_actor
run_actor_test_clean test_accumulator_actor
run_actor_test_clean test_olc_actor
run_actor_test_clean test_waveform_editor
run_actor_test_clean test_torax_actor
run_actor_test_clean test_nice_actor
run_actor_test_clean test_metis_actor
run_actor_test_clean test_chease_actor

# RUN WORKFLOWS

run_case_clean prescribed_transport 105099
run_case_clean inverse_convergence 105073
run_case_clean evolutive_controller 105073
run_case_clean metis_from_dina 105084
run_case_clean metis_nice_inverse_from_dina 105084
