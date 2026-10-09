#!/bin/bash
# Switch PDS between the EasyBuild-module and the local-install (local_installs/) build
# of each component.
#
# Called at the end of pds_setup.sh with its USE_LOCAL_<COMP> flags; can also be run
# directly, from anywhere:
#
#   USE_LOCAL_NICE=true USE_LOCAL_TORAX=true bash setup_files/use_local_programs.sh
#   bash setup_files/use_local_programs.sh --repo /path/to/pds/checkout
#
# For each component, USE_LOCAL_<COMP>="true" rewrites
#   - from lib.easybuild_programs import implementation <impl>
# into
#   - from lib.local_programs import implementation <impl>
# for every <impl> of that component (see the table below), and "false" rewrites it
# back. An unset flag leaves the component untouched. This is done in
#   - workflows/*/workflow.ymmsl (tracked: switched files must not be committed), and
#   - the actor tests ymmsl_files/*.ymmsl and ymmsl_files/*/*.ymmsl (git-ignored,
#     rendered from the tracked *.template files by setup_files/setup_test_files.sh;
#     re-rendering resets them to the module, so run this script again afterwards. The
#     templates themselves stay on the module.)
# Only import lines of exactly that form are touched; every other byte of those files is
# preserved (including CRLF line endings). Running it twice gives the same result.
#
# MUSCLE3_DASHBOARD is a command-line tool, not a workflow implementation. For it,
# "true" creates the marker file local_installs/.use_local_muscle3_dashboard and "false"
# removes it; bin/m3dash (first on PATH once the PDS module is loaded) runs
# local_installs/muscle3-dashboard/venv/bin/m3dash while the marker exists, and the
# module's m3dash otherwise.
#
# A component is only switched to local if every path its local_programs.ymmsl entries
# (or, for the dashboard, bin/m3dash) rely on exists; otherwise a WARNING is printed and
# it stays on the module.
#
# workflows/lib/local_programs.ymmsl and workflows/lib/easybuild_programs.ymmsl are NOT
# modified: every local entry takes the component's code from a fixed
# $PDS_REPO/local_installs/... path (the layout the setup_files/setup_<comp>.sh scripts
# build; modules are loaded there only for toolchain/runtime libraries/MATLAB), and
# $PDS_REPO is set at run time (PDS module, bin/pds-run-case, bin/pds-create-case,
# bin/pds-configure). Nothing in them depends on setup-time choices, so only the
# workflow imports decide which file an implementation comes from.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "${1:-}" = "--repo" ]; then
  REPO="$(cd "${2:?--repo needs a directory}" && pwd)"
fi

