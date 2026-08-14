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
# Also builds muscle3_venv: metis4muscle3.m doesn't use a matlab-native
# MUSCLE3 client -- it calls Python's real libmuscle via MATLAB's
# `pyenv(...)`/`py.*` bridge. That Python must satisfy two constraints at
# once: (1) its libmuscle version must exactly match the actual
# muscle_manager (0.10.0, from PDS-IMAS-MUSCLE3) or actor registration fails
# with a wire-protocol "Unknown session X requested" error (confirmed), and
# (2) it must be a Python version MATLAB's `py.*` bridge actually supports
# (3.9-3.12 as of MATLAB/2025b-r1 -- 3.13, what PDS-IMAS-MUSCLE3's own venv
# uses, isn't supported by any MATLAB version installed on this cluster,
# confirmed against MathWorks' own compatibility table). No existing PDS
# venv satisfies both, so this builds a small, dedicated one on Python 3.11
# with just `muscle3==0.10.0` pip-installed.
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

# See header comment: a dedicated Python-3.11 + muscle3==0.10.0 venv for
# metis4muscle3.m's own `pyenv(...)` call, kept separate from
# PDS-IMAS-MUSCLE3's venv (Python 3.13, unsupported by any installed MATLAB).
module load Python/3.11.5-GCCcore-13.2.0
if [[ ! -d "$CHECKOUT/muscle3_venv" ]]; then
  python3 -m venv "$CHECKOUT/muscle3_venv"
fi
"$CHECKOUT/muscle3_venv/bin/pip" install --quiet "muscle3==0.10.0"
"$CHECKOUT/muscle3_venv/bin/python" -c "import libmuscle; assert libmuscle.__version__ == '0.10.0'"
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
