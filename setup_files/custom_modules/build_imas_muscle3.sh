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
# The optional per-run graph card (ymmsl2svg) still needs a separate,
# carefully-pinned install -- see IMAS-MUSCLE3's own
# [project.optional-dependencies].dashboard entry and its comment for why
# it's not a plain pip extra: ymmsl2svg's own dependency chain pulls in an
# experimental ymmsl fork *older* than what muscle3/imas-muscle3 require,
# which would silently break every actor in this shared venv, not just the
# dashboard, if left in place. So: install the exact pin IMAS-MUSCLE3 itself
# documents, then always reassert the correct ymmsl afterward and fail loudly
# if that doesn't hold.
#
# Usage: bash build_imas_muscle3.sh <module-version> [branch]
# e.g:   bash build_imas_muscle3.sh develop-2026-08-10 develop
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source common.sh
source lib_venv_actor.sh

MODULE_VERSION="${1:?usage: build_imas_muscle3.sh <module-version> [branch]}"
BRANCH="${2:-develop}"

build_venv_actor_module "IMAS-MUSCLE3" "$MODULE_VERSION" \
  "https://github.com/iterorganization/IMAS-MUSCLE3.git" "$BRANCH"

PREFIX="$PDS_SOFTWARE_ROOT/IMAS-MUSCLE3/$MODULE_VERSION"

echo "############## Adding muscle3-dashboard's optional graph card ##############"
# shellcheck disable=SC1091
. "$PREFIX/venv/bin/activate"
pip install "ymmsl2svg @ git+https://github.com/DaanVanVugt/ymmsl2svg.git@feat/conduit-hover-labels" \
  || echo "WARNING: ymmsl2svg failed to install -- dashboard will work without the per-run graph card."
pip install "ymmsl>=0.17,<0.18"
INSTALLED_YMMSL="$(python -c 'import ymmsl; print(ymmsl.__version__)' 2>/dev/null || echo unknown)"
case "$INSTALLED_YMMSL" in
  0.17.*) ;;
  *)
    echo "ERROR: ymmsl is $INSTALLED_YMMSL after reasserting >=0.17,<0.18 -- something still wants an incompatible version. Do not rely on this venv for actors until this is resolved." >&2
    deactivate
    exit 1
    ;;
esac
python -c 'import muscle3_dashboard.recorder.actor' \
  || echo "WARNING: muscle3_dashboard.recorder is missing -- recorder-based workflows (prescribed_transport, etc.) will fail at runtime. Check IMAS-MUSCLE3's pyproject.toml still lists muscle3-dashboard[recording] as a core dependency."
deactivate

echo "Installed IMAS-MUSCLE3/$MODULE_VERSION -> $PREFIX/venv"
echo "  muscle_dashboard / m3dash available once this module is loaded"
