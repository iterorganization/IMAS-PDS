_run_workflow_complete() {
  local cur prev base dir

  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  base="$(pwd)"

  # First argument: list workflows/
  if [[ $COMP_CWORD -eq 1 ]]; then
    COMPREPLY=()
    if [[ -d "$base/workflows" ]]; then
      for d in "$base/workflows"/*; do
        [[ -d "$d/scenarios" ]] || continue
        name="$(basename "$d")"
        [[ "$name" == "$cur"* ]] && COMPREPLY+=("$name")
      done
    fi
    return 0
  fi

  # Second argument: list scenarios for the chosen workflow
  if [[ $COMP_CWORD -eq 2 ]]; then
    dir="$base/workflows/$prev/scenarios"
    if [[ -d "$dir" ]]; then
      COMPREPLY=($(compgen -W "$(ls -1 "$dir" 2>/dev/null)" -- "$cur"))
    fi
    return 0
  fi
}

_complete_bash_wrapper() {
  # If we're NOT completing "bash run_workflow.sh", let Bash behave normally
  if [[ "${COMP_WORDS[1]}" != "run_workflow.sh" && \
        "${COMP_WORDS[1]}" != "./run_workflow.sh" ]]; then
    return 124   # <-- This tells bash: "use your default completion"
  fi

  # Otherwise, delegate to your original function
  COMP_WORDS=("${COMP_WORDS[@]:1}")
  COMP_CWORD=$((COMP_CWORD - 1))
  _run_workflow_complete
}

complete -o bashdefault -o default -F _complete_bash_wrapper bash
