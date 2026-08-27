_pds_create_case_complete() {
  local cur prev base dir scenarios_repo

  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  base="$(pwd)"

  # First argument: list any directory holding a workflow.ymmsl
  if [[ $COMP_CWORD -eq 1 ]]; then
    COMPREPLY=()
    if [[ -d "$base/workflows" ]]; then
      for d in "$base/workflows"/*; do
        [[ -f "$d/workflow.ymmsl" ]] || continue
        name="$(basename "$d")"
        [[ "$name" == "$cur"* ]] && COMPREPLY+=("$name")
      done
    fi
    return 0
  fi

  # Second argument: list shots available in the scenarios repo
  if [[ $COMP_CWORD -eq 2 ]]; then
    scenarios_repo="${SCENARIOS_REPO:-/work/projects/pds/pds-scenarios}"
    dir="$scenarios_repo"
    if [[ -d "$dir" ]]; then
      COMPREPLY=($(compgen -W "$(find "$dir" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | grep -E '^[0-9]+$')" -- "$cur"))
    fi
    return 0
  fi
}

complete -o bashdefault -o default -F _pds_create_case_complete bin/pds-create-case pds-create-case
