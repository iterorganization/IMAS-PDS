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
module use "/home/ITER/blokhus/public/modules/all"
module --ignore_cache load PDS

# RUN TEST FILES
# Single-actor smoke tests: catch a broken actor environment in seconds. Without an
# explicit --run-dir the manager creates run_<model>_<timestamp> in the CI workspace and
# nothing ever prunes them, so these land in cases/runs/ same as the case runs below.
run_actor_test_clean() {
  local test_name="$1"
  rm -rf "cases/runs/$test_name"
  mkdir "cases/runs/$test_name"
  muscle_manager --start-all --run-dir "cases/runs/$test_name" "ymmsl_files/$test_name.ymmsl"
}

run_actor_test_clean test_sink_source_actor
run_actor_test_clean test_accumulator_actor
run_actor_test_clean test_olc_actor
run_actor_test_clean test_waveform_editor
run_actor_test_clean test_torax_actor
run_actor_test_clean test_nice_actor
run_actor_test_clean test_metis_actor
run_actor_test_clean test_chease_actor

# RUN WORKFLOWS
export HDF5_USE_FILE_LOCKING=FALSE  # avoid spurious HDF5 locking failures on networked storage

# Clears the scenario's stale output first, so a rerun cannot fail on a leftover file.
run_workflow_clean() {
  local workflow="$1" scenario="$2"
  shift 2
  rm -rf "workflows/$workflow/scenarios/$scenario/tmp"
  bash run_workflow.sh "$workflow" "$scenario" "$@"
}

# bin/pds-create-case + bin/pds-run-case.sbatch is the same path a real sbatch submission
# would take (module loading, case/run-dir placement) -- use it here too instead of
# duplicating that logic. pds-create-case prints the case dir it wrote; pds-run-case.sbatch
# clears that case's own run/out/<case> dir itself before running, so a rerun cannot fail on
# a leftover instances/ dir.
run_case_clean() {
  local workflow="$1" shot="$2"
  bash bin/pds-run-case.sbatch "$(bin/pds-create-case "$workflow" "$shot")"
}

# 105073 has a validated cases/overrides/ pair for inverse_convergence + evolutive_controller
# (the latter needs the former's out_nice for the same shot, so run inverse_convergence
# first); prescribed_transport needs a shot with a separate data/in_md (105073 is
# MD_LAYOUT=combined -- see workflows/prescribed_transport/README.md's scenario list).
run_case_clean prescribed_transport 105099
run_case_clean inverse_convergence 105073
run_case_clean evolutive_controller 105073

# TODO: metis workflows aren't migrated to bin/pds-create-case/bin/pds-run-case.sbatch yet
# (still workflow.ymmsl.template + create_runnable_files.sh/run_simulation.sh); re-add a
# metis case here once that migration happens.

# run_workflow_clean metis_interpretative_from_dina 105084 N_TIMESLICES=10
# run_workflow_clean metis_predictive_from_dina 105084 N_TIMESLICES=10

# TODO: metis_{interpretative,predictive}_nice_inverse_from_dina -- need `tmp/PSI_OFFSET`,
# which nothing writes. METIS's psioffset calibration constant for the NICE-coupled case
# needs real physics input, so these stay out of CI until it exists.
# run_workflow_clean metis_interpretative_nice_inverse_from_dina 105084 N_TIMESLICES=10
# run_workflow_clean metis_predictive_nice_inverse_from_dina 105084 N_TIMESLICES=10
