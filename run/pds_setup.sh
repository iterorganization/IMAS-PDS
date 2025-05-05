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
# https://github.com/iterorganization/IMAS-muscle3
# https://gitlab.inria.fr/blfauger/nice/-/wikis/home
# https://git.iter.org/projects/SCEN/repos/metis/browse/doc/METIS_installation_guide.pdf
# https://torax.readthedocs.io/en/latest/installation.html
# https://git.iter.org/projects/SCEN/repos/pds/browse

# works for:
#  torax_m3 - e5858a7e825b7b1ff24eb4943d748192e345d4a1
#  torax    - 9bc36562370448020409507eca2ac1f7ddd1bddf

# MODULE LOAD
pip install --upgrade pip
pip install --upgrade setuptools wheel

INSTALL_PDS=true
INSTALL_IMAS_MUSCLE3=true
INSTALL_METIS=true
INSTALL_NICE=true
INSTALL_TORAX=true

# SET UP PDS
if [ "$INSTALL_PDS" == true ]; then
  echo "############## INSTALLING PDS ##############"
  source imas_base_env
  git clone ssh://git@git.iter.org/scen/pds.git
  cd pds
  git checkout feature/sdcc_install_instructions
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
if [ "$INSTALL_IMAS_MUSCLE3" == true ]; then
  echo "############## INSTALLING IMAS-MUSCLE3 ##############"
  source imas_base_env
  module load IDS-Validator
  git clone git@github.com:iterorganization/IMAS-muscle3.git
  cd IMAS-muscle3
  git checkout readme
  python3 -m venv ./venv
  . venv/bin/activate
  pip install -e .
  deactivate
  module purge
  cd ..
  echo "############## FINISHED IMAS-MUSCLE3 ##############"
fi

# SET UP METIS
if [ "$INSTALL_METIS" == true ]; then
  echo "############## INSTALLING METIS ##############"
  source imas_base_env
  module load MATLAB
  module load GCC
  git clone ssh://git@git.iter.org/scen/metis.git
  cd metis
  git checkout muscle3
  python3 -m venv ./venv
  # . venv/bin/activate
  # matlab -nodisplay -nosplash -r "make_metis_linux; exit"
  # deactivate
  cd ..
  module purge
  echo "############## FINISHED METIS ##############"
fi

# SET UP NICE
if [ "$INSTALL_NICE" == true ]; then
  echo "############## INSTALLING NICE ##############"
  source imas_base_env
  module load SuiteSparse/7.7.0-intel-2023b
  module load libxml2
  git clone git@gitlab.inria.fr:blfauger/nice.git
  cd nice
  git submodule init
  git submodule update
  git checkout develop            # For now change to develop branch, otherwise next command won't work
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
if [ "$INSTALL_TORAX" == true ]; then
  echo "############## INSTALLING TORAX-M3 ##############"
  source torax_base_env
  git clone ssh://git@git.iter.org/scen/torax-m3.git
  cd torax-m3
  # git checkout feature/muscle3_actor
  git checkout e5858a7e825b7b1ff24eb4943d748192e345d4a1
  python -m venv ./venv
  . venv/bin/activate
  pip install --upgrade pip
  pip install build
  pip install 'numpy > 2'
  pip install 'imas-python @ git+ssh://git@github.com/mikesndrs/imas-python.git@feature/enable-numpy-2.0'
  pip install 'imas_core @ git+ssh://git@git.iter.org/imas/al-core.git@develop'
  # pip install 'torax @ git+ssh://git@github.com/mikesndrs/torax.git@feature/IMAS_coupling'
  pip install 'torax @ git+ssh://git@github.com/mikesndrs/torax.git@9bc36562370448020409507eca2ac1f7ddd1bddf'
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