# ---------------------------------------------------------------------------------------
# Component -> implementation mapping.
#
# Only implementations defined in BOTH workflows/lib/easybuild_programs.ymmsl and
# workflows/lib/local_programs.ymmsl can be switched. The required paths (relative to
# the repo root) are the local_installs/ paths the local_programs.ymmsl entry uses.
#
#   implementation       component         required local path(s), comma-separated
IMPL_TABLE="
temporal_coupler       IMAS_MUSCLE3      local_installs/IMAS-MUSCLE3/venv/bin/activate
loop                   IMAS_MUSCLE3      local_installs/IMAS-MUSCLE3/venv/bin/activate
load_balancer          IMAS_MUSCLE3      local_installs/IMAS-MUSCLE3/venv/bin/activate
waveform_editor        WAVEFORM_EDITOR   local_installs/Waveform-Editor/venv/bin/activate
metis                  METIS             local_installs/metis/workflow/muscle3/mfile/metis4muscle3.m
nice_inv               NICE              local_installs/nice/run/nice_imas_inv_muscle3
nice_dir               NICE              local_installs/nice/run/nice_imas_dir_muscle3
nice_evo               NICE              local_installs/nice/run/nice_imas_evo_muscle3
nice_evo_rd            NICE              local_installs/nice/run/nice_imas_evo_rd_muscle3
torax                  TORAX             local_installs/TORAX-MUSCLE3/venv/bin/activate
magnetic_controller    PCS               local_installs/pcs/pcssp/scdds
chease                 CHEASE            local_installs/chease/chease_m3/bin/chease.exe,local_installs/chease/python/config_muscle3.sh
"
# Notes:
#  - IMAS_MUSCLE3: only the PDS actors run in its venv are listed. The imas_muscle3
#    actors (source_component, sink_component, ...) are imported `from imas_muscle3`
#    in the workflows and are not touched here.
#  - METIS: the local `metis` entry still loads the METIS-IRFM module, but only for
#    MATLAB and its muscle3 Python venv; the METIS code comes from local_installs/metis.
#  - NICE: setup_nice.sh builds all four nice_imas_*_muscle3 binaries; all four
#    implementations switch together.
#  - PCS: the local magnetic_controller takes ONLY the PCS/PCSSP code from
#    local_installs/pcs; NICE's MATLAB tools, the MUSCLE3 Python venv and the MATLAB
#    IMAS module still come from the PCS/NICE/IMAS-MATLAB EasyBuild modules, exactly as
#    in the easybuild_programs.ymmsl entry, so no local NICE or IMAS-MUSCLE3 install is
#    required to switch PCS alone.
#  - CHEASE: no workflow uses it yet; the switch acts on the actor test
#    ymmsl_files/test_chease_actor.ymmsl (and on any workflow that imports `chease`).
#    The local entry sources local_installs/chease/python/config_muscle3.sh, the
#    environment setup_chease.sh builds with.
#  - MUSCLE3_DASHBOARD: not in this table, handled by the marker file (see the header).
ALL_COMPONENTS="IMAS_MUSCLE3 WAVEFORM_EDITOR METIS NICE TORAX CHEASE PCS"
DASHBOARD_M3DASH="local_installs/muscle3-dashboard/venv/bin/m3dash"
DASHBOARD_MARKER="local_installs/.use_local_muscle3_dashboard"
# ---------------------------------------------------------------------------------------

EB_FILE="$REPO/workflows/lib/easybuild_programs.ymmsl"
LOCAL_FILE="$REPO/workflows/lib/local_programs.ymmsl"

impls_of() { # component -> its implementations
  awk -v c="$1" 'NF == 3 && $2 == c { print $1 }' <<<"$IMPL_TABLE"
}
paths_of() { # implementation -> required paths, one per line
  awk -v i="$1" 'NF == 3 && $1 == i { print $3 }' <<<"$IMPL_TABLE" | tr ',' '\n'
}
defined_in() { # implementation, file
  grep -qE "^  $1:[[:space:]]*\$" "$2"
}

echo "############## SELECTING MODULE / LOCAL IMPLEMENTATIONS ##############"

case "${USE_LOCAL_MUSCLE3_DASHBOARD:-}" in
  "") ;;
  true)
    if [ -x "$REPO/$DASHBOARD_M3DASH" ]; then
      if [ ! -e "$REPO/$DASHBOARD_MARKER" ]; then
        touch "$REPO/$DASHBOARD_MARKER"
        echo "m3dash now runs the local dashboard ($DASHBOARD_M3DASH)."
      fi
    else
      echo "WARNING: USE_LOCAL_MUSCLE3_DASHBOARD=true but the local install is missing:"
      echo "           $REPO/$DASHBOARD_M3DASH"
      echo "         MUSCLE3_DASHBOARD stays on the module (install it first, e.g. with pds_setup.sh's INSTALL_* flags)."
      rm -f "$REPO/$DASHBOARD_MARKER"
    fi
    ;;
  false)
    if [ -e "$REPO/$DASHBOARD_MARKER" ]; then
      rm -f "$REPO/$DASHBOARD_MARKER"
      echo "m3dash now runs the module's dashboard."
    fi
    ;;
  *)
    echo "ERROR: USE_LOCAL_MUSCLE3_DASHBOARD=\"$USE_LOCAL_MUSCLE3_DASHBOARD\" (must be \"true\" or \"false\")" >&2
    exit 1
    ;;
