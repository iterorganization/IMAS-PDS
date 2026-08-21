#!/bin/bash
#
# You can build the PDS modules with EasyBuild.
#
#   module load EasyBuild/5.4.0
#   bash build.sh                 # everything not already installed
#   bash build.sh NICE CHEASE     # just these
#
# Building your custom module of an actor (e.g. NICE) and using it in a PDS workflow:
#
# 1. Copy the easyconfig and give it a new version, so it sits next to the
#    shared build instead of replacing it.
#
#      cd n/NICE
#      cp NICE-3.0.0.dev258-intel-2025b-pds.eb NICE-mybranch-intel-2025b-pds.eb
#
# 2. Build it into your own prefix:
#
#      export EASYBUILD_PREFIX=$HOME/my-modules
#      module load EasyBuild/5.4.0
#      eb n/NICE/NICE-mybranch-intel-2025b-pds.eb --robot="$PWD"
#
# 3. Make it visible:
#
#      module use $HOME/my-modules/modules/all
#
# 4. Copy workflows/lib/local_programs.ymmsl to workflows/lib/local_programs_<you>.ymmsl
#    and change only that actor's `modules:` line to NICE/mybranch-intel-2025b-pds.
#
# 5. In the PDS workflow you are running, repoint just that one import:
#
#      - from lib.local_programs_<you> import implementation nice_inv

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

: "${EASYBUILD_PREFIX:=$HOME/public}"
export EASYBUILD_PREFIX

: "${PDS_REPO:=$(cd ../.. && pwd)}"
export PDS_REPO

EB_OPTS=(--robot="$PWD")

declare -A LOCAL_EC=(
  [IMAS-Validator]=i/IMAS-Validator/IMAS-Validator-1.0.0.dev69-intel-2025b-pds.eb
  [IMAS-MUSCLE3]=i/IMAS-MUSCLE3/IMAS-MUSCLE3-1.0.0-intel-2025b-pds.eb
  [Waveform-Editor]=w/Waveform-Editor/Waveform-Editor-0.3.2.dev154-intel-2025b-pds.eb
  [NICE]=n/NICE/NICE-3.0.0.dev258-intel-2025b-pds.eb
  [CHEASE]=c/CHEASE/CHEASE-2026.08-intel-2025b-pds.eb
  [TORAX-MUSCLE3]=t/TORAX-MUSCLE3/TORAX-MUSCLE3-0.1.3-intel-2025b-pds.eb
  [METIS-IRFM]=m/METIS-IRFM/METIS-IRFM-2026.08-pds.eb
  [PCS]=p/PCS/PCS-2026.08-pds.eb
  [ymmsl2svg]=y/ymmsl2svg/ymmsl2svg-0.1.0-intel-2025b-pds.eb
  [PDS]=p/PDS/PDS-1.0.eb
)
BUILD_ORDER=(IMAS-Validator IMAS-MUSCLE3 Waveform-Editor NICE CHEASE TORAX-MUSCLE3 METIS-IRFM PCS ymmsl2svg PDS)

command -v eb >/dev/null || { echo "ERROR: EasyBuild not on PATH -- 'module load EasyBuild' first." >&2; exit 1; }

echo "EasyBuild prefix: $EASYBUILD_PREFIX"
echo

for name in "${BUILD_ORDER[@]}"; do
  [[ $# -eq 0 || " $* " == *" $name "* ]] || continue
  echo "############## $name (${LOCAL_EC[$name]}) ##############"
  eb "${LOCAL_EC[$name]}" "${EB_OPTS[@]}"
done

echo
echo "Done. Make the results visible with:"
echo "  module use $EASYBUILD_PREFIX/modules/all"
echo "  cd /path/to/your/pds/checkout && module load PDS"
