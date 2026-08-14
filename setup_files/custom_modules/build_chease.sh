#!/bin/bash
# Build a custom CHEASE module, targeting the full intel-2025b toolchain
# generation throughout (IMAS-Fortran, iWrap 2.0.0, MUSCLE3 0.10.0,
# iWrap-plugins-MUSCLE3), instead of CHEASE's own upstream
# python/config_muscle3.sh, which mixes generations and cannot work at all
# on this cluster -- see the two paragraphs below for exactly why, both
# confirmed empirically, not assumed.
#
# Why not just source CHEASE's own python/config_muscle3.sh (like
# setup_chease.sh does): it does `module load IMAS/4.0.0-2024.12-intel-2023b`
# then bare `module load INTERPOS XMLlib iWrap MUSCLE3 iWrap-plugins-MUSCLE3
# yMMSL-dot`. On this cluster iWrap's only major version (2.0.0) has no
# intel-2023b build at all (only intel-2025b/foss-2025b), so that bare load
# silently swaps the whole toolchain to intel-2025b mid-script, taking
# `ifort` (2023b-only) out from under the Fortran compile that follows
# (confirmed: `ifort: command not found`). There is no combination of
# existing modules that keeps everything in one generation via that script's
# own approach: IMAS-AL-Fortran (2023b's binding) has no 2025b build, and
# iWrap-plugins-MUSCLE3's 2023b build depends on MUSCLE3/0.7.2-intel-2023b,
# two minor versions behind the actual 0.10.0 manager everything else uses --
# even if the ifort issue were dodged, actor registration would fail the
# same way METIS's did (see build_metis.sh) with a wire-protocol "Unknown
# session" error.
#
# The fix used here instead: go the other direction entirely -- IMAS-Fortran
# (the 2025b-native rename of IMAS-AL-Fortran) + iWrap/2.0.0-intel-2025b +
# MUSCLE3/0.10.0-intel-2025b + iWrap-plugins-MUSCLE3/0.4.0-intel-2025b, all
# one consistent generation, no swap. The one remaining gap: intel/2025b no
# longer ships classic `ifort` at all (only `ifx`, confirmed via `which
# ifort` finding nothing), and CHEASE's own Makefile hardcodes literal
# `ifort` as the compiler command with zero `ifx` awareness anywhere in the
# repo (confirmed by grepping the whole source tree). Since `ifx` accepts
# every flag CHEASE's Makefile passes it (confirmed with a standalone test
# compile using the exact flags: -O3 -r8 -g -heap-arrays -fPIC
# -diag-disable:5462), the fix is a tiny wrapper script named literally
# "ifort" that just execs `ifx "$@"`, put first on PATH -- avoids touching
# CHEASE's vendored Makefile at all.
#
# Also needs IDS_main_version_number=4 (or a correctly-exported IMAS_VERSION
# starting with "4") set explicitly before the build: CHEASE's Makefile
# derives this from the first digit of $IMAS_VERSION to choose between its
# own copy_ids_to_itm_equilibrium_default_DD3.f90 vs _DD4.f90 mapping files
# (DD 3.x vs 4.x equilibrium IDS schema -- genuinely different field names,
# e.g. boundary%lcfs vs boundary%outline). Without it the Makefile warns
# "cannot decide on main IDS version" and silently defaults to DD3, which
# fails to compile against the DD 4.1.1 IMAS-Fortran headers loaded here.
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

# See header comment (build_nice.sh has the same fix, same reasoning):
# capture the build-time library path so it can be baked into chease.exe's
# RPATH afterward -- the Makefile's link line only sets explicit -rpath for
# IMAS-Fortran/IMAS-Core, everything else (MUSCLE3, XMLlib, INTERPOS, ...)
# relies on LD_LIBRARY_PATH at runtime instead, which a future actor
# subprocess spawned via `base_env: clean` would never have.
CHEASE_BUILD_LDPATH="$LD_LIBRARY_PATH"
make

# Isolated subshell, same as build_nice.sh: patchelf/0.18.0-GCCcore-14.3.0
# (the default) SIGILLs on at least one cluster compute node, and loading
# the older GCCcore-13.2.0 build directly in this shell would swap the
# whole GCCcore toolchain out from under any later step. Confined to its
# own subshell, after all compiling is done.
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
