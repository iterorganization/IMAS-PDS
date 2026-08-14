#!/bin/bash
# Build a custom CHEASE module against a single consistent toolchain
# generation (IMAS-Fortran, iWrap 2.0.0, MUSCLE3 0.10.0,
# iWrap-plugins-MUSCLE3, all intel-2025b) -- CHEASE's own upstream
# python/config_muscle3.sh mixes intel-2023b/2025b modules and can't build or
# register with the real 0.10.0 manager on this cluster.
#
# intel-2025b no longer ships `ifort`, only `ifx`, and CHEASE's Makefile
# hardcodes `ifort`; an `ifort` -> `ifx` wrapper script on PATH covers that
# without touching CHEASE's vendored Makefile.
#
# IDS_main_version_number=4 must be set explicitly: CHEASE's Makefile derives
# it from $IMAS_VERSION's first digit to pick its DD3 vs DD4 equilibrium
# mapping file, and silently defaults to DD3 (wrong here) if unset.
#
# Usage: bash build_chease.sh <module-version> [branch] [git-url]
# e.g:   bash build_chease.sh 2026-08-14-pds feature/muscle3
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source common.sh

MODULE_VERSION="${1:?usage: build_chease.sh <module-version> [branch] [git-url]}"
BRANCH="${2:-feature/muscle3}"
CHEASE_URL="${3:-https://gitlab.epfl.ch/spc/chease.git}"

CHECKOUT="$PDS_SOFTWARE_ROOT/CHEASE/$MODULE_VERSION"
MODULE_DIR="$PDS_MODULES_ROOT/PDS-CHEASE"
MODULE_FILE="$MODULE_DIR/$MODULE_VERSION.lua"

echo "############## Building PDS-CHEASE/$MODULE_VERSION (branch: $BRANCH) ##############"
mkdir -p "$(dirname "$CHECKOUT")" "$MODULE_DIR"

if [[ ! -d "$CHECKOUT/.git" ]]; then
  git clone "$CHEASE_URL" "$CHECKOUT"
fi
cd "$CHECKOUT"
git fetch --quiet origin
git checkout "$BRANCH"

# See header comment: an ifort->ifx shim, since CHEASE's Makefile hardcodes
# the literal command name "ifort" with no ifx awareness, but ifx accepts
# every flag it passes.
IFX_SHIM_DIR="$(mktemp -d)"
cat > "$IFX_SHIM_DIR/ifort" << 'SHIMEOF'
#!/bin/bash
exec ifx "$@"
SHIMEOF
chmod +x "$IFX_SHIM_DIR/ifort"

module purge
module load IMAS-Fortran/5.6.0-intel-2025b-DD-4.1.1
module load INTERPOS/9.2.3-iimkl-2025b
module load XMLlib/3.3.2-intel-compilers-2025.2.0
module load iWrap/2.0.0-intel-2025b
module load MUSCLE3/0.10.0-intel-2025b
module load iWrap-plugins-MUSCLE3/0.4.0-intel-2025b
export XML_USE_CHOICE=yes
export IDS_main_version_number=4
export IMAS_VERSION=4.1.1
# iwrap itself (unlike CHEASE's own Makefile) reads $FC directly to pick its
# compiler command -- config_muscle3.sh normally provides this via `export
# FC=ifort`; set it here directly since that script is intentionally not
# sourced (see header comment).
export FC=ifort
export PATH="$IFX_SHIM_DIR:$PATH"
export PYTHONPATH="$CHECKOUT/python/..:${PYTHONPATH:-}"

./build_imas.csh
rm -rf chease_m3
iwrap -f iwrap/chease_choices_M3.yaml -i "$PWD"
mv chease chease_m3

cd chease_m3
sed -i "s|<cocos_in>[0-9]\+</cocos_in>|<cocos_in>17</cocos_in>|" "input/chease_input_choices.xml"
sed -i "s|<cocos_out>[0-9]\+</cocos_out>|<cocos_out>17</cocos_out>|" "input/chease_input_choices.xml"
rm -f bin/chease.exe

# Capture the build-time library path to bake into chease.exe's RPATH below
# (same fix as build_nice.sh): the Makefile only sets explicit -rpath for
# IMAS-Fortran/IMAS-Core, everything else relies on LD_LIBRARY_PATH at
# runtime, which a `base_env: clean` actor subprocess won't have.
CHEASE_BUILD_LDPATH="$LD_LIBRARY_PATH"
make

# Isolated subshell, same as build_nice.sh: the older patchelf build needed
# here would otherwise swap the whole GCCcore toolchain out from under any
# later step in this same shell.
(
  module purge
  module use "$PDS_MODULES_ROOT" 2>/dev/null || true
  module load patchelf/0.18.0-GCCcore-13.2.0 || true
  command -v patchelf >/dev/null || { echo "ERROR: patchelf did not load" >&2; exit 1; }
  patchelf --force-rpath --add-rpath "$CHEASE_BUILD_LDPATH" bin/chease.exe
)
cd ../..
module purge
rm -rf "$IFX_SHIM_DIR"

cat > "$MODULE_FILE" << EOF
-- Custom PDS build of CHEASE, targeting the full intel-2025b toolchain
-- generation (IMAS-Fortran, iWrap 2.0.0, MUSCLE3 0.10.0,
-- iWrap-plugins-MUSCLE3) via an ifort->ifx compiler shim, instead of
-- CHEASE's own upstream python/config_muscle3.sh (mixes intel-2023b/2025b,
-- cannot work on this cluster at all -- see
-- setup_files/custom_modules/build_chease.sh's header comment for why).
-- Rebuild/update: bash setup_files/custom_modules/build_chease.sh <new-version> <branch>

help([[
PDS-CHEASE (custom PDS build of CHEASE, full intel-2025b toolchain)

Source: $CHEASE_URL @ $BRANCH
Installed: $CHECKOUT
]])

whatis("Description: Custom PDS build of CHEASE (IMAS-wrapped, MUSCLE3 0.10.0 actor)")

prepend_path("PATH", "$CHECKOUT/chease_m3/bin")
setenv("EBROOTCHEASE", "$CHECKOUT")
EOF

echo "Installed PDS-CHEASE/$MODULE_VERSION -> $CHECKOUT/chease_m3/bin"
echo "Module:    $MODULE_FILE"
echo ""
echo "NOTE: verify $CHECKOUT/chease_m3/bin/chease.exe actually runs from a"
echo "clean shell before relying on it -- e.g.:"
echo "  module purge; ldd $CHECKOUT/chease_m3/bin/chease.exe | grep 'not found'"
