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

# --ignore_cache: Lmod's module cache doesn't necessarily know about a path
# added via `module use` at runtime (especially on a CI agent that's never
# seen this path before), and reports it as "unknown" otherwise.
module use "/home/ITER/blokhus/public/modules"
module --ignore_cache load PDS

# RUN TEST FILES
# Isolated, single-actor smoke tests -- faster than the full workflow runs
# below, and catch a broken actor environment in seconds instead of minutes.
MANAGER="$EBROOTIMASMUSCLE3/venv/bin/muscle_manager"

"$MANAGER" --start-all ymmsl_files/test_sink_source_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_accumulator_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_olc_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_waveform_editor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_torax_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_nice_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_metis_actor.ymmsl

# TODO: test_chease_actor -- chease.exe builds and loads cleanly but
# segfaults at runtime (see build_chease.sh). Not yet debugged.
# "$MANAGER" --start-all ymmsl_files/test_chease_actor.ymmsl

# RUN WORKFLOWS
# One scenario per workflow, to confirm module-loading wiring works end to
# end -- not a physics validation suite. Clears stale scenario output first
# so a rerun can't fail on a leftover file from an earlier build.
export HDF5_USE_FILE_LOCKING=FALSE  # avoid spurious HDF5 locking failures on networked storage

run_workflow_clean() {
  local workflow="$1" scenario="$2"
  shift 2
  rm -rf "workflows/$workflow/scenarios/$scenario/tmp"
  bash run_workflow.sh "$workflow" "$scenario" "$@"
}

run_workflow_clean prescribed_transport 105084
run_workflow_clean inverse_convergence 105084
run_workflow_clean metis_interpretative_from_dina 105084 N_TIMESLICES=10
run_workflow_clean metis_predictive_from_dina 105084 N_TIMESLICES=10

# TODO: torax_nice_controller / torax_nice_rd_controller -- not yet migrated
# to the new module-loading design (still bare `modules: NICE` etc.).
# run_workflow_clean torax_nice_controller 105073
# run_workflow_clean torax_nice_rd_controller 105073

# TODO: metis_interpretative_nice_inverse_from_dina /
# metis_predictive_nice_inverse_from_dina -- need `tmp/PSI_OFFSET`, which
# nothing writes. No script computes METIS's psioffset calibration constant
# for the NICE-coupled case (METIS defaults it to 0.0; the plain sibling
# workflow hardcodes 9.0 for its own scenario, unverified here) -- needs real
# METIS/NICE physics input, not a guess. Left out of CI until that exists.
# run_workflow_clean metis_interpretative_nice_inverse_from_dina 105084 N_TIMESLICES=10
# run_workflow_clean metis_predictive_nice_inverse_from_dina 105084 N_TIMESLICES=10
