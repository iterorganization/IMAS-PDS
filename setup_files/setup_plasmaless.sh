# this file expects to be run from the 'local_installs' folder
set -euo pipefail # stop if anything doesn't work

# Plasmaless coil+vessel model, MATLAB (actor muscle3/muscle_plasmaless_actor.m, model
# imas_model/, machine description data/md_dd4/). Nothing to build: the install is the
# checkout. MATLAB (with the Control System Toolbox), PCS (for its muscle3 venv) and
# IMAS-MATLAB are loaded at run time by the `plasmaless` program in
# workflows/lib/local_programs.ymmsl, not here.
#
# BRANCH_PLASMALESS may be a branch, tag or commit. The default pins a commit of the
# IMAS_Muscle3 branch (main has no MUSCLE3 actor). To update, look up the new tip with
#   git ls-remote "$PLASMALESS_URL" refs/heads/IMAS_Muscle3
# and set it here and as BRANCH_PLASMALESS in pds_setup.sh; re-running this script then
# moves the existing checkout to it.
PLASMALESS_URL=${1:-"https://github.com/MireilleSchneider/plasmaless-tokamak-circuits.git"}
BRANCH_PLASMALESS=${2:-"a870c621ff512b6ee7ead46f83f0a384c2ce4652"}

if [[ ! -d "plasmaless-tokamak-circuits/.git" ]]; then
  git clone $PLASMALESS_URL plasmaless-tokamak-circuits
fi
cd plasmaless-tokamak-circuits
git fetch --quiet origin
git -c advice.detachedHead=false checkout $BRANCH_PLASMALESS
echo "  plasmaless commit: $(git rev-parse --short HEAD)"
cd ..
