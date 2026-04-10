# this file expects to be run from the 'run' folder
set -euo pipefail # stop if anything doesn't work

NICE_URL=${1:-"https://gitlab.inria.fr/blfauger/nice.git"}
BRANCH_NICE=${2:-"master"}

source imas_base_env
module load NICE
git clone $NICE_URL
cd nice
git checkout $BRANCH_NICE
git submodule init
git submodule update
cp run/iwrap/param/inv/iter/param.x* run/input
cp run/iwrap/param/xsd/param.x* run/input
cd src
cp Makefile.TEMPLATE Makefile
make -j nice_imas_inv_muscle3
make -j nice_imas_dir_muscle3
make -j nice_imas_evo_muscle3
make -j nice_imas_evo_rd_muscle3
module purge
cd ../..
