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
#  torax_m3 - 6c0ed3915
#  torax    - be3f8c4b1

# ENV VARIABLES
export IMAS_AL_DISABLE_VALIDATE=1
ulimit -s unlimited
unset MPLBACKEND

# MODULE LOAD
pip install --upgrade pip
pip install --upgrade setuptools wheel

module purge
module load Python
module load Boost
module load HDF5
module load libxml2
module load SuiteSparse/7.7.0-intel-2023b
module load IMAS/4.0.0-intel-2023b
module unload IMAS-AL-Python
# module load IMAS-Python
module load MUSCLE3
module load IDS-Validator
module load MATLAB
module load GCC

# SET UP PDS
echo "############## INSTALLING PDS ##############"
git clone ssh://git@git.iter.org/scen/pds.git
cd pds
python3 -m venv ./venv
. venv/bin/activate
pip install 'imas-python @ git+ssh://git@github.com/iterorganization/IMAS-Python.git@develop'
pip install 'imas_core @ git+ssh://git@git.iter.org/imas/al-core.git@develop'
pip install -e .
deactivate
cd ..
 
# SET UP IMAS-M3
echo "############## INSTALLING IMAS-MUSCLE3 ##############"
git clone git@github.com:iterorganization/IMAS-muscle3.git
cd IMAS-muscle3
git checkout readme
python3 -m venv ./venv
pip install 'imas-python @ git+ssh://git@github.com/iterorganization/IMAS-Python.git@develop'
pip install 'imas_core @ git+ssh://git@git.iter.org/imas/al-core.git@develop'
. venv/bin/activate
pip install -e .
deactivate
cd ..

# SET UP METIS
# echo "############## INSTALLING METIS ##############"
# git clone ssh://git@git.iter.org/scen/metis.git
# cd metis
# python3 -m venv ./venv
# . venv/bin/activate
# matlab -nodisplay -nosplash -r "make_metis_linux; exit"
# deactivate
# cd ..

# SET UP NICE
echo "############## INSTALLING NICE ##############"
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
cd ../..

# SET UP TORAX-M3
echo "############## INSTALLING TORAX-M3 ##############"
git clone ssh://git@git.iter.org/scen/torax-m3.git
cd torax-m3
python3 -m venv ./venv
. venv/bin/activate
pip install --upgrade pip
pip install build
pip install 'numpy > 2'
# pip install imas-python
pip install 'imas-python @ git+ssh://git@github.com/iterorganization/IMAS-Python.git@develop'
pip install 'imas_core @ git+ssh://git@git.iter.org/imas/al-core.git@develop'
# pip install 'torax @ git+ssh://git@github.com/mikesndrs/torax.git@feature/IMAS_coupling'
pip install 'torax @ git+ssh://git@github.com/mikesndrs/torax.git@feature/be3f8c4b1'
git checkout 6c0ed3915
pip install -e .
deactivate

# # Install QLKNN_7_11
# git clone https://github.com/google-deepmind/fusion_surrogates.git
# pip install -e ./fusion_surrogates
# export TORAX_QLKNN_MODEL_PATH="$PWD"/fusion_surrogates/fusion_surrogates/models/qlknn_7_11.qlknn
# echo export TORAX_QLKNN_MODEL_PATH="$PWD"/fusion_surrogates/fusion_surrogates/models/qlknn_7_11.qlknn >> ~/.bashrc

# END MESSAGE
echo 'You can try out the test couplings in the pds/ymmsl_files directory by running:'
echo ''
echo 'muscle_manager --start-all path/to/my/file.ymmsl'
echo ''
echo 'Make sure to change any relavant file paths in the ymmsl files!'

