#!/bin/bash
# Apply the local patches PDS depends on. Run from the 'run' folder, after
# setup_imas_muscle3.sh and setup_waveform_editor.sh. Idempotent: re-running is a no-op.
#
# Both patches are unmerged upstream and both are load-bearing:
#
#   muscle3-manager-env-vars-and-input-copies   two changes to muscle_manager.py:
#     (a) ${PDS_REPO} / ${SCENARIOS_REPO} in case files. Stock muscle3 uses setting values
#         verbatim, so without this the actors receive a literal "${PDS_REPO}/...". Until
#         bin/pds-run was deleted this job was done by its envsubst.
#     (b) copies the yMMSL files given on the command line into <run_dir>/input/, numbered
#         in merge order. The run dir already gets configuration.ymmsl, but that is the
#         resolved and flattened form -- four times the size and not what anyone wrote.
#         run_dir.py's own layout docstring documents these copies; nothing implemented
#         them. They are one patch because both touch the same regions of one file.
#
#   waveform-editor-relative-imports      relative data URIs in a scenario's waveforms.yaml.
#     Without it a scenario has to name its data by absolute path, which is only correct
#     on the machine it was written on.
#
# FALLBACK: if the muscle3 patch is not merged in reasonable time, the alternative is a
# thin wrapper that runs `envsubst` over the ymmsl files before calling muscle_manager --
# what bin/pds-run did. That reintroduces a wrapper (against Goal C) but needs no patched
# muscle3. The Waveform-Editor patch has no such fallback short of absolute paths.
set -euo pipefail

PDS_REPO="${PDS_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PATCHES="$PDS_REPO/ci/patches"
M3_VENV="${M3_VENV:-$PWD/IMAS-MUSCLE3/venv}"
WE_DIR="${WE_DIR:-$PWD/Waveform-Editor}"

fail=0

apply_to_git_repo() {  # <repo> <patch>
  local repo="$1" patch="$2"
  if git -C "$repo" apply --reverse --check "$patch" 2>/dev/null; then
    echo "  already applied: $(basename "$patch")"
  elif git -C "$repo" apply --check "$patch" 2>/dev/null; then
    git -C "$repo" apply "$patch"
    echo "  applied: $(basename "$patch")"
  else
    echo "  FAILED to apply $(basename "$patch") to $repo" >&2
    echo "    The upstream file has probably moved on. Check whether the change has been" >&2
    echo "    merged -- if so, delete the patch; if not, rebase it." >&2
    fail=1
  fi
}

apply_to_tree() {  # <dir> <patch> <marker_file> <marker> -- for non-git installed packages
  # "Already applied?" is decided by looking for <marker> in <marker_file>, not by
  # `patch -R --dry-run`: patch matches with fuzz and cheerfully reports that a reverse
  # apply would succeed against a pristine file, which would skip the real apply.
  #
  # --batch is equally essential: without it patch prompts on a failed hunk, and a prompt
  # answered by EOF looks like success while changing nothing.
  local dir="$1" patch="$2" marker_file="$3" marker="$4"
  if grep -q -- "$marker" "$dir/$marker_file" 2>/dev/null; then
    echo "  already applied: $(basename "$patch")"
  elif patch -p1 -d "$dir" --dry-run --batch --silent < "$patch" >/dev/null 2>&1; then
    patch -p1 -d "$dir" --batch --silent < "$patch" >/dev/null
    echo "  applied: $(basename "$patch")"
  else
    echo "  FAILED to apply $(basename "$patch") in $dir" >&2
    echo "    The upstream file has probably moved on. Check whether the change has been" >&2
    echo "    merged -- if so, delete the patch; if not, rebase it." >&2
    fail=1
  fi
}

echo "muscle3 (in $M3_VENV):"
if [[ -d "$M3_VENV" ]]; then
  SITE=$("$M3_VENV/bin/python" -c "import muscle3, pathlib; print(pathlib.Path(muscle3.__file__).parent.parent)")
  apply_to_tree "$SITE" "$PATCHES/muscle3-manager-env-vars-and-input-copies.patch" \
                "muscle3/muscle_manager.py" "def save_input_files("
else
  echo "  SKIPPED: no venv at $M3_VENV -- run setup_imas_muscle3.sh first" >&2
  fail=1
fi

echo "Waveform-Editor (in $WE_DIR):"
if [[ -d "$WE_DIR/.git" ]]; then
  branch=$(git -C "$WE_DIR" rev-parse --abbrev-ref HEAD)
  if [[ "$branch" != "feature/reference-tendency-old" ]]; then
    echo "  WARNING: on branch '$branch'. globals.imports exists ONLY on" >&2
    echo "    feature/reference-tendency-old; on develop every PDS waveforms.yaml fails" >&2
    echo "    with \"'imports' is not a parameter of YamlGlobals\"." >&2
  fi
  apply_to_git_repo "$WE_DIR" "$PATCHES/waveform-editor-relative-imports.patch"
else
  echo "  SKIPPED: no checkout at $WE_DIR -- run setup_waveform_editor.sh first" >&2
  fail=1
fi

echo
if [[ $fail -ne 0 ]]; then
  echo "One or more patches could not be applied." >&2
  exit 1
fi

# Verify rather than assume: a patch that applied cleanly can still be a no-op if the
# upstream code moved underneath it.
echo "Verifying:"
if [[ -d "$M3_VENV" ]]; then
  # Block style, not flow: the '{' in ${HOME} would break a flow mapping.
  printf 'ymmsl_version: v0.2\nsettings:\n  probe: ${HOME}/x\n' > /tmp/pds_patch_probe.ymmsl
  got=$("$M3_VENV/bin/python" -c "
from muscle3.muscle_manager import load_configuration
print(load_configuration(['/tmp/pds_patch_probe.ymmsl']).settings['probe'])" 2>&1 || true)
  rm -f /tmp/pds_patch_probe.ymmsl
  if [[ "$got" == "$HOME/x" ]]; then
    echo "  muscle3 expands \${VAR} in settings: yes"
  else
    echo "  muscle3 does NOT expand \${VAR} in settings (got '$got')" >&2
    exit 1
  fi
  if "$M3_VENV/bin/python" -c "
import muscle3.muscle_manager as m; raise SystemExit(0 if hasattr(m, 'save_input_files') else 1)"; then
    echo "  muscle3 copies input yMMSL into <run_dir>/input/: yes"
  else
    echo "  muscle3 does NOT copy input yMMSL into the run dir" >&2
    exit 1
  fi
fi
echo "All patches applied."
