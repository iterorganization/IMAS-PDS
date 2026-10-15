# this file expects to be run from the 'local_installs' folder
set -euo pipefail # stop if anything doesn't work

# Plasmaless coil+vessel model, MATLAB (actor muscle3/muscle_plasmaless_actor.m, model
# imas_model/, machine description data/md_dd4/). Nothing to build: the install is the
# checkout. MATLAB (with the Control System Toolbox), PCS (for its muscle3 venv) and
# IMAS-MATLAB are loaded at run time by the `plasmaless` program in
# workflows/lib/local_programs.ymmsl, not here.
#
# BRANCH_PLASMALESS defaults to the IMAS_Muscle3_with_plasma branch of the
# plasma-tokamak-circuits repository (renamed 2026-10-15), which holds the MUSCLE3
# actor, the plasma-free model and the optional linear and vertical-instability models
# (IMAS_Muscle3 holds the plasma-free model only; main has no actor). A tag or
# commit may be passed as 2nd argument instead to pin a version.
PLASMALESS_URL=${1:-"https://github.com/federico-pesamosca/plasma-tokamak-circuits.git"}
BRANCH_PLASMALESS=${2:-"IMAS_Muscle3_with_plasma"}

if [[ ! -d "plasma-tokamak-circuits/.git" ]]; then
  git clone $PLASMALESS_URL plasma-tokamak-circuits
fi
cd plasma-tokamak-circuits
git fetch --quiet origin
git checkout $BRANCH_PLASMALESS
echo "  plasmaless commit: $(git rev-parse --short HEAD)"
cd ..
