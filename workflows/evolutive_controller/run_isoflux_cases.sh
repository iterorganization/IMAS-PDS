#!/bin/bash
# evolutive_controller 105073 isoflux shape-control test with the standard controller program magnetic_controller
# (workflows/lib/local_programs.ymmsl; no PSC, no MCLS). CASE (argument) =
#   isoflux_off  shape_control 0: reference without shape control;  overlay cases/overrides/evolutive_controller_105073_isoflux_off.ymmsl
#   isoflux_xp   shape_control 3: isoflux X-point control;          overlay cases/overrides/evolutive_controller_105073_isoflux_xp.ymmsl
#   isoflux_lim_off  shape_control 0: reference of isoflux_lim;   overlay cases/overrides/evolutive_controller_105073_isoflux_lim_off.ymmsl
#   isoflux_lim      shape_control 2: isoflux limiter control;    overlay cases/overrides/evolutive_controller_105073_isoflux_lim.ymmsl
#   isoflux_off_long / isoflux_xp_long   the same two on 10 s (16.2176 -> 26.2176 s) with the dense trace inverse_convergence_105073_dense
#   isoflux_xp_fs2      isoflux_xp with isoflux_flux_scale 2 (dense trace)
#   isoflux_xp_refxp    isoflux_xp with the reference flux at the reference X-point, xp_flux_at_ref 1 (dense trace)
#   isoflux_off_rz / isoflux_xp_rz  isoflux_off / isoflux_xp_refxp with the position controller RZIp on (dense trace)
#   isoflux_lim_off_cc / isoflux_lim_cc  isoflux_lim_off / isoflux_lim on a rerun of the limiter trace with the area-weighted current centre
# isoflux_off/xp: window 16.217598 -> 20.2176 s (4 s) on cases/runs/inverse_convergence_105073; isoflux_lim_off/lim: window 7.417598 -> 10.4176 s
# (3 s, limited plasma) on cases/runs/inverse_convergence_105073_limiter. The trace of a case is its latest stamped run
# cases/runs/<TRACE>_<stamp>, substituted for @TRACE_RUN@ in a copy of the overlay under /scratch/users/$USER/claude_tmp/isoflux_ov/
# (the first four overlays carry no placeholder and name their trace run themselves).
# Case folder cases/evolutive_controller_105073_<CASE> (a copy of the base case,
# rebuilt at every call), run directory cases/runs/evolutive_controller_105073_<CASE>_<stamp>, controller outputs there:
# isoflux_refs.mat, isoflux_log.csv, simulink_log.csv.
# RUN_TIMEOUT=<s>  time limit of the run inside the job (default 4500 s: 4 s of plasma at ~6.5 min of wall time per
#                  plasma second, plus ~10 min of MATLAB init). The 10 s cases (*_long) need ~75 min of plasma plus the
#                  init: submit them with --time=02:00:00 and --export=ALL,PDS_REPO=<repo>,RUN_TIMEOUT=6000.
# MATLAB controller inits are serialised with the mkdir lock cases/runs/psc5_init.lockdir (shared with run_psc_cases.sh
# and controllers/CCS/mcls/model_build/build_mcls_controller.sh: the inits regenerate the same PCS *.sldd).
#SBATCH -J isoflux
#SBATCH --partition=all
#SBATCH --time=01:30:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=24 --mem=96G
#SBATCH -o cases/runs/psc_logs/iso_%x_%j.log
# The -o path is relative to the submission directory and its folder must exist:
#   sbatch --chdir=<repo> --export=ALL,PDS_REPO=<repo> --job-name=iso_xp workflows/evolutive_controller/run_isoflux_cases.sh isoflux_xp
set -uo pipefail
PDS_REPO="${PDS_REPO:-${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}}"
export PDS_REPO
[[ -f "$PDS_REPO/bin/pds-run-case.sbatch" ]] || { echo "PDS_REPO=$PDS_REPO is not the PDS repo root"; exit 1; }
cd "$PDS_REPO"
source /usr/share/lmod/lmod/init/bash
module use /work/projects/pds/modules/all
# Pinned: PDS/1.1 (IMAS-MUSCLE3 1.0.1.dev133) recorder rejects the 's' recorder ports of this
# workflow ("recorder ports must be f_init, not s"); the reference runs used PDS/1.0.
module load PDS/1.0
echo "HEAD $(git rev-parse --short HEAD) (+ uncommitted: $(git status --short | wc -l) entries)"
CASES="isoflux_off isoflux_xp isoflux_lim_off isoflux_lim isoflux_off_long isoflux_xp_long isoflux_xp_fs2 isoflux_xp_refxp isoflux_off_rz isoflux_xp_rz isoflux_lim_off_cc isoflux_lim_cc"
V=${1:?CASE must be one of: $CASES}
case $V in
  isoflux_off|isoflux_xp) TRACE=inverse_convergence_105073;;
  isoflux_off_long|isoflux_xp_long|isoflux_xp_fs2|isoflux_xp_refxp|isoflux_off_rz|isoflux_xp_rz) TRACE=inverse_convergence_105073_dense;;
  isoflux_lim_off|isoflux_lim|isoflux_lim_off_cc|isoflux_lim_cc) TRACE=inverse_convergence_105073_limiter;;
  *) echo "unknown CASE $V ($CASES)"; exit 1;;
