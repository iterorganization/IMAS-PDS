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

# The loaded module(s) only exist to provide a `python3` to bootstrap the venv below --
# all doc-build deps (including imas-python/imas-core) come from `.[docs]` via uv. But the
# module's PYTHONPATH (e.g. Python-bundle-PyPI's bundled `pbr`) leaks into uv's "isolated"
# build subprocess, so setuptools' egg_info step discovers pbr's `egg_info.writers` entry
# point from outside the venv and fails importing pbr.git's `pkg_resources` dependency,
# which isn't installed in the isolated build env. Drop it now that python3 is resolved.
unset PYTHONPATH

source "$(dirname "${BASH_SOURCE[0]}")/../setup_files/ensure_uv.sh"

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
