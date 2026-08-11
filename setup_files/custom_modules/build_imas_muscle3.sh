#!/bin/bash
# Build a custom IMAS-MUSCLE3 module -- e.g. to track `develop` ahead of the
# official cluster module (currently IMAS-MUSCLE3/1.0.0-intel-2025b).
#
# Also installs muscle3-dashboard into the SAME venv, not a separate one --
# see docs/source/courses/basic/muscle3_dashboard.rst: a recorder tab's plot
# file imports imas_muscle3.visualization, which needs imas_muscle3 and the
# full IMAS stack in the dashboard's own venv to render (otherwise the tab
# just shows an error message). A lean, separate muscle3-dashboard venv
# doesn't have that; this venv already does, since it's the same one
# IMAS-MUSCLE3 itself was just installed into. Once this module is loaded,
# `muscle_dashboard`/`m3dash` are on PATH alongside the actors, no separate
# venv to activate.
#
# Because this is a shared venv, the optional graph-card dependency
# (ymmsl2svg) is installed carefully: it has, at least once, pulled in an
# experimental ymmsl fork older than what muscle3/imas-muscle3 require,
# which would silently break every actor in this venv, not just the
# dashboard. This script always reasserts the correct ymmsl afterward and
# fails loudly if that doesn't hold -- see the comment at that step.
#
# Usage: bash build_imas_muscle3.sh <module-version> [branch] [dashboard-branch]
# e.g:   bash build_imas_muscle3.sh develop-2026-08-10 develop main
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source common.sh
source lib_venv_actor.sh

MODULE_VERSION="${1:?usage: build_imas_muscle3.sh <module-version> [branch] [dashboard-branch]}"
BRANCH="${2:-develop}"
DASHBOARD_BRANCH="${3:-main}"
DASHBOARD_URL="https://github.com/multiscale/muscle3-dashboard.git"

build_venv_actor_module "IMAS-MUSCLE3" "$MODULE_VERSION" \
  "https://github.com/iterorganization/IMAS-MUSCLE3.git" "$BRANCH"

PREFIX="$PDS_SOFTWARE_ROOT/IMAS-MUSCLE3/$MODULE_VERSION"
DASHBOARD_SRC="$PREFIX/muscle3-dashboard-src"

echo "############## Adding muscle3-dashboard (branch: $DASHBOARD_BRANCH) ##############"
if [[ ! -d "$DASHBOARD_SRC/.git" ]]; then
  git clone "$DASHBOARD_URL" "$DASHBOARD_SRC"
fi
(
  cd "$DASHBOARD_SRC"
  git fetch --quiet origin
  git checkout "$DASHBOARD_BRANCH"
  git pull --quiet origin "$DASHBOARD_BRANCH" || true
)

# shellcheck disable=SC1091
. "$PREFIX/venv/bin/activate"
pip install -e "$DASHBOARD_SRC"
# Optional ymmsl2svg dependency for the per-run simulation graph card; if it
# fails to install, the rest of the dashboard still works, just with a
# dropdown of components shown instead of the graph.
#
# CAUTION: ymmsl2svg's own dependency chain has pulled in an experimental
# ymmsl fork (e.g. 0.16.1.dev0) that's *older* than what muscle3/imas-muscle3
# themselves require (>=0.17,<0.18) -- confirmed by pip's own conflict
# warning when this happened. That's not the documented "graph card hidden"
# degradation, it's a real regression risk to this venv's actors (source,
# sink, recorder, validator, ... all run from here per
# workflows/lib/local_programs.ymmsl). So: always re-assert the correct
# ymmsl afterward, whether or not the [graph] extra itself succeeded.
pip install -e "${DASHBOARD_SRC}[graph]" \
  || echo "WARNING: muscle3-dashboard [graph] extra failed -- dashboard will work without the per-run graph card."
pip install "ymmsl>=0.17,<0.18"
INSTALLED_YMMSL="$(python -c 'import ymmsl; print(ymmsl.__version__)' 2>/dev/null || echo unknown)"
case "$INSTALLED_YMMSL" in
  0.17.*) ;;
  *)
    echo "ERROR: ymmsl is $INSTALLED_YMMSL after reasserting >=0.17,<0.18 -- something in muscle3-dashboard's dependency chain still wants an incompatible version. Do not rely on this venv for actors until this is resolved." >&2
    deactivate
    exit 1
    ;;
esac
deactivate

echo "Installed muscle3-dashboard (branch $DASHBOARD_BRANCH) into $PREFIX/venv"
echo "  muscle_dashboard / m3dash available once IMAS-MUSCLE3/$MODULE_VERSION is loaded"
