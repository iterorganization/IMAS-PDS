#!/bin/bash
# Build a custom NICE module, linked against MUSCLE3/0.10.0.
#
# The official NICE module's binaries have MUSCLE3/0.9.1 hardcoded into
# their RPATH (verified via readelf), which always wins over env vars, so
# this rebuilds NICE from source against 0.10.0 instead.
#
#
# Usage: bash build_nice.sh <module-version> [branch] [git-url]
# e.g:   bash build_nice.sh 3.0.0-pds-intel-2025b master
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source common.sh

MODULE_VERSION="${1:?usage: build_nice.sh <module-version> [branch] [git-url]}"
BRANCH="${2:-master}"
NICE_URL="${3:-https://gitlab.inria.fr/blfauger/nice.git}"

CHECKOUT="$PDS_SOFTWARE_ROOT/NICE/$MODULE_VERSION"
MODULE_NAME="${PDS_MODULE_PREFIX}NICE"
MODULE_DIR="$PDS_MODULES_ROOT/$MODULE_NAME"
MODULE_FILE="$MODULE_DIR/$MODULE_VERSION.lua"

echo "############## Building $MODULE_NAME/$MODULE_VERSION (branch: $BRANCH) ##############"
mkdir -p "$(dirname "$CHECKOUT")" "$MODULE_DIR"

# Overriding NICE's MUSCLE3 dependency to 0.10.0 leaves Lmod re-warning (and
# sometimes non-zero-exiting) on every later module command -- don't let
# `set -e` treat that as fatal; verify success via env vars instead.
module purge || true
module load NICE || true
module load MUSCLE3/0.10.0-intel-2025b || true

if [[ -z "${EBROOTMUSCLE3:-}" ]]; then
  echo "ERROR: MUSCLE3/0.10.0-intel-2025b did not actually load (EBROOTMUSCLE3 unset)." >&2
  exit 1
fi

# NICE only bakes explicit RPATH for IMAS-Cpp/IMAS-Core; everything else
# relies on LD_LIBRARY_PATH at runtime, which our PATH-only custom module
# won't provide later. Capture it now to bake into the RPATH below.
NICE_BUILD_LDPATH="$LD_LIBRARY_PATH"
# patchelf/0.18.0-GCCcore-14.3.0 (default) SIGILLs on some nodes; loading the
# working 13.2.0 build here would swap the whole GCCcore toolchain out from
# under the build. Load it in its own subshell per binary instead, after
# compiling is done.

if [[ ! -d "$CHECKOUT/.git" ]]; then
  git clone "$NICE_URL" "$CHECKOUT"
fi
cd "$CHECKOUT"
git fetch --quiet origin
git checkout "$BRANCH"
git submodule init
git submodule update
cp run/iwrap/param/inv/iter/param.x* run/input
cp run/iwrap/param/xsd/param.x* run/input

cd src
cp -f Makefile.TEMPLATE Makefile
NICE_MUSCLE3_TARGETS="nice_imas_inv_muscle3 nice_imas_dir_muscle3 nice_imas_evo_muscle3 nice_imas_evo_rd_muscle3"

# Remove any .o files from a previous run that may have been compiled under a
# swapped/wrong toolchain (e.g. a prior attempt that loaded patchelf too
# early) -- cheap to regenerate, not worth risking a silent ABI mismatch.
rm -f ./*.o

for target in $NICE_MUSCLE3_TARGETS; do
  # Cap parallelism: a bare `make -j` spawns one job per source file, which
  # can get the compiler OOM-killed (same note as setup_files/setup_nice.sh).
  make -j "$(nproc)" "$target"
done

for target in $NICE_MUSCLE3_TARGETS; do
  # Bake the full build-time library path into the binary's RPATH, so it
  # finds libmuscle.so/libymmsl.so and everything else at run time without
  # any of NICE's build dependencies loaded. Isolated in a subshell so
  # patchelf's toolchain swap (see above) can't affect anything else -- it's
  # the last thing done per binary.
  (
    module load patchelf/0.18.0-GCCcore-13.2.0 || true
    command -v patchelf >/dev/null || { echo "ERROR: patchelf did not load" >&2; exit 1; }
    patchelf --force-rpath --add-rpath "$NICE_BUILD_LDPATH" "../run/$target"
  )
done
cd ../..
module purge || true

cat > "$MODULE_FILE" << EOF
-- Custom PDS build of NICE, rebuilt against MUSCLE3/0.10.0 (the official
-- NICE/3.0.0 module is RPATH-linked to MUSCLE3/0.9.1, which conflicts with
-- IMAS-MUSCLE3/Waveform-Editor's MUSCLE3/0.10.0 dependency -- see the
-- comment at the top of setup_files/custom_modules/build_nice.sh).
-- Rebuild/update: bash setup_files/custom_modules/build_nice.sh <new-version> <branch>

help([[
$MODULE_NAME (custom PDS build of NICE, MUSCLE3/0.10.0-linked)

Source: $NICE_URL @ $BRANCH
Installed: $CHECKOUT
]])

whatis("Description: Custom PDS build of NICE, linked against MUSCLE3/0.10.0")

prepend_path("PATH", "$CHECKOUT/run")
setenv("EBROOTNICE", "$CHECKOUT")
EOF

echo "Installed $MODULE_NAME/$MODULE_VERSION -> $CHECKOUT/run"
echo "Module:    $MODULE_FILE"
echo ""
echo "NOTE: verify $CHECKOUT/run/nice_imas_inv_muscle3 actually runs and links"
echo "against MUSCLE3/0.10.0 before relying on it -- e.g.:"
echo "  ldd $CHECKOUT/run/nice_imas_inv_muscle3 | grep muscle"
