#!/bin/bash
# The PDS checkout environment that the umbrella module PDS/1.0 used to set (PATH, PYTHONPATH,
# YMMSL_PATH, IMAS_VERSION, stack limit). Source it after ci/resolve_deps.sh:
#     export COMBO=intel-2025b-dd4; source ci/resolve_deps.sh; source ci/pds_env.sh
# PDS_REPO: an exported value wins (it must be a checkout: bin/pds-run exists, as the module
# required); otherwise the checkout this file belongs to.
_pe_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P) || return 1
if [[ -n "${PDS_REPO:-}" && ! -f "$PDS_REPO/bin/pds-run" ]]; then
    echo "pds_env: ERROR: PDS_REPO=$PDS_REPO is not a PDS checkout (no bin/pds-run)" >&2
    unset _pe_root
    return 1
fi
export PDS_REPO=${PDS_REPO:-$_pe_root}
unset _pe_root
export PATH="$PDS_REPO/bin:$PATH"
export PYTHONPATH="$PDS_REPO${PYTHONPATH:+:$PYTHONPATH}"
# Lets workflows resolve `from lib.easybuild_programs import ...`.
export YMMSL_PATH="$PDS_REPO/workflows${YMMSL_PATH:+:$YMMSL_PATH}"
# Env settings every workflow actor needs (same values as the module).
export IMAS_VERSION=4.0.0
unset MPLBACKEND
ulimit -s unlimited 2>/dev/null || true
export PDS_DEPS_RESOLVED=1
