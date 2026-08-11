#!/bin/bash
# Build a custom IMAS-MUSCLE3 module -- e.g. to track `develop` ahead of the
# official cluster module (currently IMAS-MUSCLE3/1.0.0-intel-2025b).
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
