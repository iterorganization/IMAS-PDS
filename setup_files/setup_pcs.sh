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
cd ..

# muscle3_venv: the Python 3.11 + muscle3==0.10.0 venv MATLAB's pyenv() drives libmuscle
# through (workflows/lib/local_programs.ymmsl, magnetic_controller entry), created exactly
# as the PCS easyconfig does (setup_files/easyconfigs/p/PCS/*.eb, postinstallcmds). A local
# checkout must not fall back on that module for it. Skipped if it already exists.
if [[ ! -x muscle3_venv/bin/python ]]; then
  (
    module purge
    module load Python/3.11.5-GCCcore-13.2.0
    python -m venv muscle3_venv
    muscle3_venv/bin/pip install --quiet "muscle3==0.10.0" "ymmsl==0.17.0"
  )
fi
cd ..
