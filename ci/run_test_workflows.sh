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

# Run a job script on Slurm and block until it ends. sbatch --wait exits with the job's exit
# code, so a failed run still fails CI under set -e; the job log is printed either way.
# Without a Slurm client on the agent, the script runs locally with bash instead.
slurm_run() {
  local log="$1" status=0
  shift
  if ! command -v sbatch >/dev/null; then
    echo "slurm_run: sbatch not found, running $1 locally" >&2
    bash "$@"
    return
  fi
  mkdir -p "$(dirname "$log")"
  sbatch --wait --output="$log" "$@" || status=$?
  cat "$log" || true
  return "$status"
}

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
  slurm_run "cases/runs/$(basename "$case_dir").slurm.out" bin/pds-run-case.sbatch "$case_dir"
}

# Run a case with checkpointing, then resume a second run from the middle workflow snapshot.
run_case_with_checkpoints() {
  local workflow="$1" shot="$2" every="$3"
  local case_dir="$PWD/cases/${workflow}_${shot}_checkpoints"
  bin/pds-create-case "$workflow" "$shot" "$case_dir"
  cat > "$case_dir/checkpoints.ymmsl" <<EOF
ymmsl_version: v0.2
checkpoints:
  at_end: true
  simulation_time:
  - every: $every
EOF
  local runs="cases/runs/$(basename "$case_dir")"
  slurm_run "$runs.slurm.out" bin/pds-run-case.sbatch "$case_dir" "$case_dir/checkpoints.ymmsl"

  local run_dir snapshots
  run_dir="$(realpath "$runs")"
  # Mid-run snapshots, one per distinct simulation time, in time order. The at_end ones
  # only hold "Final" snapshots and would resume at the very end.
  mapfile -t snapshots < <(awk '$NF == "Intermediate" {print $2, FILENAME}' \
    "$run_dir"/snapshots/snapshot_*.ymmsl | sort -n -u -k1,1 | cut -d' ' -f2)
  (( ${#snapshots[@]} >= 3 )) || { echo "expected >= 3 intermediate snapshots in $run_dir/snapshots" >&2; return 1; }
  # The resumed run needs checkpoints too: libmuscle 0.10 crashes on resume without them.
  slurm_run "$runs.resume.slurm.out" bin/pds-run-case.sbatch "$case_dir" \
    "$case_dir/checkpoints.ymmsl" "${snapshots[${#snapshots[@]} / 2]}"
}

# RUN TEST FILES

run_actor_test_clean test_sink_source_actor
run_actor_test_clean test_accumulator_actor
run_actor_test_clean test_olc_actor
run_actor_test_clean test_waveform_editor
run_actor_test_clean test_torax_actor
run_actor_test_clean test_nice_actor
run_actor_test_clean test_metis_actor
# run_actor_test_clean test_chease_actor

# Repeatability: the same coupling twice must give bit-identical sinks (catches
# thread-order or uninitialised-memory non-determinism in an actor).
bash ci/check_repeatability.sh ymmsl_files/test_nice_actor.ymmsl 2

# RUN WORKFLOWS

run_case_clean prescribed_transport 105099
run_case_with_checkpoints prescribed_transport 105099 10
run_case_clean inverse_convergence 105073
run_case_clean evolutive_controller 105073
run_case_clean metis_from_dina 105084
run_case_clean metis_nice_inverse_from_dina 105084
