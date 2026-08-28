# this file expects to be run from the 'local_installs' folder
set -euo pipefail # stop if anything doesn't work

module purge
module load Python/3.11.5-GCCcore-13.2.0

source "$(dirname "${BASH_SOURCE[0]}")/ensure_uv.sh"

IMAS_MUSCLE3_URL=${1:-"https://github.com/iterorganization/IMAS-MUSCLE3.git"}
BRANCH_IMAS_MUSCLE3=${2:-"develop"}

if [[ ! -d "IMAS-MUSCLE3/.git" ]]; then
  git clone $IMAS_MUSCLE3_URL IMAS-MUSCLE3
fi
cd IMAS-MUSCLE3
git fetch --quiet origin
git checkout $BRANCH_IMAS_MUSCLE3
if [[ ! -d venv ]]; then
  "$UV" venv ./venv
fi
. venv/bin/activate
"$UV" pip install -e .
echo "  muscle3 version: $("$UV" pip show muscle3 | grep '^Version')"
"$UV" pip install "ymmsl2svg @ git+https://github.com/DaanVanVugt/ymmsl2svg.git@feat/conduit-hover-labels"
echo "  muscle3-dashboard version: $("$UV" pip show muscle3-dashboard | grep '^Version')"
deactivate
module purge
cd ..
