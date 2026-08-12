# this file expects to be run from the 'run' folder
set -euo pipefail # stop if anything doesn't work

module purge
module load Python

# uv isn't guaranteed to be present; bootstrap it via a disposable venv if missing
# (not `pip install --user`: the home directory may not be writable, and the
# shared module Python's site-packages usually isn't either).
if command -v uv >/dev/null 2>&1; then
  UV="$(command -v uv)"
else
  rm -rf .uv-bootstrap
  python3 -m venv .uv-bootstrap
  .uv-bootstrap/bin/pip install --quiet uv
  UV="$(.uv-bootstrap/bin/python -c 'import uv; print(uv.find_uv_bin())')"
fi

IMAS_MUSCLE3_URL=${1:-"https://github.com/iterorganization/IMAS-MUSCLE3.git"}
BRANCH_IMAS_MUSCLE3=${2:-"develop"}

if [[ ! -d "IMAS-MUSCLE3/.git" ]]; then
  git clone $IMAS_MUSCLE3_URL IMAS-MUSCLE3
fi
cd IMAS-MUSCLE3
git fetch --quiet origin
git checkout $BRANCH_IMAS_MUSCLE3
if [[ ! -d venv ]]; then
  "$UV" venv ./venv
fi
. venv/bin/activate
"$UV" pip install -e .
echo "  muscle3 version: $("$UV" pip show muscle3 | grep '^Version')"
deactivate
module purge
cd ..
