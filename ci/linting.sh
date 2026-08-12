#!/bin/bash
# Bamboo CI script for linting
# Note: this script should be run from the root of the git repository

# Debuggging:
set -e -o pipefail
echo "Loading modules..."

# Set up environment such that module files can be loaded
source /etc/profile.d/modules.sh
module purge
# Load modules required for linting
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

# Create a venv
rm -rf venv
"$UV" venv venv
. venv/bin/activate

# Install and run linters
"$UV" pip install --upgrade .[linting]

ruff format --check pds
ruff check pds
ty check pds
