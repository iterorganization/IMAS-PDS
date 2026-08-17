#!/bin/bash
# Build a custom IMAS-MUSCLE3 module -- e.g. to track `develop` ahead of the
# official cluster module.
#
# Do NOT separately clone/pip-install muscle3-dashboard: develop already
# declares muscle3-dashboard[recording] (a specific feature branch) as a core
# dependency, so build_venv_actor_module's `pip install -e .` already gets a
# fully dashboard-capable venv with the `recorder` submodule included. A
# separate install would overwrite it with one missing that submodule.
#
# ymmsl2svg (the optional dashboard graph card) needs ymmsl.v0_2.TimelineTree,
# only on ymmsl-python's `feature/timelines` branch, whose version string
# trips pip's dependency-conflict check against muscle3's declared ymmsl
# range -- a version-string mismatch only, not a functional break (confirmed:
# actors and a real workflow run still work). Install anyway.
#
# The OLC/validator actor needs imas-validator from `develop`, not the latest
# PyPI release, which calls an imas-python attribute removed for good in
# imas-python 2.3 -- crashes the actor at run time, and MUSCLE3 SIGKILLs
# every other actor when one crashes, so this looks like a mass failure. The
# check below verifies develop's fix actually landed.
#
# Usage: bash build_imas_muscle3.sh <module-version> [branch]
# e.g:   bash build_imas_muscle3.sh develop-2026-08-10 develop
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source common.sh
source lib_venv_actor.sh

MODULE_VERSION="${1:?usage: build_imas_muscle3.sh <module-version> [branch]}"
BRANCH="${2:-develop}"

MODULE_NAME="${PDS_MODULE_PREFIX}IMAS-MUSCLE3"
build_venv_actor_module "$MODULE_NAME" "$MODULE_VERSION" \
  "https://github.com/iterorganization/IMAS-MUSCLE3.git" "$BRANCH"

PREFIX="$PDS_SOFTWARE_ROOT/IMAS-MUSCLE3/$MODULE_VERSION"

echo "############## Fixing imas-validator (OLC actor) ##############"
# shellcheck disable=SC1091
. "$PREFIX/venv/bin/activate"
pip install "git+https://github.com/iterorganization/imas-validator.git@develop"

echo "############## Adding muscle3-dashboard's optional graph card ##############"
pip install "ymmsl2svg @ git+https://github.com/DaanVanVugt/ymmsl2svg.git@feat/conduit-hover-labels" \
  || echo "WARNING: ymmsl2svg failed to install -- dashboard will work without the per-run graph card."

FAIL=0
python -c 'import imas_muscle3.actors.source_component' 2>&1 \
  || { echo "ERROR: imas_muscle3 actors broke after installing ymmsl2svg." >&2; FAIL=1; }
python -c 'import imas_muscle3.actors.recorder_component' 2>&1 \
  || { echo "ERROR: imas_muscle3 recorder actor broke after installing ymmsl2svg." >&2; FAIL=1; }
python -c 'import libmuscle, muscle3' 2>&1 \
  || { echo "ERROR: libmuscle/muscle3 (the manager) broke after installing ymmsl2svg." >&2; FAIL=1; }
IMAS_VALIDATOR_DIR="$(python -c 'import imas_validator, os; print(os.path.dirname(imas_validator.__file__))')"
if grep -rq "has_imas" "$IMAS_VALIDATOR_DIR" 2>/dev/null; then
  echo "ERROR: installed imas-validator ($IMAS_VALIDATOR_DIR) still references has_imas -- likely resolved back to the broken 1.0.0 PyPI release instead of develop. The OLC/validator actor will crash and take the whole simulation down with it (MUSCLE3 SIGKILLs every other actor when one crashes)." >&2
  FAIL=1
fi
if [[ "$FAIL" -eq 1 ]]; then
  echo "ERROR: actor stack is broken -- do not rely on this venv until this is resolved." >&2
  deactivate
  exit 1
fi
python -c 'from ymmsl.v0_2 import TimelineTree; from ymmsl2svg.main import configuration2svg' 2>/dev/null \
  && echo "NOTE: graph card import chain OK -- ymmsl2svg should render." \
  || echo "NOTE: graph card import chain still broken -- dashboard will show the dropdown fallback instead (harmless, see muscle3_dashboard/components/ymmsl_graph.py's own try/except for this)."
deactivate

echo "Installed $MODULE_NAME/$MODULE_VERSION -> $PREFIX/venv"
echo "  muscle_dashboard / m3dash available once this module is loaded"
