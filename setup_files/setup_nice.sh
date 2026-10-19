# this file expects to be run from the 'local_installs' folder
set -euo pipefail # stop if anything doesn't work

NICE_URL=${1:-"https://gitlab.inria.fr/blfauger/nice.git"}
BRANCH_NICE=${2:-"master"}

# All nice_imas_*_muscle3 targets link against libmuscle/libymmsl via
# pkg-config; setup_muscle3.sh must have already written this wrapper env.
MUSCLE3_ENV_FILE="$PWD/tmp/muscle3-0.10.0-intel/bin/muscle3.env"
if [[ ! -f "$MUSCLE3_ENV_FILE" ]]; then
  echo "ERROR: muscle3 C++ library not set up -- run setup_muscle3.sh first." >&2
  exit 1
fi

source ../cases/imas_base_env
# A local build must not depend on NICE's own EasyBuild module (it would put the module's
# run/, runpython/ and runmatlab/ ahead of this checkout on PATH/LD_LIBRARY_PATH/
# PYTHONPATH/MATLABPATH). Only the infrastructure modules that module itself depends on
# are loaded -- the list of `module show NICE/3.0.0-intel-2023b-DD-4.1.0` minus NICE's
# MUSCLE3/0.8.0 (replaced by the 0.10.0 library from setup_muscle3.sh) and minus Python
# (src/Makefile.TEMPLATE uses neither python nor any EBROOT* variable: IMAS and MUSCLE3
# come in through pkg-config, SuiteSparse/libxml2 through the modules' LIBRARY_PATH).
# The same list is recorded next to the binaries for the run-time entries in
# workflows/lib/local_programs.ymmsl (nice_*), which load it instead of a NICE module.
NICE_DEP_MODULES="intel/2023b IMAS-Cpp/5.5.0-intel-2023b-DD-4.1.0 SuiteSparse/7.7.0-intel-2023b Eigen/3.4.0-GCCcore-13.2.0 libxml2/2.11.5-GCCcore-13.2.0"
module load $NICE_DEP_MODULES

if [[ ! -d "nice/.git" ]]; then
  git clone $NICE_URL nice
fi
cd nice
git fetch --quiet origin
git checkout $BRANCH_NICE
git submodule init
git submodule update
cp run/iwrap/param/inv/iter/param.x* run/input
cp run/iwrap/param/xsd/param.x* run/input

# Pull PKG_CONFIG_PATH/LD_LIBRARY_PATH for muscle3 0.10.0 into the build env
# (no lmod module is published for it -- only 0.7.x/0.8.0 are).
source "$MUSCLE3_ENV_FILE"

cd src
cp -f Makefile.TEMPLATE Makefile
NICE_MUSCLE3_TARGETS="nice_imas_inv_muscle3 nice_imas_dir_muscle3 nice_imas_evo_muscle3 nice_imas_evo_rd_muscle3"
module load patchelf/0.18.0-GCCcore-13.2.0

# Binaries are skipped if already built (below), to avoid recompiling the whole tree on every
# CI/dev run -- but that cache is only valid if it was built against $NICE_DEP_MODULES. Record
# the modules a binary was linked against next to it (as a shell fragment the run-time entries
# source), so a change of $NICE_DEP_MODULES above (e.g. a toolchain bump) invalidates stale
# binaries automatically instead of silently exec'ing a binary linked against a different,
# now-mismatched module tree.
RUNTIME_MODULES_FILE="../run/.nice_runtime_modules"
# Pre-2026-10 marker: it held the name of the NICE module the build was made under. A build
# made under NICE/3.0.0-intel-2023b-DD-4.1.0 was linked against exactly the modules
# $NICE_DEP_MODULES lists (that module's own dependencies), so it stays valid.
LEGACY_MARKER_FILE="../run/.nice_built_with_module"
recorded_modules="$( { [[ -f "$RUNTIME_MODULES_FILE" ]] && source "$RUNTIME_MODULES_FILE" && echo "${NICE_RUNTIME_MODULES:-}"; } 2>/dev/null || echo unknown)"
if [[ "$recorded_modules" != "$NICE_DEP_MODULES" ]]; then
  if [[ "$(cat "$LEGACY_MARKER_FILE" 2>/dev/null || echo unknown)" == "NICE/3.0.0-intel-2023b-DD-4.1.0" ]]; then
    echo "  Existing build was made under NICE/3.0.0-intel-2023b-DD-4.1.0, i.e. against $NICE_DEP_MODULES -- keeping it."
  else
    # No marker file at all (e.g. binaries from before this check existed) counts as a
    # mismatch too -- provenance unknown, so don't trust the cache.
    echo "  Existing build (if any) wasn't confirmed built against $NICE_DEP_MODULES -- forcing a rebuild."
    for target in $NICE_MUSCLE3_TARGETS; do
      rm -f "../run/$target"
    done
  fi
fi

for target in $NICE_MUSCLE3_TARGETS; do
  if [[ -f "../run/$target" ]]; then
    echo "  $target already built -- skipping (delete local_installs/nice/run/$target to force a rebuild)."
    continue
  fi
  # Cap parallelism: a bare `make -j` spawns one job per source file, which gets the
  # compilers OOM-killed on memory-limited CI agents, and `$(nproc)` reports the host's
  # cores, not the per-user quota (4 cores on the SDCC login nodes).
  make -j 4 "$target"
  # Bake $MUSCLE3_HOME/lib into the binary's RPATH so it finds libmuscle.so/
  # libymmsl.so at run time without sourcing muscle3.env (the actor scripts
  # that exec these binaries don't).
  patchelf --force-rpath --add-rpath "$MUSCLE3_HOME/lib" "../run/$target"
done
cat > "$RUNTIME_MODULES_FILE" <<RUNTIME_MODULES
# Written by setup_files/setup_nice.sh -- source it (bash) to get the modules the local
# NICE binaries in this directory were built against, and the muscle3 0.10.0 library
# directory baked into their RPATH. No NICE module is needed to run them.
export NICE_RUNTIME_MODULES="$NICE_DEP_MODULES"
export MUSCLE3_LIB="$MUSCLE3_HOME/lib"
RUNTIME_MODULES
rm -f "$LEGACY_MARKER_FILE"

module purge
cd ../..
