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
# Single-actor smoke tests: catch a broken actor environment in seconds.
muscle_manager --start-all ymmsl_files/test_sink_source_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_accumulator_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_olc_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_waveform_editor.ymmsl
muscle_manager --start-all ymmsl_files/test_torax_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_nice_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_metis_actor.ymmsl
muscle_manager --start-all ymmsl_files/test_chease_actor.ymmsl

# RUN WORKFLOWS
# One scenario per workflow, to confirm the wiring works end to end -- not a physics
# validation suite. Clears stale output so a rerun cannot fail on a leftover file.
export HDF5_USE_FILE_LOCKING=FALSE  # avoid spurious HDF5 locking failures on networked storage

run_workflow_clean() {
  local workflow="$1" scenario="$2"
  shift 2
  rm -rf "workflows/$workflow/scenarios/$scenario/tmp"
  bash run_workflow.sh "$workflow" "$scenario" "$@"
}

# prescribed_transport and inverse_convergence are driven by cases/, which need a prepared
# pds-scenarios checkout -- skipped when SCENARIOS_REPO is unset.
#
# They also need a patched muscle_manager: the cases name ${PDS_REPO}/${SCENARIOS_REPO} and
# stock muscle3 passes setting values through verbatim (see ci/patches/). Checked rather
# than applied, since apply_patches.sh refuses to modify a read-only shared install.
if [[ ! -d "${SCENARIOS_REPO:-}/105084/data/in" ]]; then
  echo "SKIP: cases/105084_* need SCENARIOS_REPO pointing at a prepared pds-scenarios" >&2
elif ! python -c 'import muscle3,os,sys; sys.exit(0 if "expand_settings" in open(os.path.join(os.path.dirname(muscle3.__file__),"muscle_manager.py")).read() else 1)' 2>/dev/null; then
  echo "SKIP: cases/105084_* need a patched muscle_manager (ci/patches/); this one is stock" >&2
else
  muscle_manager --start-all cases/105084_prescribed.ymmsl
  muscle_manager --start-all cases/105084_convergence.ymmsl
fi

run_workflow_clean evolutive_controller 105084
run_workflow_clean metis_interpretative_from_dina 105084 N_TIMESLICES=10
run_workflow_clean metis_predictive_from_dina 105084 N_TIMESLICES=10

# TODO: metis_{interpretative,predictive}_nice_inverse_from_dina -- need `tmp/PSI_OFFSET`,
# which nothing writes. METIS's psioffset calibration constant for the NICE-coupled case
# needs real physics input, so these stay out of CI until it exists.
# run_workflow_clean metis_interpretative_nice_inverse_from_dina 105084 N_TIMESLICES=10
# run_workflow_clean metis_predictive_nice_inverse_from_dina 105084 N_TIMESLICES=10
