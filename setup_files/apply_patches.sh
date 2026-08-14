#!/bin/bash
# Apply the local patches PDS depends on. Run after the IMAS-MUSCLE3 and Waveform-Editor
# installs exist (setup_files/custom_modules/build_*.sh). Idempotent: re-running is a no-op.
#
# Both patches are unmerged upstream and both are load-bearing:
#
#   muscle3-manager-env-vars-and-input-copies   two changes to muscle_manager.py:
#     (a) expands ${PDS_REPO} / ${SCENARIOS_REPO} in setting values. Stock muscle3 uses
#         them verbatim, so without this the actors receive a literal "${PDS_REPO}/...".
#     (b) copies the yMMSL files given on the command line into <run_dir>/input/, numbered
#         in merge order. The run dir otherwise keeps only configuration.ymmsl, the
#         resolved and flattened form.
#
#   waveform-editor-relative-imports      relative data URIs in a scenario's waveforms.yaml.
#     Without it a scenario has to name its data by absolute path, which is only correct
#     on the machine it was written on.
set -euo pipefail

PDS_REPO="${PDS_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PATCHES="$PDS_REPO/ci/patches"
# Prefer the module-provided installs ($EBROOT* from `module load PDS`, or the same names
# exported by ci/run_test_workflows.sh for its local builds); fall back to the old
# per-user run/ layout when neither is set.
M3_VENV="${M3_VENV:-${EBROOTIMASMUSCLE3:+$EBROOTIMASMUSCLE3/venv}}"
M3_VENV="${M3_VENV:-$PWD/IMAS-MUSCLE3/venv}"
WE_DIR="${WE_DIR:-${EBROOTWAVEFORMEDITOR:-$PWD/Waveform-Editor}}"
# Two layouts in use. Older checkouts have the repo cloned directly into
# run/Waveform-Editor, so the prefix IS the checkout. custom_modules/build_*.sh instead
# creates <prefix>/{src,venv} and does `pip install -e <prefix>/src`, so the checkout is
# one level down -- and because that install is editable, patching src/ is what takes
# effect.
[[ -d "$WE_DIR/.git" ]] || [[ ! -d "$WE_DIR/src/.git" ]] || WE_DIR="$WE_DIR/src"

# A shared module install belongs to whoever built it, so patching it in place is not
# possible -- and silently skipping would leave a run that fails much later, for reasons
# that look nothing like a missing patch.
for target in "$M3_VENV" "$WE_DIR"; do
  if [[ -e "$target" && ! -w "$target" ]]; then
    cat >&2 <<MSG
apply_patches: $target is not writable.

It is a shared install owned by someone else -- most likely one of the PDS-* modules. The
two patches in ci/patches/ cannot be applied to it, and without them:

  * \${PDS_REPO} / \${SCENARIOS_REPO} in cases/ reach the actors as literal text;
  * relative data URIs in a scenario's waveforms.yaml resolve against each MUSCLE3
    instance's own work directory instead of the scenario, and the reads fail.

Two ways forward:

  1. Ask whoever owns the module to fold ci/patches/ into their
     setup_files/custom_modules/build_*.sh, and rebuild. This is the right fix.
  2. Build your own copies and point the module variables at them for your session:
       cd \$PDS_REPO/setup_files/custom_modules
       bash build_imas_muscle3.sh 1.0.0-local
       bash build_waveform_editor.sh 0.3.1-local feature/reference-tendency-old
       module use \$HOME/public/modules
       module load PDS-IMAS-MUSCLE3 PDS-Waveform-Editor
       bash \$PDS_REPO/setup_files/apply_patches.sh
     The rest of the stack (NICE, TORAX, the IMAS modules) still comes from the module.
MSG
    exit 1
  fi
done

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
  echo "  SKIPPED: no venv at $M3_VENV -- run custom_modules/build_imas_muscle3.sh first" >&2
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
  echo "  SKIPPED: no checkout at $WE_DIR -- run custom_modules/build_waveform_editor.sh first" >&2
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

# Verify the Waveform-Editor patch in the interpreter that will actually import it, not
# just in the checkout -- an editable install can point somewhere other than $WE_DIR.
WE_PY="${WE_PY:-${EBROOTWAVEFORMEDITOR:+$EBROOTWAVEFORMEDITOR/venv/bin/python}}"
if [[ -x "${WE_PY:-}" ]]; then
  if "$WE_PY" -c "
import inspect
from waveform_editor.import_resolver import ImportResolver
raise SystemExit(0 if 'base_dir' in inspect.signature(ImportResolver.__init__).parameters else 1)"; then
    echo "  Waveform-Editor resolves relative import URIs: yes"
  else
    echo "  Waveform-Editor does NOT resolve relative import URIs" >&2
    echo "    The venv is importing a different copy than $WE_DIR." >&2
    exit 1
  fi
fi
echo "All patches applied."
