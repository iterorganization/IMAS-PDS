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

BRANCH_PDS='feature/sdcc_install_instructions'
BRANCH_IMAS_MUSCLE3='main'
BRANCH_WAVEFORM_EDITOR='main'
BRANCH_METIS='muscle3'
BRANCH_NICE='master'
BRANCH_TORAX='feature/IMAS_coupling'
BRANCH_TORAX_M3='feature/muscle3_actor'

# MODULE LOAD
pip install --upgrade pip
pip install --upgrade setuptools wheel

# SET UP PDS
if [ "$INSTALL_PDS" = "true" ] && [ ! -d "pds" ]; then
  echo "############## INSTALLING PDS ##############"
  source imas_base_env
  git clone ssh://git@git.iter.org/scen/pds.git -b $BRANCH_PDS
  cd pds
  python3 -m venv ./venv
  . venv/bin/activate
  pip install -e .
  deactivate
  module purge
  cd ..
  bash setup_test_files.bash
  echo "############## FINISHED PDS ##############"
fi

# SET UP IMAS-M3
if [ "$INSTALL_IMAS_MUSCLE3" = "true" ] && [ ! -d "IMAS-muscle3" ]; then
  echo "############## INSTALLING IMAS-MUSCLE3 ##############"
  source imas_base_env
  module load IDS-Validator
  git clone git@github.com:iterorganization/IMAS-muscle3.git -b $BRANCH_IMAS_MUSCLE3
  cd IMAS-muscle3
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
  git clone git@github.com:iterorganization/Waveform-Editor.git -b $BRANCH_WAVEFORM_EDITOR
  cd Waveform-Editor
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
  git clone ssh://git@git.iter.org/scen/metis.git -b $BRANCH_METIS
  cd metis
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
  git clone git@gitlab.inria.fr:blfauger/nice.git -b $BRANCH_NICE
  cd nice
  git submodule init
  git submodule update
  cp run/iwrap/param/inv/iter/param.x* run/input
  cp run/iwrap/param/xsd/param.x* run/input
  cd src
  cp Makefile.TEMPLATE Makefile
  make -j nice_imas_inv_muscle3
  make -j nice_imas_dir_muscle3
  make -j nice_imas_evo_muscle3
  module purge
  cd ../..
  echo "############## FINISHED NICE ##############"
fi

# SET UP TORAX-M3
if [ "$INSTALL_TORAX" = "true" ] && [ ! -d "torax-m3" ]; then
  echo "############## INSTALLING TORAX-M3 ##############"
  source torax_base_env
  git clone ssh://git@git.iter.org/scen/torax-m3.git -b $BRANCH_TORAX_M3
  cd torax-m3
  python -m venv ./venv
  . venv/bin/activate
  pip install --upgrade pip
  pip install build
  pip install 'numpy > 2'
  pip install 'imas-python @ git+ssh://git@github.com/mikesndrs/imas-python.git@feature/enable-numpy-2.0'
  pip install 'imas_core @ git+ssh://git@git.iter.org/imas/al-core.git@develop'
  pip install 'torax @ git+ssh://git@github.com/mikesndrs/torax.git@feature/IMAS_coupling'
  pip install muscle3
  pip install -e . --no-deps
  deactivate
  module purge
  cd ..
  echo "############## FINISHED TORAX-M3 ##############"
fi

# END MESSAGE
echo 'You can try out the test couplings in the pds/ymmsl_files directory by running:'
echo ''
echo 'muscle_manager --start-all path/to/my/file.ymmsl'
echo ''
echo 'Make sure to change any relavant file paths in the ymmsl files!'

