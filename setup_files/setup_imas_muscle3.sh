# this file expects to be run from the 'run' folder
set -euo pipefail # stop if anything doesn't work

module purge
# Pinned: unversioned `module load Python` resolves to whatever the agent's
# default Python module is, which can be older than muscle3-dashboard's
# `requires-python = ">=3.11"` floor (seen in CI: 3.10.20).
module load Python/3.11.5-GCCcore-13.2.0

IMAS_MUSCLE3_URL=${1:-"https://github.com/iterorganization/IMAS-MUSCLE3.git"}
BRANCH_IMAS_MUSCLE3=${2:-"develop"}

if [[ ! -d "IMAS-MUSCLE3/.git" ]]; then
  git clone $IMAS_MUSCLE3_URL IMAS-MUSCLE3
fi
cd IMAS-MUSCLE3
git fetch --quiet origin
git checkout $BRANCH_IMAS_MUSCLE3
if [[ ! -d venv ]]; then
  python3 -m venv ./venv
fi
. venv/bin/activate
pip install --upgrade pip
pip install --upgrade setuptools wheel
pip install -e .
echo "  muscle3 version: $(pip show muscle3 | grep '^Version')"

# muscle3-dashboard[recording] is already a hard dependency above (this venv
# already carries the full IMAS stack imas_muscle3 needs), so this alone
# turns it into a fully dashboard-capable venv too (graph card included):
# `run/IMAS-MUSCLE3/venv` can run `muscle_dashboard`/`m3dash` end to end on
# its own, one venv, one setup script.
#
# `pip install -e .[dashboard]` alone can't do this: ymmsl2svg's git branch
# depends on ymmsl-python's feature/timelines branch, which self-reports as
# a pre-0.17 dev version despite being newer than the 0.17.0 release, so a
# normal resolve conflicts with this project's (and muscle3's) `ymmsl>=0.17`
# floor and raises ResolutionImpossible. Force-install the two pinned refs
# directly instead, bypassing dependency resolution so pip never has to
# reconcile both ymmsl constraints in one resolve.
pip install "svg.py" click
pip install --no-deps "ymmsl2svg @ git+https://github.com/DaanVanVugt/ymmsl2svg.git@feat/conduit-hover-labels"
pip install --no-deps "ymmsl @ git+https://github.com/multiscale/ymmsl-python.git@feature/timelines"
echo "  muscle3-dashboard version: $(pip show muscle3-dashboard | grep '^Version')"
deactivate
module purge
cd ..
