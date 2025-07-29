# NOTE:
# This is only a means to guide users in the right way,
# not a maintained install script.

# For use on SDCC
# User needs to have access to:
# github.com:iterorganization/IMAS-muscle3.git
# gitlab.inria.fr:blfauger/nice.git
# git.iter.org/scen/metis.git
# git.iter.org/scen/torax-m3.git
# git.iter.org/scen/pds.git

# installation guides
# https://git.iter.org/projects/SCEN/repos/pds/browse
# https://github.com/iterorganization/IMAS-muscle3
# https://github.com/iterorganization/Waveform-Editor
# https://git.iter.org/projects/SCEN/repos/metis/browse/doc/METIS_installation_guide.pdf
# https://gitlab.inria.fr/blfauger/nice/-/wikis/home
# https://torax.readthedocs.io/en/latest/installation.html

INSTALL_PDS="true"
INSTALL_IMAS_MUSCLE3="true"
INSTALL_WAVEFORM_EDITOR="true"
INSTALL_METIS="true"
INSTALL_NICE="true"
INSTALL_TORAX="true"
INSTALL_CHEASE="true"

BRANCH_PDS='feature/sdcc_install_instructions'
BRANCH_IMAS_MUSCLE3='main'
BRANCH_WAVEFORM_EDITOR='main'
BRANCH_METIS='muscle3'
BRANCH_NICE='master'
BRANCH_TORAX='feature/muscle3_actor'
BRANCH_CHEASE='feature/muscle3'

# MODULE LOAD
pip install --upgrade pip
pip install --upgrade setuptools wheel

# SET UP PDS
if [ "$INSTALL_PDS" = "true" ]; then
  echo "############## INSTALLING PDS ##############"
  bash setup_test_files.bash
  echo "############## FINISHED PDS ##############"
fi

cd run/

# SET UP IMAS-M3
if [ "$INSTALL_IMAS_MUSCLE3" = "true" ] && [ ! -d "IMAS-muscle3" ]; then
  echo "############## INSTALLING IMAS-MUSCLE3 ##############"
  source imas_base_env
  module load IDS-Validator
  git clone git@github.com:iterorganization/IMAS-muscle3.git
  cd IMAS-muscle3
  git checkout $BRANCH_IMAS_MUSCLE3
  python3 -m venv ./venv
  . venv/bin/activate
  pip install -e .
  deactivate
  module purge
  cd ..
  echo "############## FINISHED IMAS-MUSCLE3 ##############"
fi

# SET UP WAVEFORM-EDITOR
if [ "$INSTALL_WAVEFORM_EDITOR" = "true" ] && [ ! -d "Waveform-Editor" ]; then
  echo "############## INSTALLING WAVEFORM-EDITOR ##############"
  source imas_base_env
  git clone git@github.com:iterorganization/Waveform-Editor.git
  cd Waveform-Editor
  git checkout $BRANCH_WAVEFORM_EDITOR
  python3 -m venv ./venv
  . venv/bin/activate
  pip install -e .[muscle3]
  deactivate
  module purge
  cd ..
  echo "############## FINISHED IMAS-MUSCLE3 ##############"
fi

# SET UP METIS
if [ "$INSTALL_METIS" = "true" ] && [ ! -d "metis" ]; then
  echo "############## INSTALLING METIS ##############"
  git clone ssh://git@git.iter.org/scen/metis.git
  cd metis
  git checkout $BRANCH_METIS
  matlab -nodisplay -batch zineb_path
  cd ..
  echo "############## FINISHED METIS ##############"
fi

# SET UP NICE
if [ "$INSTALL_NICE" = "true" ] && [ ! -d "nice" ]; then
  echo "############## INSTALLING NICE ##############"
  source imas_base_env
  module load SuiteSparse/7.7.0-intel-2023b
  module load libxml2
  git clone git@gitlab.inria.fr:blfauger/nice.git
  cd nice
  git checkout $BRANCH_NICE
  git submodule init
  git submodule update
  cp run/iwrap/param/inv/iter/param.x* run/input
  cp run/iwrap/param/xsd/param.x* run/input
  # sed -i "s|always_save_grids_gdd = true|always_save_grids_gdd = false|" "src/nice_imas.cc"
  cd src
  cp Makefile.TEMPLATE Makefile
  make -j nice_imas_inv_muscle3
  make -j nice_imas_dir_muscle3
  make -j nice_imas_evo_muscle3
  module purge
  cd ../..
  echo "############## FINISHED NICE ##############"
fi

# SET UP TORAX
if [ "$INSTALL_TORAX" = "true" ] && [ ! -d "torax" ]; then
  echo "############## INSTALLING TORAX ##############"
  source torax_base_env
  git clone ssh://git@github.com/mikesndrs/torax.git
  cd torax
  git checkout $BRANCH_TORAX
  python -m venv ./venv
  . venv/bin/activate
  pip install --upgrade pip
  pip install build
  pip install 'numpy > 2'
  pip install 'imas-python @ git+ssh://git@github.com/mikesndrs/imas-python.git@feature/enable-numpy-2.0'
  pip install 'imas_core @ git+ssh://git@git.iter.org/imas/al-core.git@develop'
  pip install -e .[dev,muscle3]
  deactivate
  module purge
  cd ..
  echo "############## FINISHED TORAX ##############"
fi

# SET UP CHEASE
if [ "$INSTALL_CHEASE" = "true" ] && [ ! -d "chease" ]; then
  echo "############## INSTALLING CHEASE ##############"
  # source imas_base_env
  git clone ssh://git@gitlab.epfl.ch:spc/chease.git
  cd chease
  git checkout $BRANCH_CHEASE
  cd python
  source config_muscle3.sh
  cd ..
  ./build_imas.csh
  iwrap -f iwrap/chease_choices_M3.yaml -i $PWD
  mv chease chease_m3

  cd chease_m3
  sed -i "s|<cocos_in>[0-9]\+</cocos_in>|<cocos_in>17</cocos_in>|" "input/chease_input_choices.xml"
  sed -i "s|<cocos_out>[0-9]\+</cocos_out>|<cocos_out>17</cocos_out>|" "input/chease_input_choices.xml"
  rm bin/chease.exe
  make
  cd ..

  cd ..
  echo "############## FINISHED CHEASE ##############"
fi

cd ..

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

