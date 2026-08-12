# Shared build logic for the PDS actor packages that are a plain
# "git clone + venv + pip install -e ." install: IMAS-MUSCLE3, Waveform-Editor,
# TORAX-MUSCLE3. Sourced by build_<name>.sh; not run directly.
#
# Produces a versioned install under $PDS_SOFTWARE_ROOT and a matching Lmod
# modulefile under $PDS_MODULES_ROOT, so `module load <module-name>/<version>`
# works the same way as the official cluster modules, but tracking whatever
# branch/tag you point it at.
#
# The generated modulefile only ever prepends PATH to the venv's bin/ -- the
# same as a plain `source venv/bin/activate` -- and deliberately never touches
# PYTHONPATH, so it can't leak into other actors' venvs the way a module with
# a PYTHONPATH prepend can (see bin/pds-run's comment on the MUSCLE3 module
# for why that matters).
#
# The Lmod module name (first arg, e.g. "PDS-IMAS-MUSCLE3") is deliberately
# decoupled from the software install path and the $EBROOT* variable name,
# which both use the name with any "PDS-" prefix stripped. This isn't just
# cosmetic: several workflow .ymmsl(.template) files (e.g.
# torax_nice_controller, the metis_*_from_dina workflows,
# workflows/lib/easybuild_programs.ymmsl) specify actor implementations via a
# bare `modules: NICE` / `modules: IMAS-MUSCLE3` key -- MUSCLE3's own
# per-actor `module load` mechanism, completely separate from
# local_programs.ymmsl's $EBROOT*-based virtual_env: approach. If our custom
# builds used those same bare names, `module load NICE` inside one of those
# actor subprocesses could resolve to the official (RPATH-broken) module
# instead of ours, depending on Lmod's tie-breaking across merged module
# trees -- a real, silent-failure risk, not a hypothetical one. The PDS-
# prefix makes that collision structurally impossible.

build_venv_actor_module() {
  local module_name="$1" module_version="$2" git_url="$3" branch="$4"
  shift 4
  local pip_overrides=("$@") # optional: extra `pip install X==Y` pins applied after -e .

  local bare_name="${module_name#PDS-}"
  local prefix="$PDS_SOFTWARE_ROOT/$bare_name/$module_version"
  local module_dir="$PDS_MODULES_ROOT/$module_name"
  local module_file="$module_dir/$module_version.lua"
  local ebroot_var
  ebroot_var="EBROOT$(echo "$bare_name" | tr '[:lower:]' '[:upper:]' | tr -d '-')"

  echo "############## Building $module_name/$module_version (branch: $branch) ##############"
  mkdir -p "$prefix" "$module_dir"

  module purge
  module load Python

  if [[ ! -d "$prefix/src/.git" ]]; then
    git clone "$git_url" "$prefix/src"
  fi
  (
    cd "$prefix/src"
    git fetch --quiet origin
    git checkout "$branch"
    git pull --quiet origin "$branch" || true
  )

  if [[ ! -d "$prefix/venv" ]]; then
    python3 -m venv "$prefix/venv"
  fi
  # shellcheck disable=SC1091
  . "$prefix/venv/bin/activate"
  pip install --upgrade pip setuptools wheel
  pip install -e "$prefix/src"
  if [[ ${#pip_overrides[@]} -gt 0 ]]; then
    pip install "${pip_overrides[@]}"
  fi
  deactivate
  module purge

  cat > "$module_file" << EOF
-- Custom PDS build of $bare_name, tracking '$branch'.
-- Rebuild/update to a new version: re-run this repo's
-- setup_files/custom_modules/build_$(echo "$bare_name" | tr '[:upper:]' '[:lower:]' | tr -d '-').sh <new-version> <branch>
-- with a different <new-version>, so old and new coexist side by side.

help([[
$module_name (custom PDS build of $bare_name)

Source: $git_url @ $branch
Installed: $prefix
]])

whatis("Description: Custom PDS build of $bare_name ($git_url @ $branch)")

prepend_path("PATH", "$prefix/venv/bin")
setenv("$ebroot_var", "$prefix")
EOF

  echo "Installed $module_name/$module_version -> $prefix/venv"
  echo "Module:    $module_file"
}
