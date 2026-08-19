#!/bin/bash
# Build every module the PDS workflows need, with EasyBuild.
#
# Replaces the old setup_files/custom_modules/build_*.sh scripts. Most of what
# used to be hand-rolled here now comes straight from upstream easyconfigs; see
# README.md for what is pulled from where, and why the handful of local .eb
# files in this directory still exist.
#
# Usage:
#   bash build.sh              # everything not already installed
#   bash build.sh NICE CHEASE  # just these (names as listed in the arrays below)
#
# Override the install location by exporting EASYBUILD_PREFIX first; it defaults
# to ~/public so other people on SDCC can use what you build.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

: "${EASYBUILD_PREFIX:=$HOME/public}"
export EASYBUILD_PREFIX

: "${PDS_REPO:=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
export PDS_REPO

# --rpath is not optional. Every actor in workflows/lib/local_programs.ymmsl runs
# with `base_env: clean`, so its binaries have to resolve every shared library
# with nothing but their own module loaded -- no inherited LD_LIBRARY_PATH. This
# is what the old build_nice.sh / build_chease.sh faked afterwards with
# `patchelf --add-rpath "$LD_LIBRARY_PATH"`.
#
# --robot=<dir> takes priority over --robot-paths, so this directory resolves
# first: that is what makes i/IMAS-Validator/IMAS-Validator-1.0.0-intel-2025b.eb
# win over the copy in PR #26550, without shadowing anything else.
EB_OPTS=(--rpath --robot="$PWD")

# Upstream easyconfigs, taken from their (still open) pull requests rather than
# copied into this repo. Order matters: earlier entries are dependencies of
# later ones. `eb --from-pr` fetches the PR's easyconfigs and builds them.
declare -A UPSTREAM_PR=(
  [IMAS-Cpp]=26547          # IMAS-Cpp 5.6.0 + IMAS-Fortran 5.6.0 w/ DD 4.1.1
  [IMAS-Python]=26546       # 2.3.0
  [MUSCLE3]=26276           # 0.10.0
  [INTERPOS]=25841          # 9.2.3
  [iWrap]=26506             # 2.0.0 (+ JPype 1.7.1)
)
UPSTREAM_ORDER=(IMAS-Cpp IMAS-Python MUSCLE3 INTERPOS iWrap)

# Locally-maintained easyconfigs, for the codes with no upstream equivalent (plus
# the two deviations documented in README.md). Also dependency-ordered.
declare -A LOCAL_EC=(
  [IMAS-Validator]=i/IMAS-Validator/IMAS-Validator-1.0.0-intel-2025b.eb
  [IMAS-MUSCLE3]=i/IMAS-MUSCLE3/IMAS-MUSCLE3-1.0.0-intel-2025b-pds.eb
  [Waveform-Editor]=w/Waveform-Editor/Waveform-Editor-0.3.2-intel-2025b-pds.eb
  [NICE]=n/NICE/NICE-3.0.0.dev258-intel-2025b-pds.eb
  [CHEASE]=c/CHEASE/CHEASE-2026.08-intel-2025b-pds.eb
  [TORAX-MUSCLE3]=t/TORAX-MUSCLE3/TORAX-MUSCLE3-0.1.3-intel-2025b-pds.eb
  [METIS-IRFM]=m/METIS-IRFM/METIS-IRFM-2026.08-pds.eb
  [PCS]=p/PCS/PCS-2026.08-pds.eb
  [ymmsl2svg]=y/ymmsl2svg/ymmsl2svg-0.1.0-intel-2025b-pds.eb
  [PDS]=p/PDS/PDS-1.0.eb
)
# PDS last: it is the meta-module that loads the rest.
LOCAL_ORDER=(IMAS-Validator IMAS-MUSCLE3 Waveform-Editor NICE CHEASE TORAX-MUSCLE3 METIS-IRFM PCS ymmsl2svg PDS)

declare -A FORCE_REBUILD=(
  [IMAS-Validator]=IMAS-Validator/1.0.0-intel-2025b
)

wanted() {
  local target="$1"; shift
  [[ $# -eq 0 ]] && return 0
  for arg in "$@"; do [[ "$arg" == "$target" ]] && return 0; done
  return 1
}

command -v eb >/dev/null || { echo "ERROR: EasyBuild not on PATH -- 'module load EasyBuild' first." >&2; exit 1; }

echo "EasyBuild prefix: $EASYBUILD_PREFIX"
echo

for name in "${UPSTREAM_ORDER[@]}"; do
  wanted "$name" "$@" || continue
  echo "############## $name (upstream PR #${UPSTREAM_PR[$name]}) ##############"
  eb --from-pr="${UPSTREAM_PR[$name]}" "${EB_OPTS[@]}"
done

for name in "${LOCAL_ORDER[@]}"; do
  wanted "$name" "$@" || continue
  echo "############## $name (local: ${LOCAL_EC[$name]}) ##############"

  extra=()
  mod="${FORCE_REBUILD[$name]:-}"
  if [[ -n "$mod" && ! -f "$EASYBUILD_PREFIX/modules/all/$mod.lua" ]]; then
    echo "(not in $EASYBUILD_PREFIX yet, and a different build of the same name"
    echo " exists centrally -- forcing --rebuild so ours is the one that wins)"
    extra+=(--rebuild)
  fi

  eb "${LOCAL_EC[$name]}" "${EB_OPTS[@]}" "${extra[@]}"
done

echo
echo "Done. Make the results visible with:"
echo "  module use $EASYBUILD_PREFIX/modules/all"
echo "  cd /path/to/your/pds/checkout && module load PDS"
