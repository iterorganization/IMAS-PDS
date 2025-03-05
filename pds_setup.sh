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

# ENV VARIABLES
export IMAS_AL_DISABLE_VALIDATE=1
ulimit -s unlimited
unset MPLBACKEND

# MODULE LOAD
pip install --upgrade pip
pip install --upgrade setuptools wheel

module purge
module load libxml2
module load SuiteSparse/7.7.0-intel-2023b
module load IMAS/4.0.0-2024.12-intel-2023b
module load IMASPy
module load MUSCLE3
module load IDS-Validator
module load MATLAB
module load GCC

# SET UP METIS
git clone ssh://git@git.iter.org/scen/metis.git
cd metis
python3 -m venv ./venv
. venv/bin/activate
matlab -nodisplay -nosplash -r "make_metis_linux; exit"
deactivate
cd ..

# SET UP NICE
# dd v4 needs fix
git clone git@gitlab.inria.fr:blfauger/nice.git
cd nice
git submodule init
git submodule update
cp run/iwrap/param/inv/param.x* run/input
cp run/iwrap/param/xsd/param.x* run/input
cd src
cp Makefile.DO-NOT-CHANGE-THIS-FILE Makefile
make -j nice_imas_inv_muscle3
make -j nice_imas_dir_muscle3
make -j nice_imas_evo_muscle3
cd ../..

# SET UP IMAS-M3
git clone git@github.com:iterorganization/IMAS-muscle3.git
cd IMAS-muscle3
python3 -m venv ./venv
. venv/bin/activate
pip install -e .
deactivate
cd ..

# SET UP PDS
git clone ssh://git@git.iter.org/scen/pds.git
cd pds
python3 -m venv ./venv
. venv/bin/activate
pip install -e .
deactivate
cd ..
 
# SET UP TORAX
module purge
module load Python/3.11.5-GCCcore-13.2.0
git clone ssh://git@git.iter.org/scen/torax-m3.git
cd torax-m3
python3 -m venv ./venv
. venv/bin/activate
cd ..
git clone git@github.com:google-deepmind/torax.git
cd torax
pip install -e .
cd ..
cd torax-m3
pip install -e .
deactivate
cd ..

# END MESSAGE
echo 'You can try out the test couplings in the pds/ymmsl_files directory by running:'
echo ''
echo 'muscle_manager --start-all path/to/my/file.ymmsl'
echo ''
echo 'Make sure to change any relavant file paths in the ymmsl files!'

# test runs if given 'with-test' flag
if [[ "$1" == "with-test" ]]; then
  # Some of the test files might need some changes to point to local files
  mkdir -p ~/public/imasdb/ITER/4/666666
  cp -r /home/ITER/fargerb/public/imasdb/ITER/4/666666/1 ~/public/imasdb/ITER/4/666666
  
  cd pds/ymmsl_files
  muscle_manager --start-all test_sink_source_actor.ymmsl
  muscle_manager --start-all test_olc_actor.ymmsl
  muscle_manager --start-all test_nice_actor.ymmsl
  muscle_manager --start-all test_torax_actor.ymmsl
  muscle_manager --start-all test_metis_actor.ymmsl
  muscle_manager --start-all test_torax_nice_coupling.ymmsl
fi 

