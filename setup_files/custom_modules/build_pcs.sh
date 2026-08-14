#!/bin/bash
# Build a custom PCS module: clones the PCS + PCSSP repos into shared storage
# once, instead of every user cloning both into their own local run/pcs/
# directory (setup_files/setup_pcs.sh's old per-checkout approach).
#
# No compile step: the magnetic_controller actor invokes PCS/PCSSP as raw
# MATLAB source, not a compiled binary -- see
# workflows/torax_nice_*controller/workflow.ymmsl.template's
# `magnetic_controller` actor. The module just needs the checkout to exist
# somewhere shared and point PCS_PATH/SCDDS_COREPATH at it.
#
# Usage: bash build_pcs.sh <module-version> [branch] [git-url]
# e.g:   bash build_pcs.sh 2026-08-14-pds master
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source common.sh

MODULE_VERSION="${1:?usage: build_pcs.sh <module-version> [branch] [git-url]}"
BRANCH="${2:-master}"
PCS_URL="${3:-ssh://git@git.iter.org/pcs/pcs.git}"

CHECKOUT="$PDS_SOFTWARE_ROOT/PCS/$MODULE_VERSION"
MODULE_DIR="$PDS_MODULES_ROOT/PDS-PCS"
MODULE_FILE="$MODULE_DIR/$MODULE_VERSION.lua"

echo "############## Building PDS-PCS/$MODULE_VERSION (branch: $BRANCH) ##############"
mkdir -p "$(dirname "$CHECKOUT")" "$MODULE_DIR"

if [[ ! -d "$CHECKOUT/.git" ]]; then
  git clone "$PCS_URL" "$CHECKOUT"
fi
cd "$CHECKOUT"
git fetch --quiet origin
git checkout "$BRANCH"

if [[ ! -d "$CHECKOUT/pcssp" ]]; then
  git clone https://github.com/iterorganization/PCSSP.git pcssp
fi
cd pcssp
git submodule update --init
cd ..

cat > "$MODULE_FILE" << EOF
-- Custom PDS build of PCS -- a shared, pre-cloned checkout (no per-user
-- 'run/pcs' clone needed anymore, see
-- setup_files/custom_modules/build_pcs.sh). PCS/PCSSP is MATLAB source, not
-- a compiled binary, so this is just a shared clone plus the env vars the
-- magnetic_controller actor needs.
-- Rebuild/update: bash setup_files/custom_modules/build_pcs.sh <new-version> <branch>

help([[
PDS-PCS (shared PCS + PCSSP checkout for the magnetic_controller actor)

Source: $PCS_URL @ $BRANCH (+ PCSSP submodule)
Installed: $CHECKOUT
]])

whatis("Description: Shared PCS/PCSSP checkout, MATLAB source, no compile step")

setenv("EBROOTPCS", "$CHECKOUT")
setenv("SCDDS_COREPATH", "$CHECKOUT/pcssp/scdds")
EOF

echo "Installed PDS-PCS/$MODULE_VERSION -> $CHECKOUT"
echo "Module:    $MODULE_FILE"
