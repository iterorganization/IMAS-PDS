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

# workflows/lib/local_programs.ymmsl resolves actors via $EBROOT<NAME>, same
# as the custom modules setup_files/custom_modules/build_*.sh produce -- CI
# builds fresh into run/ every time instead, so just export the same names
# pointing at what was just built above.
export EBROOTIMASMUSCLE3="$PWD/run/IMAS-MUSCLE3"
export EBROOTWAVEFORMEDITOR="$PWD/run/Waveform-Editor"
export EBROOTNICE="$PWD/run/nice"
export EBROOTTORAXMUSCLE3="$PWD/run/TORAX-MUSCLE3"

###### RUN TEST FILES ######
# All actors run on muscle3 0.10 so the manager also needs to run on 0.10.
MANAGER="$EBROOTIMASMUSCLE3/venv/bin/muscle_manager"

"$MANAGER" --start-all ymmsl_files/test_sink_source_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_accumulator_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_olc_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_waveform_editor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_visualization_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_torax_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_nice_actor.ymmsl
# "$MANAGER" --start-all ymmsl_files/test_metis_actor.ymmsl

###### RUN WORKFLOWS ######
export HDF5_USE_FILE_LOCKING=FALSE

bash run_workflow.sh prescribed_transport 105084
bash run_workflow.sh inverse_convergence 105084
# # EXPECT CRASH, HOW TO HANDLE?
# bash run_workflow.sh  torax_nice_self_rd_controller 105073

# # WAIT FOR METIS EASYBUILD MODULE
# bash run_workflow.sh metis_interpretative_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_predictive_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_interpretative_nicne_inverse_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_predictive_nice_inverse_from_dina 105084 N_TIMESLICES=10
