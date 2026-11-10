#!/bin/bash
# PSC-4: build pcssp_controller_and_ps_psc.slx (copy of the fork wrapper with the PSC) and compile it,
# in the controller actor's module chain (PCS/2026.08-pds + IMAS-MATLAB 5.6.0 -> MATLAB 2025b-r1).
# VirtualGL LD_PRELOAD / DISPLAY are unset as bin/pds-run-case.sbatch:89 does (they hang load_simulink).
#SBATCH -J build_psc_controller
#SBATCH --partition=all_debug
#SBATCH --time=00:50:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=16G
#SBATCH -o cases/runs/psc4_logs/build_psc_controller_%j.log
# The -o path is relative to the submission directory: submit from the repo root,
#   cd <repo> && mkdir -p cases/runs/psc4_logs && \
#   sbatch preprocessing/psps/psc_run/build_psc_controller.sh
# or from elsewhere with `sbatch --chdir=<repo> ...`. PCS_PATH defaults to local_installs/pcs-nightly
# (pcs + pcssp-nightly with the PSC, installed by pds_setup.sh with INSTALL_PCS_NIGHTLY=true); export
# PCS_PATH to use another checkout.
source /usr/share/lmod/lmod/init/bash
# Repo root: an exported PDS_REPO, else the sbatch submission directory, else this file's location.
N="${PDS_REPO:-${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}}"
[[ -f "$N/bin/pds-run-case.sbatch" ]] || { echo "$N is not the PDS repo root"; exit 1; }
module purge
module use /work/projects/pds/modules/all
module load PCS/2026.08-pds
module load IMAS-MATLAB/5.6.0-intel-2025b-DD-4.1.1
unset LD_PRELOAD VGL_ISACTIVE VGL_DISPLAY DISPLAY PYTHONPATH
export PCS_PATH="${PCS_PATH:-$N/local_installs/pcs-nightly}"   # default: pds_setup.sh, INSTALL_PCS_NIGHTLY
[[ -d "$PCS_PATH/pcssp/src/psc" ]] || { echo "pcs-nightly not installed ($PCS_PATH/pcssp/src/psc missing): run pds_setup.sh with INSTALL_PCS_NIGHTLY=true"; exit 1; }
export SCDDS_COREPATH=$PCS_PATH/pcssp/scdds
W=/scratch/users/$USER/psc4                                   # scratch work folder (MATLAB cwd and tempdir)
export TMPDIR=$W/tmp_build_${SLURM_JOB_ID:-$$}; mkdir -p "$TMPDIR"
CFG=$(ls -d $N/cases/input/psc/A_nom/psc_config_*)
T="$N/preprocessing/psps/psc_run"
cd "$W"
matlab -batch "try; addpath('$T'); build_psc_controller_wrapper('$N/controllers/CCS', '$CFG'); catch ME; disp(getReport(ME)); exit(1); end"
echo "matlab rc=$?"
