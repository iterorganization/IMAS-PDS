#!/bin/bash
# Build a custom NICE module, linked against the official MUSCLE3/0.10.0
# module.
#
# Why this is needed: the official NICE/3.0.0-intel-2025b-DD-4.1.1 module's
# binaries have MUSCLE3/0.9.1's lib/ dir hardcoded into their RPATH (verified
# with `readelf -d`). RPATH always wins over environment variables, so no
# modulefile trick can point them at a different MUSCLE3 -- and
# IMAS-MUSCLE3/Waveform-Editor both require MUSCLE3/0.10.0. The only real fix
# is rebuilding NICE from source against 0.10.0, which is what this does.
#
# Named PDS-NICE, not bare NICE: several workflow .ymmsl(.template) files
# (torax_nice_controller, the metis_*_from_dina workflows,
# workflows/lib/easybuild_programs.ymmsl) specify `modules: NICE` directly --
# MUSCLE3's own per-actor module-load mechanism, separate from
# local_programs.ymmsl's $EBROOT*-based approach. If this were also just
# "NICE", those actors' bare `module load NICE` could resolve to the official
# (RPATH-broken) one instead of this build, depending on Lmod's tie-breaking
# across merged module trees -- not hypothetical, a real collision risk.
#
# We still `module load NICE` (the official one) first purely to pull in its
# OTHER build dependencies for free (IMAS-Cpp, SuiteSparse, Eigen, libxml2)
# via its own depends_on chain; MUSCLE3/0.10.0 loaded right after overrides
# just the MUSCLE3 piece for the actual build/link step.
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
MODULE_DIR="$PDS_MODULES_ROOT/PDS-NICE"
MODULE_FILE="$MODULE_DIR/$MODULE_VERSION.lua"

echo "############## Building PDS-NICE/$MODULE_VERSION (branch: $BRANCH) ##############"
mkdir -p "$(dirname "$CHECKOUT")" "$MODULE_DIR"

# Loading NICE then overriding its MUSCLE3 dependency to 0.10.0 leaves NICE's
# bookkeeping permanently unsatisfied (it wanted 0.9.1) for the rest of this
# shell -- Lmod re-warns about that on *every* subsequent module command, not
# just the one that caused it, and can return non-zero for it even though the
# load itself succeeds. So: don't let `set -e` treat any of these as fatal,
# and verify success explicitly via env vars afterward instead of exit codes.
module purge || true
module load NICE || true
module load MUSCLE3/0.10.0-intel-2025b || true

if [[ -z "${EBROOTMUSCLE3:-}" ]]; then
  echo "ERROR: MUSCLE3/0.10.0-intel-2025b did not actually load (EBROOTMUSCLE3 unset)." >&2
  exit 1
fi

# The Makefile only bakes in explicit -Wl,-rpath for IMAS-Cpp/IMAS-Core;
# everything else NICE links against (SuiteSparse, Blitz++, Boost, libxml2,
# ...) relies on LD_LIBRARY_PATH at runtime instead -- fine for the official
# module (which reloads the same dependencies every time via depends_on), not
# fine for our custom module (which only sets PATH, so none of this would be
# on LD_LIBRARY_PATH later). Capture the full build-time library path now, so
# every one of those directories gets baked into the RPATH below too -- same
# fix as MUSCLE3, just for everything at once, matching what the official
# EasyBuild-built NICE binary itself does (confirmed via `readelf -d`: it has
# 60+ RPATH entries, not just its own).
NICE_BUILD_LDPATH="$LD_LIBRARY_PATH"
# NOTE: patchelf is deliberately NOT loaded here. patchelf/0.18.0-GCCcore-14.3.0
# (the default) SIGILLs on at least one cluster compute node -- the older
# GCCcore-13.2.0 build works everywhere tested, but loading it here would
# swap the *whole* GCCcore toolchain (g++/ld) down to 13.2.0 for the rest of
# this shell, breaking links against the GCCcore-14.3.0-built IMAS-Cpp/
# IMAS-Core/CapnProto libs NICE needs (confirmed: caused
# `undefined reference to __cxa_call_terminate`). It's loaded in its own
# subshell per binary instead, after all compiling is done, so the swap never
# reaches a `make` call.

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
PDS-NICE (custom PDS build of NICE, MUSCLE3/0.10.0-linked)

Source: $NICE_URL @ $BRANCH
Installed: $CHECKOUT
]])

whatis("Description: Custom PDS build of NICE, linked against MUSCLE3/0.10.0")

prepend_path("PATH", "$CHECKOUT/run")
setenv("EBROOTNICE", "$CHECKOUT")
EOF

echo "Installed PDS-NICE/$MODULE_VERSION -> $CHECKOUT/run"
echo "Module:    $MODULE_FILE"
echo ""
echo "NOTE: verify $CHECKOUT/run/nice_imas_inv_muscle3 actually runs and links"
echo "against MUSCLE3/0.10.0 before relying on it -- e.g.:"
echo "  ldd $CHECKOUT/run/nice_imas_inv_muscle3 | grep muscle"
