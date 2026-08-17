#!/bin/bash
# Build a custom Waveform-Editor module -- e.g. to track `main` ahead of the
# official cluster module (currently Waveform-Editor/0.3.1-intel-2025b).
#
# Usage: bash build_waveform_editor.sh <module-version> [branch]
# e.g:   bash build_waveform_editor.sh main-2026-08-10 main
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source common.sh
source lib_venv_actor.sh

MODULE_VERSION="${1:?usage: build_waveform_editor.sh <module-version> [branch]}"
BRANCH="${2:-main}"

build_venv_actor_module "${PDS_MODULE_PREFIX}Waveform-Editor" "$MODULE_VERSION" \
  "https://github.com/iterorganization/Waveform-Editor.git" "$BRANCH"