esac

declare -A TARGET # implementation -> easybuild_programs | local_programs
for comp in $ALL_COMPONENTS; do
  var="USE_LOCAL_$comp"
  val="${!var:-}"
  case "$val" in
    "") continue ;;
    true | false) ;;
    *)
      echo "ERROR: $var=\"$val\" (must be \"true\" or \"false\")" >&2
      exit 1
      ;;
  esac
  impls="$(impls_of "$comp")"
  if [ -z "$impls" ]; then
    [ "$val" = "true" ] && echo "NOTE: $var=true has no effect ($comp has no implementation in both lib/*_programs.ymmsl)."
    continue
  fi
  target="easybuild_programs"
  if [ "$val" = "true" ]; then
    target="local_programs"
    missing=""
    for impl in $impls; do
      while read -r p; do
        [ -e "$REPO/$p" ] || missing+=" $p"
      done < <(paths_of "$impl")
    done
    if [ -n "$missing" ]; then
      echo "WARNING: $var=true but the local install is missing:"
      for p in $missing; do echo "           $REPO/$p"; done
      echo "         $comp stays on the module (install it first, e.g. with pds_setup.sh's INSTALL_* flags)."
      continue
    fi
  fi
  for impl in $impls; do
    if defined_in "$impl" "$EB_FILE" && defined_in "$impl" "$LOCAL_FILE"; then
      TARGET[$impl]="$target"
    else
      echo "WARNING: '$impl' is not defined in both lib/easybuild_programs.ymmsl and lib/local_programs.ymmsl; not switched."
    fi
  done
done

n_changed=0
# Workflows (tracked) and the rendered actor tests (git-ignored; the templates are at
# most one directory deep, ymmsl_files/output/ holds run results); see the header.
for wf in "$REPO"/workflows/*/workflow.ymmsl "$REPO"/ymmsl_files/*.ymmsl \
  "$REPO"/ymmsl_files/*/*.ymmsl; do
  [ -f "$wf" ] || continue
  case "$wf" in "$REPO"/ymmsl_files/output/*) continue ;; esac
  sed_args=()
  for impl in "${!TARGET[@]}"; do
    to="${TARGET[$impl]}"
    from="local_programs"
    [ "$to" = "local_programs" ] && from="easybuild_programs"
    # \(\r\?\) keeps a CRLF line ending as it is.
    sed_args+=(-e "s/^- from lib\.$from import implementation $impl\(\r\?\)\$/- from lib.$to import implementation $impl\1/")
  done
  [ ${#sed_args[@]} -gt 0 ] || break
  tmp="$(mktemp "$wf.XXXXXX")"
  sed "${sed_args[@]}" "$wf" >"$tmp"
  if cmp -s "$wf" "$tmp"; then
    rm -f "$tmp"
    continue
  fi
  echo "Changed ${wf#"$REPO"/}:"
  diff "$wf" "$tmp" | grep '^[<>]' | sed -e 's/^</    -/' -e 's/^>/    +/' | tr -d '\r' || true
  cat "$tmp" >"$wf" # keep the file's inode and permissions
  rm -f "$tmp"
  n_changed=$((n_changed + 1))
done
[ "$n_changed" -eq 0 ] && echo "Imports already match the USE_LOCAL_* flags; nothing changed."

if grep -lE '^- from lib\.local_programs import implementation ' "$REPO"/workflows/*/workflow.ymmsl >/dev/null 2>&1; then
  echo ""
  echo "REMINDER: these workflow files now import local implementations. They are locally"
  echo "modified for your installation only and must NOT be committed:"
  grep -lE '^- from lib\.local_programs import implementation ' "$REPO"/workflows/*/workflow.ymmsl |
    sed "s|^$REPO/|    |"
fi
echo "############## FINISHED SELECTING IMPLEMENTATIONS ##############"
