#!/bin/bash
# Bamboo CI script to install pds and run all tests
# Note: this script should be run from the root of the git repository

# Debuggging:
set -e -o pipefail

set -x

# Run a setup step in the background
run_step() {
  local name="$1"; shift
  ( "$@" 2>&1 | sed -u "s/^/[$name] /" ) &
  printf -v "pid_$name" '%s' "$!"
}

# Wait for a step started with run_step and report failure under its name.
wait_step() {
  local name="$1" pid="$2"
  wait "$pid" && return 0
  echo "[$name] FAILED" >&2
  return 1
}

###### SETUP ######
source "$(dirname "${BASH_SOURCE[0]}")/../setup_files/ensure_uv.sh"
source /etc/profile.d/modules.sh
module purge

# Bootstrap uv once here and put it on PATH so every setup_*.sh below finds
# it via `command -v uv` and skips ensure_uv.sh's own bootstrap -- otherwise
# running several of them in parallel would race on .uv-bootstrap.
export PATH="$(dirname "$UV"):$PATH"

run_step test_files bash setup_files/setup_test_files.sh

cd run/

run_step muscle3 bash ../setup_files/setup_muscle3.sh
run_step imas_muscle3 bash ../setup_files/setup_imas_muscle3.sh
run_step waveform_editor bash ../setup_files/setup_waveform_editor.sh \
  "https://github.com/iterorganization/Waveform-Editor.git" feature/reference-tendency-old
run_step torax bash ../setup_files/setup_torax.sh

fail=0

if wait_step muscle3 "$pid_muscle3"; then
  run_step nice bash ../setup_files/setup_nice.sh \
    "https://gitlab.inria.fr/blfauger/nice.git" develop
else
  echo "[nice] skipped -- muscle3 setup did not finish" >&2
  fail=1
fi

if wait_step imas_muscle3 "$pid_imas_muscle3"; then
  # imas-validator 1.0.0 (latest release) is incompatible with imas-python 2.3
  # (removed has_imas attribute); the olc actor needs the develop fix.
  run_step imas_validator "$UV" pip install \
    --python ./IMAS-MUSCLE3/venv/bin/python \
    "git+https://github.com/iterorganization/imas-validator.git@develop"
  wait_step imas_validator "$pid_imas_validator" || fail=1
else
  echo "[imas_validator] skipped -- imas_muscle3 setup did not finish" >&2
  fail=1
fi

wait_step waveform_editor "$pid_waveform_editor" || fail=1
wait_step torax "$pid_torax" || fail=1
[[ -n "${pid_nice:-}" ]] && { wait_step nice "$pid_nice" || fail=1; }

cd ..
wait_step test_files "$pid_test_files" || fail=1

if [[ $fail -ne 0 ]]; then
  echo "One or more setup steps failed" >&2
  exit 1
fi

###### RUN TEST FILES ######
# All actorn run on muscle3 0.10 so the manager also needs to run on 0.10.
MANAGER="$PWD/run/IMAS-MUSCLE3/venv/bin/muscle_manager"

# Prefixed tf_ to avoid colliding with the pid_<name> vars the setup steps
# above already set and waited on (e.g. pid_torax, pid_waveform_editor).
run_step tf_sink_source "$MANAGER" --start-all ymmsl_files/test_sink_source_actor.ymmsl
run_step tf_accumulator "$MANAGER" --start-all ymmsl_files/test_accumulator_actor.ymmsl
run_step tf_olc "$MANAGER" --start-all ymmsl_files/test_olc_actor.ymmsl
run_step tf_waveform_editor "$MANAGER" --start-all ymmsl_files/test_waveform_editor.ymmsl
run_step tf_visualization "$MANAGER" --start-all ymmsl_files/test_visualization_actor.ymmsl
run_step tf_torax "$MANAGER" --start-all ymmsl_files/test_torax_actor.ymmsl
run_step tf_nice "$MANAGER" --start-all ymmsl_files/test_nice_actor.ymmsl
# run_step tf_metis "$MANAGER" --start-all ymmsl_files/test_metis_actor.ymmsl

###### RUN WORKFLOWS ######
run_step prescribed_transport bash run_workflow.sh prescribed_transport 105084
run_step inverse_convergence bash run_workflow.sh inverse_convergence 105084
# # EXPECT CRASH, HOW TO HANDLE?
# bash run_workflow.sh  torax_nice_self_rd_controller 105084

# # WAIT FOR METIS EASYBUILD MODULE
# bash run_workflow.sh metis_interpretative_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_predictive_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_interpretative_nicne_inverse_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_predictive_nice_inverse_from_dina 105084 N_TIMESLICES=10

###### CHECK RUNS ######
tf_fail=0
wait_step tf_sink_source "$pid_tf_sink_source" || tf_fail=1
wait_step tf_accumulator "$pid_tf_accumulator" || tf_fail=1
wait_step tf_olc "$pid_tf_olc" || tf_fail=1
wait_step tf_waveform_editor "$pid_tf_waveform_editor" || tf_fail=1
wait_step tf_visualization "$pid_tf_visualization" || tf_fail=1
wait_step tf_torax "$pid_tf_torax" || tf_fail=1
wait_step tf_nice "$pid_tf_nice" || tf_fail=1

if [[ $tf_fail -ne 0 ]]; then
  echo "One or more test file runs failed" >&2
  exit 1
fi

wf_fail=0
wait_step prescribed_transport "$pid_prescribed_transport" || wf_fail=1
wait_step inverse_convergence "$pid_inverse_convergence" || wf_fail=1

if [[ $wf_fail -ne 0 ]]; then
  echo "One or more workflow runs failed" >&2
  exit 1
fi
