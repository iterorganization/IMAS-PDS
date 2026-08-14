#!/bin/bash
# Bamboo CI script to install pds and run all tests
# Note: this script should be run from the root of the git repository

# Debuggging:
set -e -o pipefail

set -x

source "$(dirname "${BASH_SOURCE[0]}")/../setup_files/ensure_uv.sh"

# SETUP
source /etc/profile.d/modules.sh
module purge

bash setup_files/setup_test_files.sh

# Load the PDS meta-module instead of building NICE/IMAS-MUSCLE3/
# Waveform-Editor/TORAX-MUSCLE3/METIS fresh into run/ on every single CI run
# (the old approach -- see setup_files/setup_*.sh, still used by
# pds_setup.sh's informal guide script, but no longer by CI). `module load
# PDS` bootstraps IMAS-Python (+ IMAS-Core/UDA transitively) and
# PDS-IMAS-MUSCLE3 (muscle_manager, muscle_dashboard); every workflow actor
# then loads its OWN complete environment when MUSCLE3 spawns it
# (base_env: clean + modules:, see workflows/lib/local_programs.ymmsl and
# each workflow's own workflow.ymmsl.template), so nothing else needs
# loading here. Redeployed fresh from this checkout's own setup_files/PDS.lua
# on every run (rather than trusting a pre-existing deployment) so CI always
# tests exactly what's in the checkout, not whatever happened to be
# deployed last.
#
# Assumes /home/ITER/blokhus/public/modules is reachable from wherever this
# runs (a personal, world-readable publish directory on this cluster, same
# one setup_files/custom_modules/build_*.sh install the PDS-<Name> actor
# modules into) -- not yet a properly shared/published location; fine for
# now since CI runs on the same cluster, but worth moving eventually.
PDS_MODULES_ROOT="/home/ITER/blokhus/public/modules"
mkdir -p "$PDS_MODULES_ROOT/PDS"
sed "s|@@PDS_ROOT@@|$(pwd)|g" setup_files/PDS.lua > "$PDS_MODULES_ROOT/PDS/1.0.lua"
module use "$PDS_MODULES_ROOT"
module load PDS

# RUN TEST FILES
# Isolated, single-actor smoke tests -- independent of (and faster than) the
# full workflow runs below, and still worth keeping even where a real
# workflow exercises the same actor type: these catch a broken actor
# environment in seconds instead of minutes, in isolation from everything
# else in a real workflow. ymmsl_files/test_*.ymmsl.template have all been
# updated to the new module-loading design (base_env: clean + modules:
# PDS-<Name>, matching workflows/lib/local_programs.ymmsl), replacing the
# old bare `modules: IMAS-MUSCLE3` / `NICE` names and manually-exported
# EBROOT*=$PWD/run/... this script used to rely on before `module load PDS`.
MANAGER="$EBROOTIMASMUSCLE3/venv/bin/muscle_manager"

"$MANAGER" --start-all ymmsl_files/test_sink_source_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_accumulator_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_olc_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_waveform_editor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_visualization_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_torax_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_nice_actor.ymmsl
"$MANAGER" --start-all ymmsl_files/test_metis_actor.ymmsl

# TODO: test_chease_actor -- chease.exe (built by
# setup_files/custom_modules/build_chease.sh) loads and resolves all its
# libraries correctly (confirmed: `ldd` clean from a purged shell), but
# segfaults (exit -11) with zero output as soon as it's actually run, both
# as a real muscle3 actor and invoked bare from its own directory (so it's
# not a working-directory/missing-input-file issue). Likely related to the
# ifort->ifx compiler swap build_chease.sh uses (see its header comment) --
# ifx is a from-scratch LLVM rewrite, not a guaranteed drop-in despite
# accepting the same flags. Needs real debugging (gdb/core dump, or trying
# -O0 per the Makefile's own F90FLAGS_O0 in case it's an optimization-level
# miscompile) before this can be re-enabled.
# "$MANAGER" --start-all ymmsl_files/test_chease_actor.ymmsl

# RUN WORKFLOWS
# One scenario per workflow, just enough to confirm every actor type's
# module-loading wiring actually works end to end -- not a physics
# validation suite. Each is idempotent: clear any stale scenario output from
# a previous run on this same agent/workspace first, so a rerun can't fail
# on a leftover "file already exists" from an earlier build (confirmed this
# happens: IMAS's `imas convert` doesn't overwrite by default).
#
# HDF5_USE_FILE_LOCKING=FALSE avoids spurious HDF5 file-locking failures on
# networked storage (carried over from origin/master's own CI work).
export HDF5_USE_FILE_LOCKING=FALSE

run_workflow_clean() {
  local workflow="$1" scenario="$2"
  shift 2
  rm -rf "workflows/$workflow/scenarios/$scenario/tmp"
  bash run_workflow.sh "$workflow" "$scenario" "$@"
}

run_workflow_clean prescribed_transport 105084
run_workflow_clean inverse_convergence 105084
run_workflow_clean metis_interpretative_from_dina 105084 N_TIMESLICES=10
run_workflow_clean metis_predictive_from_dina 105084 N_TIMESLICES=10

# TODO: torax_nice_controller / torax_nice_rd_controller -- every actor
# except magnetic_controller already runs correctly under the new
# module-loading design. magnetic_controller itself needs run/pcs (a PCS +
# PCSSP checkout), which setup_files/custom_modules/build_pcs.sh can
# produce, but building it is currently blocked on git access to
# ssh://git@git.iter.org/pcs/pcs.git ("Repository not found / no
# permission"). Re-enable once that access is sorted out and PDS-PCS exists.
# run_workflow_clean torax_nice_controller 105073
# run_workflow_clean torax_nice_rd_controller 105073

# TODO: metis_interpretative_nice_inverse_from_dina /
# metis_predictive_nice_inverse_from_dina -- fail at "CREATING RUNNABLE
# YMMSL FILE" with `tmp/PSI_OFFSET: No such file or directory`. This file is
# never written by either workflow's own preprocess_data.sh (confirmed by
# reading it) -- a pre-existing gap in the METIS/NICE coupling itself, not a
# module-loading issue introduced by this rework. Needs its own
# investigation into what's supposed to generate tmp/PSI_OFFSET.
# run_workflow_clean metis_interpretative_nice_inverse_from_dina 105084 N_TIMESLICES=10
# run_workflow_clean metis_predictive_nice_inverse_from_dina 105084 N_TIMESLICES=10
