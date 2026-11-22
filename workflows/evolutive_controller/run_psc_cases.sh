#!/bin/bash
# evolutive_controller 105073 with the Pulse Supervision Controller (PSC) and the MCLS (Magnetic Control Local
# Supervisor) in the controller actor: launcher of the case ip_story_mockup. The controller program is
# magnetic_controller_psc (workflows/lib/local_programs.ymmsl: the usual init muscle_controller_NICE_IMAS_iter_init.m,
# with the PSC added by the init when psc_enabled = 1; with mcls_enabled = 1 the init runs
# controllers/CCS/pcssp_controller_and_ps_mcls.slx, built once by controllers/CCS/mcls/model_build/build_mcls_controller.sh).
# The case settings otherwise (1 ms exchange, VS1+VS3, PS model). VARIANT =
#   ip_story_mockup  scenario story 105073 with the MCLS (cases/input/psc/ip_story_mockup/README.md): window
#                    115.817598 -> 138.0 s, three MCLS modes, gap control dispatched by the MCLS;
#                    overlay cases/overrides/evolutive_controller_105073_ip_story_mockup.ymmsl;
#                    case folder cases/evolutive_controller_105073_ip_story_mockup
# Options (environment variables):
#   SHORT_WINDOW=1   smoke check of ip_story_mockup on a 0.2 s window (115.817598 -> 116.02 s: torax.t_final =
#                    nice_evo_rd.t_end = 116.02 s, written into the case folder as smoke_window.ymmsl): checks that the
#                    model initialises and exchanges with NICE; case folder cases/evolutive_controller_105073_ip_story_mockup_smoke
#   DRY_RUN=1        login node, no Slurm: builds the case folder, expands the overlays and generates the workflow, then
#                    stops before the lock and the run
#   RUN_TIMEOUT=<s>  time limit of the run inside the job (default 10800 s = 3 h: 22.2 s of plasma at ~6.5 min of wall
#                    time per plasma second = 2.4 h, plus ~10 min of MATLAB/PSC init and the post-processing;
#                    5100 s with SHORT_WINDOW=1)
# MATLAB controller inits are serialised with a mkdir lock (cases/runs/psc5_init.lockdir, shared with
# controllers/CCS/mcls/model_build/build_mcls_controller.sh: the inits regenerate the same PCS *.sldd).
#SBATCH -J psc_evo
#SBATCH --partition=all
#SBATCH --time=03:30:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=24 --mem=96G
#SBATCH -o cases/runs/psc_logs/psc_evo_%x_%j.log
# The -o path is relative to the submission directory and its folder must exist:
#   mkdir -p <repo>/cases/runs/psc_logs
#   sbatch --chdir=<repo> --export=ALL,PDS_REPO=<repo>,VARIANT=ip_story_mockup workflows/evolutive_controller/run_psc_cases.sh
# The 03:30:00 above covers RUN_TIMEOUT (3 h) plus the job set-up; the smoke check fits in --time=01:30:00:
#   sbatch --time=01:30:00 --chdir=<repo> --export=ALL,PDS_REPO=<repo>,VARIANT=ip_story_mockup,SHORT_WINDOW=1 workflows/evolutive_controller/run_psc_cases.sh
# Dry run:  DRY_RUN=1 VARIANT=ip_story_mockup PDS_REPO=<repo> bash workflows/evolutive_controller/run_psc_cases.sh
# The case override holds ${PDS_REPO} (repo root) and ${CASE_DIR} (case folder) placeholders: they are expanded
# below (envsubst, as bin/pds-create-case does) into the case folder before muscle_manager sees them.
# After the run a non-fatal summary of RUN_DIR/simulink_log.csv (the controller logs the four PSC columns psc_segment /
# psc_ip_too_high / psc_end_of_flux / psc_z_excursion there) and of RUN_DIR/mcls_log.csv (ControlModeIndex /
# ForceControlMode changes) is printed.
set -uo pipefail
# Repo root: an exported PDS_REPO, else the sbatch submission directory (sbatch copies this script to the
# spool, so BASH_SOURCE cannot locate the repo there), else this file's location (workflows/evolutive_controller).
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
VARIANTS="ip_story_mockup"
V=${VARIANT:?VARIANT must be one of: $VARIANTS}
DRY_RUN=${DRY_RUN:-0}
SHORT_WINDOW=${SHORT_WINDOW:-0}
OVD=$PDS_REPO/cases/overrides
# per variant: case input folder, overlays, MCLS or not, default timeout of the run (s), case folder
case $V in
  ip_story_mockup)
    IN=cases/input/psc/ip_story_mockup;  OVS=(evolutive_controller_105073_ip_story_mockup.ymmsl);  RT=10800; MCLS=1
    C=cases/evolutive_controller_105073_ip_story_mockup ;;
  *) echo "unknown VARIANT $V ($VARIANTS)"; exit 1 ;;
