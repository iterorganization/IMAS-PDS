# this file expects to be run from the 'local_installs' folder
set -euo pipefail # stop if anything doesn't work

PCS_URL=${1:-"ssh://git@git.iter.org/pcs/pcs.git"}
BRANCH_PCS=${2:-"master"}

git clone "$PCS_URL"
cd pcs
git checkout $BRANCH_PCS
git clone https://github.com/iterorganization/PCSSP.git pcssp
cd pcssp
git submodule update --init
cd ../..
