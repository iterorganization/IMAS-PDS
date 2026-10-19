# this file expects to be run from the 'local_installs' folder
set -euo pipefail # stop if anything doesn't work

WAVEFORM_EDITOR_URL=${1:-"https://github.com/iterorganization/Waveform-Editor.git"}
BRANCH_WAVEFORM_EDITOR=${2:-"feature/reference-tendency-old"}  # PDS waveform files need globals.imports: added upstream 2026-06-24 (e11680d), reverted on develop 2026-07-22 (0cb665e); only this branch (= PDS module commit 08eebe8) keeps it

source ../cases/imas_base_env
module load Python

source "$(dirname "${BASH_SOURCE[0]}")/ensure_uv.sh"

if [[ ! -d "Waveform-Editor/.git" ]]; then
  git clone $WAVEFORM_EDITOR_URL Waveform-Editor
fi
cd Waveform-Editor
git fetch --quiet origin
git checkout $BRANCH_WAVEFORM_EDITOR
if [[ ! -d venv ]]; then
  "$UV" venv ./venv
fi
. venv/bin/activate
"$UV" pip install --no-config -e .[muscle3]
"$UV" pip install --no-config "ymmsl==0.17.0"  # --no-config: ignore the PDS repo's [tool.uv] ymmsl override (docs only); libmuscle 0.10.0 needs ymmsl 0.17.0
echo "  muscle3 version: $("$UV" pip show muscle3 | grep '^Version')"
deactivate
module purge
cd ..
