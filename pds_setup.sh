# NOTE:
# This is only a means to guide users in the right way,
# not a maintained install script.
#
# IMAS-MUSCLE3, muscle3-dashboard, Waveform-Editor, NICE, TORAX-MUSCLE3, and
# METIS are no longer installed by this script -- each now has a shared
# PDS-<Name> module instead of a per-checkout clone (see
# setup_files/custom_modules/build_*.sh and setup_files/PDS.lua for why:
# RPATH/PYTHONPATH conflicts rule out the official SDCC modules for these).
# `module load PDS` is enough to use any of them; nothing here to run first.
# (muscle3-dashboard specifically comes for free with PDS-IMAS-MUSCLE3 --
# IMAS-MUSCLE3's own pyproject.toml declares it as a core dependency, so a
# separate install here would risk overwriting that correct install with an
# incomplete one, see build_imas_muscle3.sh's header comment.)
#
# CHEASE also has a PDS-CHEASE module now (same build_chease.sh), but it's
# not a drop-in replacement for this script's old setup_chease.sh: that
# script sources CHEASE's own upstream python/config_muscle3.sh unmodified,
# which is *already* broken on this cluster today (mixes intel-2023b/2025b,
# `ifort: command not found` -- see build_chease.sh's header comment for the
# full story) regardless of whether this script is used. PDS-CHEASE's
# chease.exe builds successfully but currently segfaults at runtime -- known,
# unresolved (see ci/run_test_workflows.sh's TODO for test_chease_actor).
#
# PCS has no working module yet: setup_files/custom_modules/build_pcs.sh
# exists, but building it is blocked on git access to
# ssh://git@git.iter.org/pcs/pcs.git ("Repository not found / no
# permission"). setup_files/setup_pcs.sh below remains the only currently
# working path for anyone with proper access.
#
# installation guides
# https://github.com/iterorganization/IMAS-PDS

INSTALL_PDS="true"
INSTALL_PCS="true"

BRANCH_PDS='master'
BRANCH_PCS='master'

is_sourced() {
  [[ "${BASH_SOURCE[0]}" != "$0" ]]
}

if is_sourced; then
  echo "Please run this script using bash:"
  echo "'bash pds_setup.sh'"
  echo "Do not source it."
  return 1
fi

set -euo pipefail # stop if anything doesn't work

CURR_INSTALL='START'
(
  trap 'printf "INSTALLATION RAN INTO PROBLEM [$CURR_INSTALL]:\n\"$BASH_COMMAND\" (line $LINENO)\n REMOVE DIRECTORY BEFORE TRYING AGAIN"' ERR

  # SET UP PDS
  CURR_INSTALL='PDS FILES'
  if [ "$INSTALL_PDS" = "true" ]; then
    echo "############## INSTALLING PDS ##############"
    bash setup_files/setup_test_files.sh
    echo "############## FINISHED PDS ##############"
  fi

  cd run/

  # SET UP PCS
  CURR_INSTALL='PCS'
  PCS_URL="ssh://git@git.iter.org/pcs/pcs.git"
  if [ "$INSTALL_PCS" = "true" ] \
    && [ ! -d "pcs" ] \
    && git ls-remote "$PCS_URL" &>/dev/null; then
    echo "############## INSTALLING PCS ##############"
    bash ../setup_files/setup_pcs.sh $PCS_URL $BRANCH_PCS
    echo "############## FINISHED PCS ##############"
  else
    echo "Skipping PCS"
  fi

  cd ..
)

# END MESSAGE
echo 'YOU CAN TRY OUT THE TEST COUPLINGS IN THE PDS/YMMSL_FILES DIRECTORY BY RUNNING'
echo ''
echo 'module use /home/ITER/blokhus/public/modules && module load PDS'
echo ''
echo 'AND'
echo ''
echo 'muscle_manager --start-all ymmsl_files/path/to/my/file.ymmsl'
echo ''
echo 'MAKE SURE TO CHANGE ANY RELAVANT FILE PATHS IN THE YMMSL FILES!'

