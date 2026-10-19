# this file expects to be run from the 'local_installs' folder
set -euo pipefail # stop if anything doesn't work

# METIS_URL=${1:-"https://gitlab.eufus.psnc.pl/g2jfa/metis.git"}
METIS_URL=${1:-"ssh://git@git.iter.org/scen/metis.git"} # Temporary until latest developments pushed to GitLab
BRANCH_METIS=${2:-"muscle3_develop"}

source ../cases/imas_base_env
module load MATLAB
git clone $METIS_URL
cd metis
git checkout $BRANCH_METIS
matlab -nodisplay -batch zineb_path
module purge

# muscle3_venv: the Python 3.11 + muscle3==0.10.0 venv MATLAB's pyenv() drives libmuscle
# through (workflows/lib/local_programs.ymmsl, metis entry), created exactly as the
# METIS-IRFM easyconfig does (setup_files/easyconfigs/m/METIS-IRFM/*.eb, postinstallcmds).
# A local checkout must not fall back on that module for it. Skipped if it already exists.
if [[ ! -x muscle3_venv/bin/python ]]; then
  (
    module purge
    module load Python/3.11.5-GCCcore-13.2.0
    python -m venv muscle3_venv
    muscle3_venv/bin/pip install --quiet "muscle3==0.10.0" "ymmsl==0.17.0"
  )
fi
cd ..
