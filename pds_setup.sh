# NOTE:
# This is only a means to guide users in the right way,
# not a maintained install script.

# For use on SDCC
# User needs to have access to:
# github.com:iterorganization/IMAS-MUSCLE3.git
# gitlab.inria.fr:blfauger/nice.git
# git.iter.org/scen/metis.git
# git.iter.org/scen/torax-m3.git
# git.iter.org/scen/pds.git

# installation guides
# https://git.iter.org/projects/SCEN/repos/pds/browse
# https://github.com/iterorganization/IMAS-MUSCLE3
# https://github.com/iterorganization/Waveform-Editor
# https://git.iter.org/projects/SCEN/repos/metis/browse/doc/METIS_installation_guide.pdf
# https://gitlab.inria.fr/blfauger/nice/-/wikis/home
# https://torax.readthedocs.io/en/latest/installation.html

INSTALL_PDS="true"
INSTALL_IMAS_MUSCLE3="false"
INSTALL_WAVEFORM_EDITOR="true"
INSTALL_METIS="true"
INSTALL_NICE="false"
INSTALL_TORAX="true"
INSTALL_CHEASE="true"
INSTALL_PCS="true"

BRANCH_PDS='master'
BRANCH_IMAS_MUSCLE3='develop'
BRANCH_WAVEFORM_EDITOR='main'
BRANCH_METIS='muscle3_develop'
BRANCH_NICE='master'
BRANCH_TORAX='develop'
BRANCH_CHEASE='feature/muscle3'
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

  # TODO: turn off install arg when easybuild module available

  # MODULE LOAD
  pip install --upgrade pip
  pip install --upgrade setuptools wheel

  # SET UP PDS
  CURR_INSTALL='PDS FILES'
  if [ "$INSTALL_PDS" = "true" ]; then
    echo "############## INSTALLING PDS ##############"
    bash setup_files/setup_test_files.sh
    echo "############## FINISHED PDS ##############"
  fi

  cd run/

  # SET UP IMAS-M3
  CURR_INSTALL='IMAS-MUSCLE3'
  IMAS_MUSCLE3_URL="https://github.com/iterorganization/IMAS-MUSCLE3.git"
  if [ "$INSTALL_IMAS_MUSCLE3" = "true" ] \
    && [ ! -d "IMAS-MUSCLE3" ] \
    && git ls-remote "$IMAS_MUSCLE3_URL" &>/dev/null; then
    echo "############## INSTALLING IMAS-MUSCLE3 ##############"
    bash ../setup_files/setup_imas_muscle3.sh $IMAS_MUSCLE3_URL $BRANCH_IMAS_MUSCLE3
    echo "############## FINISHED IMAS-MUSCLE3 ##############"
  else
    echo "Skipping IMAS_MUSCLE3"
  fi

  # SET UP WAVEFORM-EDITOR
  CURR_INSTALL='WAVEFORM-EDITOR'
  WAVEFORM_EDITOR_URL="https://github.com/iterorganization/Waveform-Editor.git"
  if [ "$INSTALL_WAVEFORM_EDITOR" = "true" ] \
    && [ ! -d "Waveform-Editor" ] \
    && git ls-remote "$WAVEFORM_EDITOR_URL" &>/dev/null; then
    echo "############## INSTALLING WAVEFORM-EDITOR ##############"
    bash ../setup_files/setup_waveform_editor.sh $WAVEFORM_EDITOR_URL $BRANCH_WAVEFORM_EDITOR
    echo "############## FINISHED WAVEFORM-EDITOR ##############"
  else
    echo "Skipping WAVEFORM_EDITOR"
  fi

  # SET UP METIS
  CURR_INSTALL='METIS'
  METIS_URL="ssh://git@git.iter.org/scen/metis.git"
  if [ "$INSTALL_METIS" = "true" ] \
    && [ ! -d "metis" ] \
    && git ls-remote "$METIS_URL" &>/dev/null; then
    echo "############## INSTALLING METIS ##############"
    bash ../setup_files/setup_metis.sh $METIS_URL $BRANCH_METIS
    echo "############## FINISHED METIS ##############"
  else
    echo "Skipping METIS"
  fi

  # SET UP NICE
  CURR_INSTALL='NICE'
  NICE_URL="https://gitlab.inria.fr/blfauger/nice.git"
  if [ "$INSTALL_NICE" = "true" ] \
    && [ ! -d "nice" ] \
    && git ls-remote "$NICE_URL" &>/dev/null; then
    echo "############## INSTALLING NICE ##############"
    bash ../setup_files/setup_nice.sh $NICE_URL $BRANCH_NICE
    echo "############## FINISHED NICE ##############"
  else
    echo "Skipped NICE"
  fi

  # SET UP TORAX
  CURR_INSTALL='TORAX-MUSCLE3'
  TORAX_URL=https://github.com/iterorganization/TORAX-MUSCLE3.git
  if [ "$INSTALL_TORAX" = "true" ] \
    && [ ! -d "TORAX-MUSCLE3" ] \
    && git ls-remote "$TORAX_URL" &>/dev/null; then
    echo "############## INSTALLING TORAX ##############"
    bash ../setup_files/setup_torax.sh $TORAX_URL $BRANCH_TORAX
    echo "############## FINISHED TORAX ##############"
  else
    echo "Skipped TORAX"
  fi

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

  # SET UP CHEASE
  CURR_INSTALL='CHEASE'
  CHEASE_URL="https://gitlab.epfl.ch/spc/chease.git"
  if [ "$INSTALL_CHEASE" = "true" ] \
    && [ ! -d "chease" ] \
    && git ls-remote "$CHEASE_URL" &>/dev/null; then
    echo "############## INSTALLING CHEASE ##############"
    bash ../setup_files/setup_chease.sh $CHEASE_URL $BRANCH_CHEASE
    echo "############## FINISHED CHEASE ##############"
  else
    echo 'Skipping CHEASE'
  fi

  cd ..
)

# END MESSAGE
echo 'YOU CAN TRY OUT THE TEST COUPLINGS IN THE PDS/YMMSL_FILES DIRECTORY BY RUNNING'
echo ''
echo 'cd run'
echo ''
echo 'AND'
echo ''
echo 'muscle_manager --start-all path/to/my/file.ymmsl'
echo ''
echo 'MAKE SURE TO CHANGE ANY RELAVANT FILE PATHS IN THE YMMSL FILES!'

