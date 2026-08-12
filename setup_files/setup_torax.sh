# this file expects to be run from the 'run' folder
set -euo pipefail # stop if anything doesn't work

TORAX_URL=${1:-"https://github.com/iterorganization/TORAX-MUSCLE3.git"}
BRANCH_TORAX=${2:-"develop"}

module purge
module load Python
module load CMake/3.27.6-GCCcore-13.2.0 UDA

source "$(dirname "${BASH_SOURCE[0]}")/ensure_uv.sh"

if [[ ! -d "TORAX-MUSCLE3/.git" ]]; then
  git clone "$TORAX_URL" TORAX-MUSCLE3
fi
cd TORAX-MUSCLE3
git fetch --quiet origin
git checkout $BRANCH_TORAX
if [[ ! -d venv ]]; then
  "$UV" venv ./venv
fi
. venv/bin/activate
"$UV" pip install -e .
# TORAX-MUSCLE3's pyproject.toml pins a stale muscle3==0.8.0; override so the
# actor is compatible with the 0.10.0 manager (IMAS-MUSCLE3/Waveform-Editor
# already resolve to 0.10.0 on their own).
"$UV" pip install "muscle3==0.10.0"
echo "  muscle3 version: $("$UV" pip show muscle3 | grep '^Version')"
deactivate
module purge
cd ..
