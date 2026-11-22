#!/bin/bash
# One-time build of controllers/CCS/pcssp_controller_and_ps_mcls.slx (+ .sldd): a copy of the controller wrapper with
# the PSC, controllers/CCS/pcssp_controller_and_ps.slx, with the MCLS (Magnetic Control Local Supervisor) block beside
# the PSC (build_mcls_controller_wrapper.m of this folder), then the smoke test. The controller init runs the built
# model when mcls_enabled = 1. Rebuild only when the source model or controllers/CCS/mcls/third_party/MCLS.m change.
# Module chain as the controller actor (PCS/2026.08-pds + IMAS-MATLAB 5.6.0 -> MATLAB 2025b-r1), pyenv = the PCS
# module's muscle3_venv (pyyaml, needed by controllers/CCS/mcls/mcls_load_table.m); VirtualGL LD_PRELOAD / DISPLAY
# unset (they hang load_simulink in batch, bin/pds-run-case.sbatch); scratch work folder /scratch/users/$USER/mcls_build.
#SBATCH -J build_mcls_controller
#SBATCH --partition=all_debug
#SBATCH --time=00:50:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=16G
#SBATCH -o cases/runs/mcls_logs/build_mcls_controller_%j.log
# The -o path is relative to the submission directory and its folder must exist before sbatch:
#   mkdir -p <repo>/cases/runs/mcls_logs
#   sbatch --chdir=<repo> --export=ALL,PDS_REPO=<repo> --partition=all_debug --time=00:50:00 \
#          controllers/CCS/mcls/model_build/build_mcls_controller.sh
# PCS_PATH defaults to local_installs/pcs-with-pcssp-nightly, dereferenced (scdds_core_paths.m asserts SCDDS_COREPATH == its
# resolved folder); export PCS_PATH to use another checkout.
# Steps: (1) MATLAB test_mcls_block_standalone part 1 (block script as a function, the mode table of ip_story_mockup);
# (2) MATLAB build_mcls_controller_wrapper.m (needs pcssp_controller_and_ps.slx; compile check with the PSC
# configuration and mode table of cases/input/psc/ip_story_mockup); (3) MATLAB test_mcls_block_standalone part 2 (load +
# update of the new model).
# Per-step MATLAB logs: cases/runs/mcls_logs/mcls_<step>_<jobid>.log.
source /usr/share/lmod/lmod/init/bash
N="${PDS_REPO:-${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)}}"
[[ -f "$N/bin/pds-run-case.sbatch" ]] || { echo "$N is not the PDS repo root"; exit 1; }
[[ -f "$N/controllers/CCS/pcssp_controller_and_ps.slx" ]] || { echo "source model controllers/CCS/pcssp_controller_and_ps.slx missing in $N"; exit 1; }
module purge
module use /work/projects/pds/modules/all
module load PCS/2026.08-pds
module load IMAS-MATLAB/5.6.0-intel-2025b-DD-4.1.1
unset LD_PRELOAD VGL_ISACTIVE VGL_DISPLAY DISPLAY PYTHONPATH
export PCS_PATH="$(readlink -f "${PCS_PATH:-$N/local_installs/pcs-with-pcssp-nightly}")"
[[ -d "$PCS_PATH/pcssp/src/psc" ]] || { echo "pcs-with-pcssp-nightly not installed ($PCS_PATH/pcssp/src/psc missing): run pds_setup.sh with INSTALL_PCSSP_NIGHTLY=true or export PCS_PATH"; exit 1; }
export SCDDS_COREPATH=$PCS_PATH/pcssp/scdds
W=/scratch/users/$USER/mcls_build                             # scratch work folder (MATLAB cwd and tempdir)
export TMPDIR=$W/tmp_build_${SLURM_JOB_ID:-$$}; mkdir -p "$TMPDIR"
LOGS=$N/cases/runs/mcls_logs; mkdir -p "$LOGS"
J=${SLURM_JOB_ID:-$$}
B="$N/controllers/CCS/mcls/model_build"
TS="$N/controllers/CCS/mcls/tests"
CASE_IN="$N/cases/input/psc/ip_story_mockup"
for f in "$CASE_IN/mcls_table.yaml" "$CASE_IN/psc_config/PS.xml" "$N/controllers/CCS/mcls/third_party/MCLS.m" "$N/controllers/CCS/mcls/mcls_library_defaults.yaml"; do
  [[ -f $f ]] || { echo "$f missing"; exit 1; }
done
echo "repo $N  PCS_PATH $PCS_PATH  work $W  logs $LOGS"
cd "$W"
run_matlab() {  # name, matlab statements
  local name=$1 code=$2
  echo "=== $name start $(date +%T)"
  matlab -batch "try; pyenv('Version','$EBROOTPCS/muscle3_venv/bin/python','ExecutionMode','InProcess'); addpath('$B', '$TS'); $code catch ME; disp(getReport(ME)); exit(1); end" > "$LOGS/mcls_${name}_$J.log" 2>&1
  local rc=$?
  echo "=== $name rc=$rc $(date +%T); RESULT lines:"; grep -h "^RESULT\|^  OK\|^  FAIL\|Starting Control Mode\|Mode Forced" "$LOGS/mcls_${name}_$J.log" | head -40
  return $rc
}
# (1) part 1 of the smoke test: the block script as a plain MATLAB function, no Simulink (ccs = '' skips part 2)
run_matlab test1 "test_mcls_block_standalone('$N', '', false);" || exit 1
# Init lock shared with the run launcher workflows/evolutive_controller/run_psc_cases.sh: the PCS module inits
# regenerate the *.sldd of PCS_PATH, and a
# concurrent diagram update fails with "Data dictionary ... has been changed on the disk" (job 1317158 vs 1317159,
# 2026-11-15). The EXIT trap releases it on every exit path.
LOCK="$N/cases/runs/psc5_init.lockdir"
ACQUIRED=
release_lock() { [ -n "$ACQUIRED" ] && rmdir "$LOCK" 2>/dev/null && echo "init lock released $(date +%T) ($LOCK)"; }
trap release_lock EXIT
until mkdir "$LOCK" 2>/dev/null; do sleep 10; done
ACQUIRED=1
echo "init lock acquired $(date +%T) ($LOCK)"
# (2) the model (+ compile check with the PSC configuration and mode table of ip_story_mockup)
run_matlab build "build_mcls_controller_wrapper('$N/controllers/CCS', '$CASE_IN/psc_config', '$CASE_IN/mcls_table.yaml');" || exit 1
grep -q "^RESULT update OK" "$LOGS/mcls_build_$J.log" || { echo "build: diagram update did not succeed (see $LOGS/mcls_build_$J.log)"; exit 1; }
# (3) smoke test part 2
run_matlab test "test_mcls_block_standalone('$N', '$N/controllers/CCS', true);" || exit 1
echo "MCLS_BUILD_DONE $(date +%T)"
