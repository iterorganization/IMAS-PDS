# this file expects to be run from the 'run' folder
set -euo pipefail # stop if anything doesn't work

module purge
module load Python

IMAS_MUSCLE3_URL=${1:-"https://github.com/iterorganization/IMAS-MUSCLE3.git"}
BRANCH_IMAS_MUSCLE3=${2:-"develop"}
git clone $IMAS_MUSCLE3_URL
cd IMAS-MUSCLE3
git checkout $BRANCH_IMAS_MUSCLE3
python3 -m venv ./venv
. venv/bin/activate
pip install --upgrade pip
pip install --upgrade setuptools wheel
pip install -e .
deactivate
module purge
cd ..
