# this file expects to be run from the 'run' folder
set -euo pipefail # stop if anything doesn't work

MUSCLE3_DASHBOARD_URL=${1:-"https://github.com/multiscale/muscle3-dashboard.git"}
BRANCH_MUSCLE3_DASHBOARD=${2:-"main"}

module purge
# Pinned: unversioned `module load Python` resolves to whatever the agent's
# default Python module is, which can be older than muscle3-dashboard's
# `requires-python = ">=3.11"` floor (seen in CI: 3.10.20).
module load Python/3.11.5-GCCcore-13.2.0

if [[ ! -d "muscle3-dashboard/.git" ]]; then
  git clone $MUSCLE3_DASHBOARD_URL muscle3-dashboard
fi
cd muscle3-dashboard
git fetch --quiet origin
git checkout $BRANCH_MUSCLE3_DASHBOARD
if [[ ! -d venv ]]; then
  python3 -m venv ./venv
fi
. venv/bin/activate
pip install -e .[graph]
echo "  muscle3-dashboard version: $(pip show muscle3-dashboard | grep '^Version')"
deactivate
module purge
cd ..
