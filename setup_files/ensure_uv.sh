# Source this file to set $UV to an absolute path to a working `uv` binary.
#
# uv isn't guaranteed to be present on CI agents or HPC login nodes, so this
# bootstraps it via a disposable venv if missing. Deliberately not
# `pip install --user`: the caller's home directory may not be writable, and
# the shared module Python's site-packages usually isn't either.
if command -v uv >/dev/null 2>&1; then
  UV="$(command -v uv)"
else
  rm -rf .uv-bootstrap
  python3 -m venv .uv-bootstrap
  .uv-bootstrap/bin/pip install --quiet uv
  UV="$(.uv-bootstrap/bin/python -c 'import uv; print(uv.find_uv_bin())')"
fi
