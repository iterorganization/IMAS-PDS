#!/bin/bash
# Build a custom CHEASE module: runs the exact same build recipe as
# setup_files/setup_chease.sh (clone, config_muscle3.sh, build_imas.csh,
# iwrap, the COCOS sed patch, make), just into shared storage instead of a
# per-user run/chease/ directory, plus RPATH-baking so the resulting
# chease.exe doesn't need any of its build dependencies loaded at run time.
#
# CHEASE is currently only wired up in the legacy
# ymmsl_files/test_chease_actor.ymmsl.template smoke test (bare `modules:
# IMAS-MUSCLE3`, [PWD_PLACEHOLDER], no `base_env: clean` -- predates this
# whole module-loading redesign), not any workflow under workflows/. This
# module makes that test actor self-contained the same way as everything
# else; it doesn't unblock a currently-broken production workflow the way
# PDS-METIS/PDS-PCS did.
#
# Like NICE (see build_nice.sh's header comment), this is a real compile step
# (`make` in chease_m3/), not just a shared clone -- the same RPATH-vs-
# LD_LIBRARY_PATH risk applies: CHEASE's Makefile likely bakes RPATH for a
# few explicit libs and relies on LD_LIBRARY_PATH (set by config_muscle3.sh
# at build time) for everything else, which a `base_env: clean` actor
# subprocess would never have. So: capture the full build-time
# LD_LIBRARY_PATH and patchelf it onto chease.exe's RPATH afterward, same
# fix, same reasoning as build_nice.sh. Not verified by a real workflow run
# yet (no production workflow uses this actor) -- if chease.exe still fails
# to find a library at run time despite this, check `ldd` first, same as the
# "NOTE" build_nice.sh prints at the end.
#
# Usage: bash build_chease.sh <module-version> [branch] [git-url]
# e.g:   bash build_chease.sh 2026-08-14-pds feature/muscle3
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source common.sh

MODULE_VERSION="${1:?usage: build_chease.sh <module-version> [branch] [git-url]}"
BRANCH="${2:-feature/muscle3}"
CHEASE_URL="${3:-https://gitlab.epfl.ch/spc/chease.git}"

CHECKOUT="$PDS_SOFTWARE_ROOT/CHEASE/$MODULE_VERSION"
MODULE_DIR="$PDS_MODULES_ROOT/PDS-CHEASE"
MODULE_FILE="$MODULE_DIR/$MODULE_VERSION.lua"

echo "############## Building PDS-CHEASE/$MODULE_VERSION (branch: $BRANCH) ##############"
mkdir -p "$(dirname "$CHECKOUT")" "$MODULE_DIR"

export XML_USE_CHOICE="NO"
# setup_chease.sh has this same line commented out -- config_muscle3.sh
# (sourced below) is what actually sets up the build environment; preserved
# as-is rather than guessing it should be enabled.
# source imas_base_env

if [[ ! -d "$CHECKOUT/.git" ]]; then
  git clone "$CHEASE_URL" "$CHECKOUT"
fi
cd "$CHECKOUT"
git fetch --quiet origin
git checkout "$BRANCH"

cd python
# shellcheck disable=SC1091
source config_muscle3.sh
cd ..
./build_imas.csh
iwrap -f iwrap/chease_choices_M3.yaml -i "$PWD"
rm -rf chease_m3
mv chease chease_m3

cd chease_m3
sed -i "s|<cocos_in>[0-9]\+</cocos_in>|<cocos_in>17</cocos_in>|" "input/chease_input_choices.xml"
sed -i "s|<cocos_out>[0-9]\+</cocos_out>|<cocos_out>17</cocos_out>|" "input/chease_input_choices.xml"
rm -f bin/chease.exe

# See header comment: capture the build-time library path (set by
# config_muscle3.sh above) right before compiling, so it can be baked into
# chease.exe's RPATH afterward -- same reasoning as build_nice.sh.
CHEASE_BUILD_LDPATH="$LD_LIBRARY_PATH"
make

# Isolated subshell, same as build_nice.sh: patchelf/0.18.0-GCCcore-14.3.0
# (the default) SIGILLs on at least one cluster compute node, and loading the
# older GCCcore-13.2.0 build directly in this shell would swap the whole
# GCCcore toolchain out from under any later step. Confined to its own
# subshell, after all compiling is done.
(
  module load patchelf/0.18.0-GCCcore-13.2.0 || true
  command -v patchelf >/dev/null || { echo "ERROR: patchelf did not load" >&2; exit 1; }
  patchelf --force-rpath --add-rpath "$CHEASE_BUILD_LDPATH" bin/chease.exe
)
cd ../..

cat > "$MODULE_FILE" << EOF
-- Custom PDS build of CHEASE (mirrors setup_files/setup_chease.sh's build
-- recipe into shared storage, see setup_files/custom_modules/build_chease.sh
-- for why: same RPATH-vs-LD_LIBRARY_PATH risk as NICE, since it's also a
-- fresh \`make\` compile, not just a shared clone).
-- Rebuild/update: bash setup_files/custom_modules/build_chease.sh <new-version> <branch>

help([[
PDS-CHEASE (custom PDS build of CHEASE)

Source: $CHEASE_URL @ $BRANCH
Installed: $CHECKOUT
]])

whatis("Description: Custom PDS build of CHEASE (IMAS-wrapped, MUSCLE3 actor)")

prepend_path("PATH", "$CHECKOUT/chease_m3/bin")
setenv("EBROOTCHEASE", "$CHECKOUT")
EOF

echo "Installed PDS-CHEASE/$MODULE_VERSION -> $CHECKOUT/chease_m3/bin"
echo "Module:    $MODULE_FILE"
echo ""
echo "NOTE: verify $CHECKOUT/chease_m3/bin/chease.exe actually runs from a"
echo "clean shell before relying on it -- e.g.:"
echo "  module purge; ldd $CHECKOUT/chease_m3/bin/chease.exe | grep 'not found'"
