# Shared paths for the custom PDS dependency modules built by the
# build_*.sh scripts in this directory. Source this from a build script,
# not directly.
#
# Layout mirrors SDCC's own EasyBuild tree, just under your own account:
#   $PDS_SOFTWARE_ROOT/<Name>/<version>/   -- install prefix (venv or compiled binaries)
#   $PDS_MODULES_ROOT/<Name>/<version>.lua -- matching Lmod modulefile
#
# Override either by exporting it before calling a build script, e.g. to
# install somewhere other than your own home directory.

: "${PDS_SOFTWARE_ROOT:=$HOME/public/software}"
: "${PDS_MODULES_ROOT:=$HOME/public/modules}"
