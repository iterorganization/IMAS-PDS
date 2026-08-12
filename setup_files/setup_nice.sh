# this file expects to be run from the 'run' folder
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

source imas_base_env
# Pinned to match the version the nice_inv actor script (workflows/lib/local_programs.ymmsl)
# loads at run time -- an unversioned `module load NICE` floats to whatever the EasyBuild
# tree's default is, which can drift to a newer toolchain (e.g. intel-2025b) and produce a
# binary whose deps don't match the older module loaded at run time, failing to exec (127).
NICE_MODULE="NICE/3.0.0-intel-2023b-DD-4.1.0"
module load "$NICE_MODULE"

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
module load patchelf

# Binaries are skipped if already built (below), to avoid recompiling the whole tree on every
# CI/dev run -- but that cache is only valid if it was built against $NICE_MODULE. Record the
# module a binary was linked against next to it, so a bump of $NICE_MODULE above (e.g. the
# EasyBuild default drifting to a newer toolchain) invalidates stale binaries automatically
# instead of silently exec'ing a binary linked against a different, now-mismatched module tree.
BUILT_WITH_FILE="../run/.nice_built_with_module"
# No marker file at all (e.g. binaries from before this check existed) counts as a mismatch too
# -- provenance unknown, so don't trust the cache.
if [[ "$(cat "$BUILT_WITH_FILE" 2>/dev/null || echo unknown)" != "$NICE_MODULE" ]]; then
  echo "  Existing build (if any) wasn't confirmed built against $NICE_MODULE -- forcing a rebuild."
  for target in $NICE_MUSCLE3_TARGETS; do
    rm -f "../run/$target"
  done
fi

for target in $NICE_MUSCLE3_TARGETS; do
  if [[ -f "../run/$target" ]]; then
    echo "  $target already built -- skipping (delete run/nice/run/$target to force a rebuild)."
    continue
  fi
  # Cap parallelism: a bare `make -j` spawns one job per source file, which
  # gets the compilers OOM-killed on memory-limited CI agents.
  make -j "$(nproc)" "$target"
  # Bake $MUSCLE3_HOME/lib into the binary's RPATH so it finds libmuscle.so/
  # libymmsl.so at run time without sourcing muscle3.env (the actor scripts
  # that exec these binaries don't).
  patchelf --force-rpath --add-rpath "$MUSCLE3_HOME/lib" "../run/$target"
done
echo "$NICE_MODULE" > "$BUILT_WITH_FILE"

module purge
cd ../..
