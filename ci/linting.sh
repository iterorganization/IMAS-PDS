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

source "$(dirname "${BASH_SOURCE[0]}")/../setup_files/ensure_uv.sh"

# Create a venv
rm -rf venv
"$UV" venv venv
. venv/bin/activate

# Install and run linters
# docs/visualization needed too so ty can resolve every import across the repo
"$UV" pip install --upgrade .[docs,linting,visualization]

ruff format --check .
ruff check .
ty check .
