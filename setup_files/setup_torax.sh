# this file expects to be run from the 'run' folder
set -euo pipefail # stop if anything doesn't work

TORAX_URL=${1:-"https://github.com/iterorganization/TORAX-MUSCLE3.git"}
BRANCH_TORAX=${2:-"main"}

module purge
module load Python
module load CMake/3.27.6-GCCcore-13.2.0 UDA
git clone "$TORAX_URL"
cd TORAX-MUSCLE3
git checkout $BRANCH_TORAX
python -m venv ./venv
. venv/bin/activate
pip install --upgrade pip setuptools
pip install build
pip install -e . "muscle3==0.8.0"
deactivate
module purge
cd ..
