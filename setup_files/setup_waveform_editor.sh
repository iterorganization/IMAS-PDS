# this file expects to be run from the 'run' folder
set -euo pipefail # stop if anything doesn't work

WAVEFORM_EDITOR_URL=${1:-"https://github.com/iterorganization/Waveform-Editor.git"}
BRANCH_WAVEFORM_EDITOR=${2:-"develop"}

source imas_base_env
module load Python

if [[ ! -d "Waveform-Editor/.git" ]]; then
  git clone $WAVEFORM_EDITOR_URL Waveform-Editor
fi
cd Waveform-Editor
git fetch --quiet origin
git checkout $BRANCH_WAVEFORM_EDITOR
if [[ ! -d venv ]]; then
  uv venv ./venv
fi
. venv/bin/activate
uv pip install -e .[muscle3]
echo "  muscle3 version: $(uv pip show muscle3 | grep '^Version')"
deactivate
module purge
cd ..
