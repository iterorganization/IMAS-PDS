#!/bin/bash
# Build a custom METIS module: clones METIS into shared storage once and runs
# its own one-time MATLAB path-init, instead of every user cloning it and
# running `matlab -batch zineb_path` in their own local run/metis/ directory
# (setup_files/setup_metis.sh's old per-checkout approach).
#
# No compile step, no RPATH concerns here (unlike build_nice.sh): the metis
# actor is invoked as raw MATLAB source, not a compiled binary --
# `addpath(getenv('DIR_METIS4MUSCLE3')); metis4muscle3(2)`, see
# workflows/metis_*_from_dina/workflow.ymmsl.template's `metis:` actor. The
# module just needs METIS's checkout to exist somewhere shared and point
# DIR_METIS4MUSCLE3 at its workflow/muscle3/mfile subdirectory.
#
# Usage: bash build_metis.sh <module-version> [branch] [git-url]
# e.g:   bash build_metis.sh 2026-08-14-pds muscle3_develop
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source common.sh

MODULE_VERSION="${1:?usage: build_metis.sh <module-version> [branch] [git-url]}"
BRANCH="${2:-muscle3_develop}"
METIS_URL="${3:-ssh://git@git.iter.org/scen/metis.git}"

CHECKOUT="$PDS_SOFTWARE_ROOT/METIS/$MODULE_VERSION"
MODULE_DIR="$PDS_MODULES_ROOT/PDS-METIS"
MODULE_FILE="$MODULE_DIR/$MODULE_VERSION.lua"

echo "############## Building PDS-METIS/$MODULE_VERSION (branch: $BRANCH) ##############"
mkdir -p "$(dirname "$CHECKOUT")" "$MODULE_DIR"

if [[ ! -d "$CHECKOUT/.git" ]]; then
  git clone "$METIS_URL" "$CHECKOUT"
fi
cd "$CHECKOUT"
git fetch --quiet origin
git checkout "$BRANCH"

# Mirrors setup_metis.sh's own sequence exactly (source imas_base_env; module
# load MATLAB; matlab -batch zineb_path), just against this shared checkout
# instead of a per-user one.
module purge || true
module load MATLAB || true
if ! command -v matlab >/dev/null; then
  echo "ERROR: MATLAB did not load -- cannot run METIS's zineb_path init." >&2
  exit 1
fi
matlab -nodisplay -batch zineb_path
module purge || true

cat > "$MODULE_FILE" << EOF
-- Custom PDS build of METIS -- a shared, pre-cloned checkout (no per-user
-- 'run/metis' clone needed anymore, see
-- setup_files/custom_modules/build_metis.sh). METIS is MATLAB source, not a
-- compiled binary, so this is just a shared clone plus the one env var the
-- metis actor's muscle3 wrapper needs.
-- Rebuild/update: bash setup_files/custom_modules/build_metis.sh <new-version> <branch>

help([[
PDS-METIS (shared METIS checkout for the metis actor's muscle3 wrapper)

Source: $METIS_URL @ $BRANCH
Installed: $CHECKOUT
]])

whatis("Description: Shared METIS checkout, MATLAB source, no compile step")

setenv("EBROOTMETIS", "$CHECKOUT")
setenv("DIR_METIS4MUSCLE3", "$CHECKOUT/workflow/muscle3/mfile")
EOF

echo "Installed PDS-METIS/$MODULE_VERSION -> $CHECKOUT"
echo "Module:    $MODULE_FILE"
