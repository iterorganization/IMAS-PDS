# this file expects to be run from the 'run' folder
set -euo pipefail # stop if anything doesn't work

TORAX_URL=${1:-"https://github.com/mikesndrs/torax.git"}
BRANCH_TORAX=${2:-"feature/muscle3_actor"}

source torax_base_env
module load CMake/3.27.6-GCCcore-13.2.0 UDA
git clone "$TORAX_URL"
cd torax
git checkout $BRANCH_TORAX
python -m venv ./venv
. venv/bin/activate
pip install --upgrade pip
pip install build
pip install 'numpy > 2'
pip install 'imas-python @ git+https://github.com/mikesndrs/IMAS-Python.git@feature/enable-numpy-2.0'
pip install 'imas_core @ git+ssh://git@git.iter.org/imas/al-core.git@develop'
pip install -e .[dev,muscle3]
deactivate
module purge
cd ..
