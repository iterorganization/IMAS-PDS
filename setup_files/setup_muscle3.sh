# this file expects to be run from the 'run' folder
#
# Bootstraps the muscle3 0.10.0 C++ library (libmuscle.so / libymmsl.so) that
# the NICE muscle3 binaries link against at build time. Uses the site-wide
# EasyBuild install directly: no modulefile is published for 0.10.0 (only
# 0.7.x/0.8.0 are reachable via `module load MUSCLE3`), so PKG_CONFIG_PATH/
# LD_LIBRARY_PATH are wired up here instead.
#
# Writes a wrapper env file to tmp/muscle3-0.10.0-intel/bin/muscle3.env;
# setup_nice.sh sources it to build against this install.
set -euo pipefail # stop if anything doesn't work

M3_HOME=${1:-"/work/imas/opt/EasyBuild/software/MUSCLE3/0.10.0-intel-2023b"}

if [[ ! -f "$M3_HOME/lib/libmuscle.so" ]]; then
  echo "ERROR: expected site-wide muscle3 0.10.0 install at $M3_HOME (not found)." >&2
  exit 1
fi

M3_PREFIX="$PWD/tmp/muscle3-0.10.0-intel"
mkdir -p "$M3_PREFIX/bin"
cat > "$M3_PREFIX/bin/muscle3.env" << MUSCLE3_ENV
# Don't execute this file, it won't help. Source it instead to make
# muscle3 0.10.0 available in your shell.
export MUSCLE3_HOME="$M3_HOME"
export PKG_CONFIG_PATH="$M3_HOME/lib/pkgconfig\${PKG_CONFIG_PATH:+:\$PKG_CONFIG_PATH}"
export LD_LIBRARY_PATH="$M3_HOME/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
export PATH="$M3_HOME/bin\${PATH:+:\$PATH}"

if [ "a\${BASH:-}" != 'a' -o "a\${ZSH_VERSION:-}" != 'a' ] ; then
    hash -r
fi
MUSCLE3_ENV

echo "  Wrote: $M3_PREFIX/bin/muscle3.env  (points at $M3_HOME)"