esac
if [[ $SHORT_WINDOW != 0 ]]; then
  RT=5100; C=${C}_smoke
fi
RUN_TIMEOUT=${RUN_TIMEOUT:-$RT}
REQ=("$OVD/${OVS[0]}" "$IN/psc_config/PS.xml" "$IN/psc_config/BTree.xml" "$IN/psc_config/PSCGlobalMonConfig.xml"
     "$IN/psc_config/PSCIntConfig.xml")
[[ $MCLS == 1 ]] && REQ+=(controllers/CCS/pcssp_controller_and_ps_mcls.slx controllers/CCS/mcls/mcls_library_defaults.yaml
                          "$IN/mcls_table.yaml")
for f in "${REQ[@]}"; do
  [[ -f $f ]] || { echo "$f missing (case inputs: $IN/README.md; MCLS model: controllers/CCS/mcls/model_build/build_mcls_controller.sh)"; exit 1; }
done
[[ -f cases/runs/inverse_convergence_105073/out_nice/equilibrium.h5 ]] || { echo "cases/runs/inverse_convergence_105073/out_nice/equilibrium.h5 missing (warm-start trace of source)"; exit 1; }
# fresh case folder (a copy of the base case, rebuilt at every call)
rm -rf "$C"; cp -a cases/evolutive_controller_105073 "$C"
export CASE_DIR="$PDS_REPO/$C"
OV=()
for f in "${OVS[@]}"; do envsubst '${PDS_REPO} ${CASE_DIR}' < "$OVD/$f" > "$C/$f"; OV+=("$C/$f"); done
if [[ $SHORT_WINDOW != 0 ]]; then
  # 0.2 s smoke window on top of the case settings (later overlays win)
  printf 'ymmsl_version: v0.2\n# 0.2 s smoke window written by run_psc_cases.sh (115.817598 -> 116.02 s)\nsettings:\n  torax.t_final: 116.02\n  nice_evo_rd.t_end: 116.02\n' > "$C/smoke_window.ymmsl"
  OV+=("$C/smoke_window.ymmsl")
fi
python workflows/evolutive_controller/make_psc_workflow.py workflows/evolutive_controller/workflow.ymmsl "$C/workflow.ymmsl" || exit 1
echo "VARIANT=$V MCLS=$MCLS SHORT_WINDOW=$SHORT_WINDOW RUN_TIMEOUT=$RUN_TIMEOUT overlays=${OV[*]} case input=$IN"
if [[ "$DRY_RUN" != 0 ]]; then
  for o in "${OV[@]}"; do echo "=== DRY RUN: expanded overlay $o (settings only)"; command grep -v '^ *#' "$o"; done
  echo "=== DRY RUN: paths named in the expanded overlay"
  command grep -o '"[^"]*"' "$C/${OVS[0]}" | tr -d '"' | while read -r p; do
    if [[ -d $p ]]; then echo "DIR  $p ($(ls "$p" | wc -l) entries)"; elif [[ -f $p ]]; then echo "FILE $p ($(stat -c %s "$p") bytes)"; else echo "MISSING $p"; fi
  done
  echo "=== DRY RUN: controller implementation in $C/workflow.ymmsl"
  command grep -n "magnetic_controller_psc" "$C/workflow.ymmsl"
  echo "DRY RUN done (nothing submitted, nothing run)"; exit 0
