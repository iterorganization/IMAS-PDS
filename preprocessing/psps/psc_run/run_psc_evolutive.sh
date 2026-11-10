#!/bin/bash
# PSC-5: evolutive_controller 105073 in the reference clone with the real PSC in the controller actor
# (magnetic_controller_psc, workflows/lib/psc_programs.ymmsl; wrapper controllers/CCS/
# pcssp_controller_and_ps_psc.slx). Fork defaults otherwise (window to 87 s, 1 ms exchange, KCURR
# closes Ip, VS1+VS3, PS model). VARIANT = A_nom | B_edit | C_zhold | D_eof | SMOKE (A_nom, 0.2 s).
# MATLAB controller inits serialised with a mkdir lock (as p2e_evolutive.sh).
#SBATCH -J psc5_evo
#SBATCH --partition=all
#SBATCH --time=01:30:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=24 --mem=96G
#SBATCH -o cases/runs/psc5_logs/psc5_evo_%x_%j.log
# The -o path is relative to the submission directory: submit from the repo root,
#   cd <repo> && mkdir -p cases/runs/psc5_logs && VARIANT=A_nom sbatch preprocessing/psps/psc_run/run_psc_evolutive.sh
# or from elsewhere with `sbatch --chdir=<repo> ...`. The case overrides
# cases/overrides/evolutive_controller_105073_psc_*.ymmsl hold ${PDS_REPO} (repo root) and ${CASE_DIR} (case
# folder) placeholders: they are expanded below (envsubst, as bin/pds-create-case does) into the case folder
# before muscle_manager sees them. The designer pulse_schedule IDS read by ps_source is not stored in the
# repository: it is generated into the case folder at run time from the variant YAML (converter --ids).
set -uo pipefail
# Repo root: an exported PDS_REPO, else the sbatch submission directory (sbatch copies this script to the
# spool, so BASH_SOURCE cannot locate the repo there), else this file's location (preprocessing/psps/psc_run).
PDS_REPO="${PDS_REPO:-${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}}"
export PDS_REPO
[[ -f "$PDS_REPO/bin/pds-run-case.sbatch" ]] || { echo "PDS_REPO=$PDS_REPO is not the PDS repo root"; exit 1; }
cd "$PDS_REPO"
source /usr/share/lmod/lmod/init/bash
module use /work/projects/pds/modules/all
module load PDS
echo "HEAD $(git rev-parse --short HEAD) (+ uncommitted: $(git status --short | wc -l) entries)"
V=${VARIANT:?}
OVD=$PDS_REPO/cases/overrides
T="$PDS_REPO/preprocessing/psps/psc_run"
C=cases/evolutive_controller_105073_psc_$V
rm -rf "$C"; cp -a cases/evolutive_controller_105073 "$C"
case $V in
  SMOKE) OVS=(evolutive_controller_105073_psc_A_nom.ymmsl evolutive_controller_105073_psc_smoke_window.ymmsl) ;;
  A_nom|B_edit|C_zhold|D_eof) OVS=(evolutive_controller_105073_psc_$V.ymmsl) ;;
  *) echo "unknown VARIANT $V"; exit 1 ;;
esac
# Designer pulse_schedule IDS (DD 4.0.0): generated from the variant YAML (SMOKE uses A_nom) by the converter
# --ids into $C/pulse_schedule_ids/ids (no --cut-at: IDS times stay absolute; needs imas-python, PDS module).
# The overrides reach it through the ${CASE_DIR} placeholder.
VY=${V/SMOKE/A_nom}
Y=cases/input/psc/$VY/ip_105073_psc_$VY.yaml
python "$T/../ip_waveform_export/ip_waveform_export.py" --yaml "$Y" --out-dir "$C/pulse_schedule_ids" --ids --dd-version 4.0.0 || exit 1
export CASE_DIR="$PDS_REPO/$C"
OV=()
for f in "${OVS[@]}"; do envsubst '${PDS_REPO} ${CASE_DIR}' < "$OVD/$f" > "$C/$f"; OV+=("$C/$f"); done
python $T/make_p2d_workflow.py workflows/evolutive_controller/workflow.ymmsl "$C/workflow_p2d.ymmsl" || exit 1
python $T/make_psc_workflow.py "$C/workflow_p2d.ymmsl" "$C/workflow.ymmsl" || exit 1
rm -f "$C/workflow_p2d.ymmsl"
echo "=== RUN $V start $(date +%T) overlays=${OV[*]}"
LOCK=$PDS_REPO/cases/runs/psc5_init.lockdir
(
  until mkdir $LOCK 2>/dev/null; do sleep 10; done
  echo "init lock acquired $(date +%T)"
  timeout ${RUN_TIMEOUT:-5100} bash bin/pds-run-case.sbatch "$C" "${OV[@]}" &
  PID=$!
  B=$(basename $C)
  while kill -0 $PID 2>/dev/null; do
    if command grep -qs "Start closed loop" $(ls -dt cases/runs/${B}_2* 2>/dev/null | head -1)/instances/magnetic_controller/stdout.txt; then break; fi
    sleep 10
  done
  sleep 30
  rmdir $LOCK; echo "init lock released $(date +%T)"
  wait $PID; echo "pds-run-case rc=$?"
)
echo "=== RUN $V end $(date +%T) run_dir=$(readlink -f cases/runs/$(basename $C))"
echo PSC5_EVO_DONE
