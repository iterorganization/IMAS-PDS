# this file expects to be run from the 'local_installs' folder
#
# Installs the PCS framework WITH the Pulse Supervision Controller (PSC) into local_installs/pcs-nightly:
#   pcs-nightly/        clone of pcs (ssh://git@git.iter.org/pcs/pcs.git), branch master
#   pcs-nightly/pcssp/  clone of pcssp-nightly (ssh://git@git.iter.org/pcs/pcssp-nightly.git), branch
#                       merge_IGZ_PSC, with its scdds submodule (pcs/pcssp_pcs_add_paths.m expects the
#                       framework under pcssp/)
# Why a second PCS install next to local_installs/pcs: the PSC (pcssp/src/psc/PSC.slx, PSCSysObj) lives on
# pcssp-nightly branch merge_IGZ_PSC, not on the GitHub PCSSP framework that setup_pcs.sh clones. It is used
# by the magnetic_controller_psc actor (workflows/lib/psc_programs.ymmsl) and the preprocessing/psps scripts.
# Tested reference: pcs aa217bc (2026-08-17) + pcssp-nightly ebf3ee0 (2026-08-31); pds_setup.sh pins these
# commits (PIN_PCS_NIGHTLY_PCS / PIN_PCSSP_NIGHTLY, set empty to follow the branch tips).
# Both repositories need SSH access to git.iter.org.
set -euo pipefail # stop if anything doesn't work

PCS_URL=${1:-"ssh://git@git.iter.org/pcs/pcs.git"}
BRANCH_PCS=${2:-"master"}
PCSSP_NIGHTLY_URL=${3:-"ssh://git@git.iter.org/pcs/pcssp-nightly.git"}
BRANCH_PCSSP_NIGHTLY=${4:-"merge_IGZ_PSC"}
PIN_PCS=${5:-""}                # commit to check out after the branch (empty = branch tip)
PIN_PCSSP_NIGHTLY=${6:-""}      # idem for pcssp-nightly

git clone "$PCS_URL" pcs-nightly
cd pcs-nightly
git checkout $BRANCH_PCS
if [ -n "$PIN_PCS" ]; then git checkout "$PIN_PCS"; fi
git clone "$PCSSP_NIGHTLY_URL" pcssp
cd pcssp
git checkout $BRANCH_PCSSP_NIGHTLY
if [ -n "$PIN_PCSSP_NIGHTLY" ]; then git checkout "$PIN_PCSSP_NIGHTLY"; fi
git submodule update --init
cd ../..
