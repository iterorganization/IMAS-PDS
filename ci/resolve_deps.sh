#!/bin/bash
# Sets up the environment of one target combination from the repository manifest deps.yaml.
# Source it (bash), do not execute it:
#     export COMBO=intel-2025b-dd4; source ci/resolve_deps.sh
# It is sourced by ci/run_test_workflows.sh (CI) and by bin/pds-create-case / bin/pds-run-case.sbatch
# when the environment is not yet set up; source ci/pds_env.sh after it (PATH, PYTHONPATH, YMMSL_PATH, IMAS_VERSION).
#
# Steps:
#  1. reads deps.yaml (repository root, or DEPS_FILE) with the system Python (/usr/bin/python3,
#     before any module is loaded; PyYAML when importable, otherwise a reader for the subset of
#     YAML used by deps.yaml);
#  2. module purge, `module use` of the site tree, then `module use -a` of the manifest's
#     module_paths (appended: a module name that exists in the site tree is taken from there);
#     loads the combination's `modules` (and its `local_modules` when DEPS_LOCAL_MODULES=1);
#  3. resolves every component, first match wins:
#       local          when the component's src_env variable (e.g. WAVEFORM_COOKER_SRC) is set:
#                      that source tree, used in place, before any other path (developer override)
#       a  module      `module load <module>`
#       b  easyconfig  `eb <easyconfig> --robot` into $DEPS_OVERLAY (EASYBUILD_PREFIX, 2 build
#                      processes, umask 022 unless set) in a clean module environment, then
#                      `module load`; only outside Bamboo, when $DEPS_OVERLAY is writable, the
#                      easyconfig exists, eb is available (or the manifest's easybuild_module loads)
#                      and DEPS_NO_BUILD is unset
#       local          under Bamboo, the checkout $bamboo_build_working_directory/<checkout>; used in place
#                      (PYTHONPATH=<tree>, <root_env>=<tree>)
#       c  git         fetch of <ref> from <git> into $CI_DEPS_DIR/src/<name>, `install` run there
#                      with DEP_PREFIX=$CI_DEPS_DIR/prefix/<name>
#     PDS additions: components with load: false are only checked (module is-avail) and exported;
#     each component's env_var is exported with the value used (module name, or source tree / prefix).
#  4. writes $CI_DEPS_DIR/env.sh (the component part of the environment, with the path taken
#     per component), sources it and runs each component's `check`.
#
# Variables:
#   COMBO (alias DEP_COMBO)  combination of deps.yaml (required), e.g. intel-2023b-dd3
#   MODULES                  space-separated module list used instead of the combination's
#                            `modules` (transition override for CI plans that still pass MODULES)
#   DEPS_FILE                manifest (default: the nearest deps.yaml above ci/, i.e. at the
#                            repository root)
#   CI_DEPS_DIR              directory of env.sh and of source-built components (default <repository root>/ci-deps)
#   DEPS_OVERLAY             EasyBuild install prefix of the user tree (default /work/projects/pds/stack)
#   DEPS_NO_BUILD=1          skip path b
#   DEPS_NO_SOURCE=1         skip path c: a missing module is an error instead of a source build
#   DEPS_LOCAL_MODULES=1     also load the combination's `local_modules`
#   SITE_MODULEPATH          site module tree (default /work/imas/etc/modules/all)
# Returns non-zero (without exiting the calling shell) on any failure.

# PDS: the instance run scripts that muscle_manager generates do a plain `module load` (no
# --ignore_cache); a stale Lmod cache on the Bamboo agent made CHEASE's dependency "unknown".
export LMOD_IGNORE_CACHE=${LMOD_IGNORE_CACHE:-yes}

_rd_main() {
    local combo=${COMBO:-${DEP_COMBO:-}}
    if [[ -z "$combo" ]]; then
        echo "resolve_deps: ERROR: set COMBO to a combination of deps.yaml (e.g. intel-2025b-dd4)" >&2
        return 1
    fi
    local here
    here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P) || return 1
    local deps_file=${DEPS_FILE:-}
    if [[ -z "$deps_file" ]]; then
        # nearest deps.yaml in the directories above ci/ (the repository root)
        local up=$here
        while [[ "$up" != / && ! -f "$up/deps.yaml" ]]; do up=$(dirname "$up"); done
        deps_file=$up/deps.yaml
    fi
    if [[ ! -r "$deps_file" ]]; then
        echo "resolve_deps: ERROR: manifest $deps_file not readable" >&2
        return 1
    fi
    deps_file=$(cd "$(dirname "$deps_file")" && pwd -P)/$(basename "$deps_file")
    local deps_dir=${CI_DEPS_DIR:-$(dirname "$here")/ci-deps}   # PDS: repository root, bin/ scripts run from anywhere
    local overlay=${DEPS_OVERLAY:-/work/projects/pds/stack}
    local site_path=${SITE_MODULEPATH:-/work/imas/etc/modules/all}
    local sys_python=/usr/bin/python3
    [[ -x "$sys_python" ]] || sys_python=python3

    mkdir -p "$deps_dir" || return 1
    local records="$deps_dir/deps_$combo.tsv"
    # env.sh of a previous run must not enter the environment set up below
    rm -f "$deps_dir/env.sh"

    echo "resolve_deps: manifest $deps_file, combination $combo"
    "$sys_python" -s -E - "$deps_file" "$combo" > "$records" <<'EOF' || return 1
