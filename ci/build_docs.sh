#!/bin/bash
# Bamboo CI script to install imaspy and run all tests
# Note: this script should be run from the root of the git repository

# Debuggging:
set -e -o pipefail
echo "Loading modules:" $@

# Set up environment such that module files can be loaded
source /etc/profile.d/modules.sh
module purge
# Modules are supplied as arguments in the CI job:
module load $@

# Debuggging:
echo "Done loading modules"
set -x

# uv isn't guaranteed to be present on the CI agent; bootstrap it via a disposable
# venv if missing (not `pip install --user`: the agent's home directory may not be
# writable, and the shared module Python's site-packages usually isn't either).
if command -v uv >/dev/null 2>&1; then
  UV="$(command -v uv)"
else
  rm -rf .uv-bootstrap
  python3 -m venv .uv-bootstrap
  .uv-bootstrap/bin/pip install --quiet uv
  UV="$(.uv-bootstrap/bin/python -c 'import uv; print(uv.find_uv_bin())')"
fi

# Set up the testing venv
rm -rf venv  # Environment should be clean, but remove directory to be sure
"$UV" venv venv
source venv/bin/activate

# Create sdist and wheel
"$UV" pip install --upgrade .[docs]

# Debugging:
"$UV" pip freeze

# Enable sphinx options:
# - `-W`: turn warnings into errors
# - `-n`: nit-picky mode, warn about all missing references
# - `--keep-going`: with -W, keep going when getting warnings
export SPHINXOPTS='-W --keep-going'

# Run sphinx to create the documentation
make -C docs clean html
