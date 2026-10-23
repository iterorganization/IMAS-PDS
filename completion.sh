_pds_create_case_complete() {
  local cur prev base dir

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

  # Second argument: list the shots in preprocessing/dina/shots
  if [[ $COMP_CWORD -eq 2 ]]; then
    dir="$base/preprocessing/dina/shots"
    if [[ -d "$dir" ]]; then
      COMPREPLY=($(compgen -W "$(cd "$dir" && ls -- *.env 2>/dev/null | sed 's/\.env$//')" -- "$cur"))
    fi
    return 0
  fi
}

complete -o bashdefault -o default -F _pds_create_case_complete bin/pds-create-case pds-create-case
