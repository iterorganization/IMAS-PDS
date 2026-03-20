# this file expects to be run from the 'run' folder
set -euo pipefail # stop if anything doesn't work

WAVEFORM_EDITOR_URL=${1:-"https://github.com/iterorganization/Waveform-Editor.git"}
BRANCH_WAVEFORM_EDITOR=${2:-"main"}

source imas_base_env
module load Python

git clone $WAVEFORM_EDITOR_URL
cd Waveform-Editor
git checkout $BRANCH_WAVEFORM_EDITOR
python3 -m venv ./venv
. venv/bin/activate
pip install -e .[muscle3]
deactivate
module purge
cd ..