import sys

def scalar(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    return text

def subset_load(path):
    """Reader for the YAML subset of deps.yaml: block mappings, block lists of scalars,
    plain or quoted scalars, folded scalars (>-), comments."""
    lines = []
    for raw in open(path):
        line = raw.rstrip("\n")
        if "\t" in line[:len(line) - len(line.lstrip())]:
            raise SystemExit("deps.yaml: tab indentation not supported")
        stripped = line.split(" #")[0].rstrip() if not line.lstrip().startswith("#") else ""
        if line.lstrip().startswith("#") or not stripped.strip():
            lines.append((None, line))
        else:
            lines.append((len(line) - len(line.lstrip()), stripped.strip()))
    pos = 0

    def block(indent):
        nonlocal pos
        result = None
        while pos < len(lines):
            ind, text = lines[pos]
            if ind is None:
                pos += 1
                continue
            if ind < indent:
                break
            if ind > indent:
                raise SystemExit("deps.yaml: unexpected indentation: " + text)
            if text.startswith("- "):
                result = [] if result is None else result
                if not isinstance(result, list):
                    raise SystemExit("deps.yaml: list item inside a mapping: " + text)
                result.append(scalar(text[2:]))
                pos += 1
                continue
            key, sep, value = text.partition(":")
            if not sep:
                raise SystemExit("deps.yaml: cannot read line: " + text)
            result = {} if result is None else result
            if not isinstance(result, dict):
                raise SystemExit("deps.yaml: mapping key inside a list: " + text)
            value = value.strip()
            pos += 1
            if value in (">-", ">"):
                parts = []
                while pos < len(lines) and (lines[pos][0] is None or lines[pos][0] > indent):
                    if lines[pos][0] is not None:
                        parts.append(lines[pos][1])
                    pos += 1
                result[key.strip()] = " ".join(parts)
            elif value:
                result[key.strip()] = scalar(value)
            else:
                nxt = pos
                while nxt < len(lines) and lines[nxt][0] is None:
                    nxt += 1
                child = lines[nxt][0] if nxt < len(lines) else -1
                if child is not None and child > indent:
                    result[key.strip()] = block(child)
                elif (child == indent and lines[nxt][1].startswith("- ")):
                    result[key.strip()] = block(child)
                else:
                    result[key.strip()] = None
        return result

    return block(0)

path, combo = sys.argv[1], sys.argv[2]
try:
    import yaml
    data = yaml.safe_load(open(path))
    reader = "PyYAML " + yaml.__version__
except ImportError:
    data = subset_load(path)
    reader = "built-in subset reader"

combos = data.get("combinations") or {}
if combo not in combos:
    raise SystemExit("deps.yaml: combination %r not found (known: %s)" % (combo, ", ".join(combos)))

def pick(value):
    if isinstance(value, dict):
        value = value.get(combo, "")
    if isinstance(value, bool):  # PDS: load: false -> "false" with PyYAML and the subset reader alike
        value = "true" if value else "false"
    value = "" if value is None else str(value)
    if "\x1f" in value or "\n" in value:
        raise SystemExit("deps.yaml: control character or newline in value %r" % value)
    return value

print("R", reader, sep="\x1f")
for p in data.get("module_paths") or []:
    print("P", pick(p), sep="\x1f")
if data.get("easybuild_module"):
    print("E", pick(data["easybuild_module"]), sep="\x1f")
for m in combos[combo].get("modules") or []:
    print("M", pick(m), sep="\x1f")
for m in combos[combo].get("local_modules") or []:
    print("L", pick(m), sep="\x1f")
fields = ("module", "easyconfig", "src_env", "checkout", "git", "ref", "install", "root_env", "check",
          "env_var", "load")  # PDS: env_var, load
for name, comp in (data.get("components") or {}).items():
    print("C", name, *(pick(comp.get(k)) for k in fields), sep="\x1f")
EOF

    local kind a b c d e f g h i j k l   # PDS: k l for the two extra C fields
    local -a mpaths=() mods=() lmods=() comps=()
    local eb_module="" reader=""
    while IFS=$'\x1f' read -r kind a b c d e f g h i j k l; do
        case "$kind" in
            R) reader=$a ;;
            P) mpaths+=("$a") ;;
            E) eb_module=$a ;;
            M) mods+=("$a") ;;
            L) lmods+=("$a") ;;
            C) comps+=("$a") ;;
        esac
    done < "$records"
    echo "resolve_deps: read with $reader"

    if ! type module >/dev/null 2>&1; then
        source /etc/profile.d/modules.sh || return 1
    fi
    module purge || return 1
    module use "$site_path" || return 1
    local p
    for p in "${mpaths[@]}"; do
        if [[ -d "$p" ]]; then
            module use -a "$p" || return 1
            echo "resolve_deps: module path $p (after the site tree)"
        else
            echo "resolve_deps: module path $p absent, skipped"
        fi
    done

    local -a load=()
    if [[ -n "${MODULES:-}" ]]; then
        read -r -a load <<< "$MODULES"
        echo "resolve_deps: module list from MODULES (override of combination $combo)"
    else
        load=("${mods[@]}")
    fi
    if [[ ${#load[@]} -eq 0 ]]; then
        echo "resolve_deps: ERROR: empty module list for $combo" >&2
        return 1
    fi
    if [[ "${DEPS_LOCAL_MODULES:-0}" == 1 ]]; then
        load+=("${lmods[@]}")
    fi
    local m
    for m in "${load[@]}"; do
        module load "$m" || { echo "resolve_deps: ERROR: module load $m failed" >&2; return 1; }
    done

    local env_file="$deps_dir/env.sh"
    {
        echo "# Written by ci/resolve_deps.sh for combination $combo from $deps_file"
        echo "# Sourced after the combination's modules are loaded."
    } > "$env_file"

    local name mod ec src_env checkout git ref install root_env check env_var load   # PDS: env_var load
    local -a checks=()
    while IFS=$'\x1f' read -r kind name mod ec src_env checkout git ref install root_env check env_var load; do
        [[ "$kind" == C ]] || continue
        local how="" tree="" explicit=""
        # explicitly exported source tree: used before the module (developer override)
        if [[ -n "$src_env" && -n "${!src_env:-}" ]]; then
            tree=${!src_env}
            tree=$(cd "$tree" && pwd -P) || { echo "resolve_deps: ERROR: $name: no directory ${!src_env}" >&2; return 1; }
            how="local"; explicit=" (explicit $src_env)"
        fi
        # PDS: load: false -> actor-only component: verify that the module exists, do not load it here
        if [[ -z "$how" && -n "$mod" && "${load,,}" == false ]]; then
            if module is-avail "$mod" >/dev/null 2>&1; then
                how="x"
            else
                echo "resolve_deps: ERROR: $name: module $mod not found (load: false, needed by the actor scripts; check module_paths and the module tree)" >&2
                return 1
            fi
        fi
        # a: module
        if [[ -z "$how" && -n "$mod" ]] && module is-avail "$mod" >/dev/null 2>&1; then
            if module load "$mod" >/dev/null 2>&1; then
                how="a"
            else
                echo "resolve_deps: $name: module $mod found but does not load"
            fi
        fi
        # b: EasyBuild build into the user tree, in a subshell with a clean module environment
        if [[ -z "$how" && -n "$mod" && -n "$ec" && -z "${bamboo_buildKey:-}" && -z "${DEPS_NO_BUILD:-}" \
              && -f "$ec" && -d "$overlay" && -w "$overlay" ]]; then
            echo "resolve_deps: $name: building $mod from $ec into $overlay (log $deps_dir/eb_$name.log)"
            if ( module purge || exit 1
                 if ! command -v eb >/dev/null 2>&1 && [[ -n "$eb_module" ]]; then module load "$eb_module" || exit 1; fi
                 command -v eb >/dev/null 2>&1 || { echo "eb not available"; exit 1; }
                 export EASYBUILD_PREFIX=${EASYBUILD_PREFIX:-$overlay} EASYBUILD_PARALLEL=${EASYBUILD_PARALLEL:-2} \
                        EASYBUILD_UMASK=${EASYBUILD_UMASK:-022}
                 eb "$ec" --robot ) > "$deps_dir/eb_$name.log" 2>&1; then
                module use -a "$overlay/modules/all" || return 1
                if module load "$mod" >/dev/null 2>&1; then how="b"; fi
            else
                echo "resolve_deps: $name: eb failed (see $deps_dir/eb_$name.log)"
            fi
        fi
        # local: Bamboo checkout, used in place
        if [[ -z "$how" ]]; then
            if [[ -n "$checkout" && -n "${bamboo_build_working_directory:-}" \
                    && -d "${bamboo_build_working_directory}/$checkout" ]]; then
                tree=${bamboo_build_working_directory}/$checkout
            fi
            if [[ -n "$tree" ]]; then
                tree=$(cd "$tree" && pwd -P) || { echo "resolve_deps: ERROR: $name: no directory $tree" >&2; return 1; }
                how="local"
            fi
        fi
        # c: git ref, installed into the job directory
        if [[ -z "$how" ]]; then
            if [[ -n "${DEPS_NO_SOURCE:-}" ]]; then   # PDS
                echo "resolve_deps: ERROR: $name: module ${mod:-?} not available and source builds are disabled (DEPS_NO_SOURCE=1)" >&2
                return 1
            fi
            if [[ -z "$git" || -z "$ref" || -z "$install" ]]; then
                echo "resolve_deps: ERROR: $name: no module ${mod:-?}, no source tree, no git/ref/install" >&2
                return 1
            fi
            local src="$deps_dir/src/$name" prefix="$deps_dir/prefix/$name"
            rm -rf "$src" "$prefix"
            mkdir -p "$src" || return 1
            echo "resolve_deps: $name: fetching $ref of $git"
            if ! { git -C "$src" init -q \
                   && GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND="ssh -o BatchMode=yes" \
                      timeout 300 git -C "$src" fetch -q --depth 1 "$git" "$ref" \
                   && git -C "$src" checkout -q FETCH_HEAD; }; then
                echo "resolve_deps: ERROR: $name: cannot fetch $ref of $git; set ${src_env:-a source tree}" >&2
                return 1
            fi
            if ! ( cd "$src" && DEP_PREFIX=$prefix && export DEP_PREFIX && eval "$install" ) \
                    > "$deps_dir/install_$name.log" 2>&1; then
                echo "resolve_deps: ERROR: $name: install failed (see $deps_dir/install_$name.log)" >&2
                return 1
            fi
            local -a sp=("$prefix"/lib/python3*/site-packages)
            how="c"
        fi

        case "$how" in
            a|b)
                echo "resolve_deps: $name: path $how, module $mod"
                {
                    echo "# $name: path $how (module)"
                    echo "module load $mod"
                } >> "$env_file" ;;
            x)  # PDS: load: false
                echo "resolve_deps: $name: module $mod available, not loaded (load: false)"
                echo "# $name: module $mod available, not loaded (load: false)" >> "$env_file" ;;
            local)
                local rev=""
                if git -C "$tree" rev-parse --git-dir >/dev/null 2>&1; then
                    rev=" ($(git -C "$tree" log -1 --format='%h %cd' --date=short) $(git -C "$tree" rev-parse --abbrev-ref HEAD))"
                fi
                echo "resolve_deps: $name: path local$explicit, source tree $tree$rev"
                {
                    echo "# $name: path local (source tree $tree$rev)"
                    echo "export PYTHONPATH=\"$tree\${PYTHONPATH:+:\$PYTHONPATH}\""
                    if [[ -n "$root_env" ]]; then echo "export $root_env=\"$tree\""; fi
                } >> "$env_file" ;;
            c)
                local rev
                rev=$(git -C "$src" log -1 --format='%h %cd' --date=short)
                echo "resolve_deps: $name: path c, $ref of $git ($rev) installed in $prefix"
                {
                    echo "# $name: path c ($ref of $git, $rev)"
                    if [[ -d "$prefix/bin" ]]; then echo "export PATH=\"$prefix/bin:\$PATH\""; fi
                    if [[ -d "${sp[0]}" ]]; then echo "export PYTHONPATH=\"${sp[0]}\${PYTHONPATH:+:\$PYTHONPATH}\""; fi
                    if [[ -n "$root_env" ]]; then echo "export $root_env=\"$prefix\""; fi
                } >> "$env_file" ;;
        esac
        # PDS: export env_var with the value the ymmsl `modules:` lines must use
        if [[ -n "$env_var" ]]; then
            local val=""
            case "$how" in a|b|x) val=$mod ;; local) val=$tree ;; c) val=$prefix ;; esac
            echo "export $env_var=\"$val\"" >> "$env_file"
        fi
        if [[ -n "$check" ]]; then
            if [[ "$how" == x ]]; then check="( module load \"$mod\" >/dev/null 2>&1 && $check )"; fi   # PDS
            checks+=("$name"$'\t'"$check")
        fi
    done < "$records"

    echo "resolve_deps: sourcing $env_file"
    source "$env_file" || { echo "resolve_deps: ERROR: sourcing $env_file failed" >&2; return 1; }
    local entry
    for entry in "${checks[@]}"; do
        echo "resolve_deps: check ${entry%%$'\t'*}"
        eval "${entry#*$'\t'}" || { echo "resolve_deps: ERROR: check of ${entry%%$'\t'*} failed" >&2; return 1; }
    done
    return 0
}

if _rd_main; then
    unset -f _rd_main
    return 0 2>/dev/null || exit 0
fi
unset -f _rd_main
return 1 2>/dev/null || exit 1