fi
# stamp taken before the run: the dated run directory created by pds-run-case.sbatch (cases/runs/<case>_<YYYYmmdd_HHMMSS>)
# must not be older than it, so an earlier run of the same case is never summarised by mistake
START_STAMP=$(date +%Y%m%d_%H%M%S)
echo "=== RUN $V start $(date +%T) overlays=${OV[*]}"
LOCK=$PDS_REPO/cases/runs/psc5_init.lockdir
(
  until mkdir $LOCK 2>/dev/null; do sleep 10; done
  echo "init lock acquired $(date +%T)"
  timeout ${RUN_TIMEOUT} bash bin/pds-run-case.sbatch "$C" "${OV[@]}" &
  PID=$!
  B=$(basename $C)
  while kill -0 $PID 2>/dev/null; do
    # only a run directory of THIS submission (stamp >= START_STAMP): in the first seconds the new directory does not
    # exist yet and the newest one may be an earlier run that already contains "Start closed loop" (the lock would
    # then be released after 30 s instead of after the MATLAB init)
    NEWD=$(ls -d cases/runs/${B}_2* 2>/dev/null | sort | tail -1)
    if [[ -n "$NEWD" && ! "${NEWD##*/${B}_}" < "$START_STAMP" ]] && \
       command grep -qs "Start closed loop" "$NEWD/instances/magnetic_controller/stdout.txt"; then break; fi
    sleep 10
  done
  sleep 30
  rmdir $LOCK; echo "init lock released $(date +%T)"
  wait $PID; echo "pds-run-case rc=$?"
)
# The convenience symlink cases/runs/<case> is created by bin/pds-run-case.sbatch only after a successful run:
# use the newest dated run directory of this case instead (exists from the start of the run, so the summary
# below also runs after an aborted simulation).
B=$(basename $C)
RUN_DIR_V=$(ls -d "$PDS_REPO/cases/runs/${B}"_2* 2>/dev/null | sort | tail -1)
RUN_STAMP=${RUN_DIR_V##*/${B}_}
if [[ -z "$RUN_DIR_V" || ! -d "$RUN_DIR_V" || "$RUN_STAMP" < "$START_STAMP" ]]; then
  echo "=== RUN $V end $(date +%T): no run directory cases/runs/${B}_<stamp> newer than $START_STAMP (found: ${RUN_DIR_V:-none}); no summary"
  echo PSC_EVO_DONE; exit 1
fi
echo "=== RUN $V end $(date +%T) run_dir=$RUN_DIR_V"
# --- post-run summary (non-fatal; csv module only) ----------------------------------------------------------
echo "=== SUMMARY $V (simulink_log.csv, mcls_log.csv; non-fatal)"
python - "$RUN_DIR_V" "$MCLS" <<'PYEOF' || echo "summary failed (non-fatal)"
import csv, os, sys
run, mcls = sys.argv[1], sys.argv[2] == "1"
def changes(path, cols, tcol):
    """print the (time, value) pairs at which each of the columns changes value"""
    if not os.path.isfile(path):
        print(f"{os.path.basename(path)}: missing"); return
    with open(path, newline="") as fh:
        rdr = csv.reader(fh); hdr = next(rdr)
        idx = {c: hdr.index(c) for c in cols if c in hdr}
        it = hdr.index(tcol) if tcol in hdr else 0
        last = {c: None for c in idx}; n = 0; t0 = t1 = None
        for r in rdr:
            if len(r) != len(hdr): continue
            n += 1; t = float(r[it]); t0 = t if t0 is None else t0; t1 = t
            for c, i in idx.items():
                v = r[i]
                if v != last[c]:
                    if last[c] is not None or n == 1: print(f"  {c}: {v} from t={t:.3f} s")
                    last[c] = v
    print(f"{os.path.basename(path)}: {n} rows, t {t0} -> {t1} s, columns {len(hdr)}; missing of the expected: {[c for c in cols if c not in idx]}")
if mcls:
    changes(os.path.join(run, "mcls_log.csv"), ["ControlModeIndex", "ShapeIpControlMode", "ForceControlMode"], "t_abs")
changes(os.path.join(run, "simulink_log.csv"), ["psc_segment", "psc_end_of_flux", "psc_z_excursion", "psc_ip_too_high"], "t")
PYEOF
echo PSC_EVO_DONE
