# this file expects to be run from the 'run' folder
set -euo pipefail # stop if anything doesn't work

module purge
module load Python

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
deactivate
module purge
cd ..
