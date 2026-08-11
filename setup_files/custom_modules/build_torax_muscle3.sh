#!/bin/bash
# Build a custom TORAX-MUSCLE3 module.
#
# Named TORAX-MUSCLE3, distinct from the official TORAX module: that one is
# published as -foss-2025b only, which conflicts with this cluster's
# intel-2025b stack (confirmed -- loading it swaps IMAS-Core/IMAS-Python down
# to older foss-2025b builds), and it doesn't include the MUSCLE3 actor
# wrapper anyway. This venv-based build sidesteps the toolchain question
# entirely, same as the official IMAS-MUSCLE3/Waveform-Editor modules do.
#
# Usage: bash build_torax_muscle3.sh <module-version> [branch]
# e.g:   bash build_torax_muscle3.sh develop-2026-08-10 develop
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source common.sh
source lib_venv_actor.sh

MODULE_VERSION="${1:?usage: build_torax_muscle3.sh <module-version> [branch]}"
BRANCH="${2:-develop}"

# TORAX-MUSCLE3's pyproject.toml pins a stale muscle3==0.8.0; override so the
# actor is compatible with the 0.10.0 manager (matches setup_files/setup_torax.sh).
build_venv_actor_module "TORAX-MUSCLE3" "$MODULE_VERSION" \
  "https://github.com/iterorganization/TORAX-MUSCLE3.git" "$BRANCH" \
  "muscle3==0.10.0"
