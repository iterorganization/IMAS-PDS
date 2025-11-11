# this file expects to be run from the 'run' folder
set -euo pipefail # stop if anything doesn't work

METIS_URL=${1:-"ssh://git@git.iter.org/scen/metis.git"}
BRANCH_METIS=${2:-"muscle3_develop"}

source imas_base_env
module load MATLAB
git clone $METIS_URL
cd metis
git checkout $BRANCH_METIS
matlab -nodisplay -batch zineb_path
module purge
cd ..
