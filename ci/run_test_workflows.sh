#!/bin/bash
# Bamboo CI script to install pds and run all tests
# Note: this script should be run from the root of the git repository

# Debuggging:
set -e -o pipefail

set -x

# SETUP
source /etc/profile.d/modules.sh
module purge

# bash pds_setup.sh
bash setup_files/setup_test_files.sh

cd run/
bash ../setup_files/setup_muscle3.sh
bash ../setup_files/setup_imas_muscle3.sh
bash ../setup_files/setup_waveform_editor.sh "https://github.com/iterorganization/Waveform-Editor.git" feature/reference-tendency-old
bash ../setup_files/setup_nice.sh "https://gitlab.inria.fr/blfauger/nice.git" develop
bash ../setup_files/setup_torax.sh
# uv isn't guaranteed to be present on the CI agent; bootstrap it via a disposable
# venv if missing (not `pip install --user`: the agent's home directory may not be
# writable, and the shared module Python's site-packages usually isn't either).
if command -v uv >/dev/null 2>&1; then
  UV="$(command -v uv)"
else
  rm -rf .uv-bootstrap
  python3 -m venv .uv-bootstrap
  .uv-bootstrap/bin/pip install --quiet uv
  UV="$(.uv-bootstrap/bin/python -c 'import uv; print(uv.find_uv_bin())')"
fi

# imas-validator 1.0.0 (latest release) is incompatible with imas-python 2.3
# (removed has_imas attribute); the olc actor needs the develop fix.
"$UV" pip install --python ./IMAS-MUSCLE3/venv/bin/python "git+https://github.com/iterorganization/imas-validator.git@develop"
cd ..


# RUN TEST FILES
# All actorn run on muscle3 0.10 so the manager also needs to run on 0.10.
MANAGER="$PWD/run/IMAS-MUSCLE3/venv/bin/muscle_manager"

# bash run_test_files.sh
"$MANAGER" --start-all ymmsl_files/test_sink_source_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_accumulator_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_olc_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_waveform_editor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_visualization_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_torax_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_nice_actor.ymmsl
# "$MANAGER" --start-all ymmsl_files/test_metis_actor.ymmsl

# RUN WORKFLOWS
bash run_workflow.sh prescribed_transport 105084
bash run_workflow.sh inverse_convergence 105084
# # EXPECT CRASH, HOW TO HANDLE?
# bash run_workflow.sh  torax_nice_self_rd_controller 105084

# # WAIT FOR METIS EASYBUILD MODULE
# bash run_workflow.sh metis_interpretative_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_predictive_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_interpretative_nicne_inverse_from_dina 105084 N_TIMESLICES=10
# bash run_workflow.sh metis_predictive_nice_inverse_from_dina 105084 N_TIMESLICES=10



