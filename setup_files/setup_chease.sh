# this file expects to be run from the 'run' folder
set -euo pipefail # stop if anything doesn't work

CHEASE_URL=${1:-"https://gitlab.epfl.ch/spc/chease.git"}
BRANCH_CHEASE=${2:-"feature/muscle3"}

export XML_USE_CHOICE="NO"
# source imas_base_env
git clone "$CHEASE_URL"
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