esac
RUN_TIMEOUT=${RUN_TIMEOUT:-4500}
OV_SRC=$PDS_REPO/cases/overrides/evolutive_controller_105073_$V.ymmsl
C=cases/evolutive_controller_105073_$V
[[ -f $OV_SRC ]] || { echo "$OV_SRC missing"; exit 1; }
TR=$(ls -d cases/runs/${TRACE}_2* 2>/dev/null | sort | tail -1)
[[ -n "$TR" && -f $TR/out_nice/equilibrium.h5 ]] || { echo "no run cases/runs/${TRACE}_<stamp> with out_nice/equilibrium.h5 (warm-start trace of source)"; exit 1; }
START_STAMP=$(date +%Y%m%d_%H%M%S)
OV=/scratch/users/$USER/claude_tmp/isoflux_ov/${V}_$START_STAMP.ymmsl
mkdir -p "$(dirname "$OV")"
sed "s#@TRACE_RUN@#$PDS_REPO/$TR#g" "$OV_SRC" > "$OV"
rm -rf "$C"; cp -a cases/evolutive_controller_105073 "$C"
# Coil-current feed-forward (linearly interpolated) and TORAX core_profiles from the overlay's source run
# (the base yaml names the coarse trace)
SRC_URI=$(sed -n 's/^ *source\.source_uri: *//p' "$OV")
WF_SRC=$(sed -n 's/^ *waveform_editor\.waveforms: *//p' "$OV")
WF=$PDS_REPO/$C/config/waveforms_ff.yaml
CP=$PDS_REPO/$C/preprocess/trace_core_profiles
if [[ -n $SRC_URI ]]; then
  SRC_RUN=$(sed 's#^"*imas:hdf5?path=\(.*\)/out_nice"*$#\1#' <<< "$SRC_URI")
  IMAS_AL_DISABLE_VALIDATE=1 python preprocessing/inverse_convergence/dedup_core_profiles_grid.py \
    "imas:hdf5?path=$SRC_RUN/out_torax" "imas:hdf5?path=$CP" || exit 1
fi
sed -e "${SRC_URI:+s#^\( *nice: \).*#\1$SRC_URI#}" -e "${SRC_URI:+s#^\( *torax: \).*#\1\"imas:hdf5?path=$CP\"#}" \
  -e 's#^\( *- {ref: nice\)}$#\1, interp: linear}#' \
  "${WF_SRC:-$C/config/evolutive_controller_105073_waveforms.yaml}" > "$WF"
sed -i '/^ *waveform_editor\.waveforms:/d' "$OV"; echo "  waveform_editor.waveforms: $WF" >> "$OV"
export CASE_DIR="$PDS_REPO/$C"
echo "=== RUN $V start $(date +%T) overlay=$OV (from $OV_SRC) trace=$TR RUN_TIMEOUT=$RUN_TIMEOUT"
LOCK=$PDS_REPO/cases/runs/psc5_init.lockdir
(
  until mkdir $LOCK 2>/dev/null; do sleep 10; done
  echo "init lock acquired $(date +%T)"
  timeout ${RUN_TIMEOUT} bash bin/pds-run-case.sbatch "$C" "$OV" &
  PID=$!
  B=$(basename $C)
  while kill -0 $PID 2>/dev/null; do
    # only a run directory of THIS submission (stamp >= START_STAMP), once its MATLAB init is over
    NEWD=$(ls -d cases/runs/${B}_2* 2>/dev/null | sort | tail -1)
    if [[ -n "$NEWD" && ! "${NEWD##*/${B}_}" < "$START_STAMP" ]] && \
       command grep -qs "Start closed loop" "$NEWD/instances/magnetic_controller/stdout.txt"; then break; fi
    sleep 10
  done
  sleep 30
  rmdir $LOCK; echo "init lock released $(date +%T)"
  wait $PID; echo "pds-run-case rc=$?"
)
B=$(basename $C)
RUN_DIR_V=$(ls -d "$PDS_REPO/cases/runs/${B}"_2* 2>/dev/null | sort | tail -1)
RUN_STAMP=${RUN_DIR_V##*/${B}_}
if [[ -z "$RUN_DIR_V" || ! -d "$RUN_DIR_V" || "$RUN_STAMP" < "$START_STAMP" ]]; then
  echo "=== RUN $V end $(date +%T): no run directory cases/runs/${B}_<stamp> newer than $START_STAMP (found: ${RUN_DIR_V:-none})"
  echo ISOFLUX_DONE; exit 1
fi
echo "=== RUN $V end $(date +%T) run_dir=$RUN_DIR_V isoflux_log.csv rows: $(($(wc -l < "$RUN_DIR_V/isoflux_log.csv" 2>/dev/null || echo 1) - 1))"
echo ISOFLUX_DONE
