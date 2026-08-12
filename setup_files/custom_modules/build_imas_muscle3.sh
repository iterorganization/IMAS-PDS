#!/bin/bash
# Build a custom IMAS-MUSCLE3 module -- e.g. to track `develop` ahead of the
# official cluster module (currently IMAS-MUSCLE3/1.0.0-intel-2025b).
#
# IMAS-MUSCLE3's develop branch (as of PR #59, "recorder_logic_in_dashboard")
# declares muscle3-dashboard[recording] (from a specific feature branch, not
# PyPI) as a CORE dependency -- see its pyproject.toml. So the plain
# `pip install -e .` that build_venv_actor_module already does is enough to
# get a fully dashboard-capable venv, `recorder` submodule included:
# `muscle_dashboard`/`m3dash` land on PATH alongside the actors, no separate
# venv to activate. Do NOT also clone/pip-install muscle3-dashboard
# separately here -- an earlier version of this script did exactly that
# (from a generic `main` checkout), which overwrote the correct
# feature-branch install with one missing the `recorder` submodule entirely
# (confirmed: `ModuleNotFoundError: No module named 'muscle3_dashboard.recorder'`
# at actual run time). If a future IMAS-MUSCLE3 version drops this from its
# core dependencies, re-add an explicit muscle3-dashboard install here.
#
# The optional per-run graph card needs ymmsl2svg, which needs
# ymmsl.v0_2.TimelineTree -- only on the multiscale/ymmsl-python
# `feature/timelines` branch, not in the ymmsl>=0.17,<0.18 that
# muscle3/imas-muscle3 formally declare. pip flags this as a dependency
# conflict ("muscle3 0.10.0 requires ymmsl<0.18,>=0.17.0, but you have ymmsl
# 0.16.1.dev0"), which looks alarming but is a version-STRING mismatch, not a
# functional break: feature/timelines just hasn't bumped its version past
# 0.17.0 yet, and is otherwise a superset. Confirmed empirically, not just
# assumed: with this ymmsl installed, imas_muscle3's actors (source, sink,
# recorder, validator) and libmuscle/muscle3 all still import cleanly, AND a
# real end-to-end workflow run (prescribed_transport/105084) completed
# successfully. So: install ymmsl2svg (which pulls this ymmsl in as its own
# transitive dependency) and verify actual functionality afterward -- actor
# imports plus the graph's own import chain -- rather than pip's version
# string, which is the wrong thing to gate on here.
#
# The OLC/validator actor needs imas-validator from `develop`, not the latest
# PyPI release (1.0.0): that release calls
# imas.backends.imas_core.imas_interface.has_imas, an attribute imas-python
# 2.3 removed FOR GOOD (it isn't coming back -- so the build-time check below
# must NOT assert imas-python still has it; instead it checks that the
# installed imas-validator's own source no longer references it at all, which
# is what `develop`'s fix actually did). Confirmed at real run time (a real
# inverse_convergence run's `validator` actor crashed with `AttributeError:
# ... has no attribute 'has_imas'`), not just at import time (a plain `import
# imas_muscle3.actors.olc_component` succeeds either way, since the call only
# happens deeper in imas_validator's own code path). One crashed actor takes
# the whole simulation down: MUSCLE3's manager SIGKILLs every other instance
# the moment one crashes, so this looked like a dozen unrelated actors
# failing at once ("-9" everywhere) when only one really was.
# ci/run_test_workflows.sh already documents and works around this exact
# issue; mirrored here so PDS-IMAS-MUSCLE3 doesn't regress it.
#
# Usage: bash build_imas_muscle3.sh <module-version> [branch]
# e.g:   bash build_imas_muscle3.sh develop-2026-08-10 develop
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source common.sh
source lib_venv_actor.sh

MODULE_VERSION="${1:?usage: build_imas_muscle3.sh <module-version> [branch]}"
BRANCH="${2:-develop}"

build_venv_actor_module "PDS-IMAS-MUSCLE3" "$MODULE_VERSION" \
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

echo "Installed PDS-IMAS-MUSCLE3/$MODULE_VERSION -> $PREFIX/venv"
echo "  muscle_dashboard / m3dash available once this module is loaded"
