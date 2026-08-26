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

_pds_create_case_complete() {
  local cur prev base dir scenarios_repo

  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  base="$(pwd)"

  # First argument: list workflows/ (any workflow.ymmsl dir, not just the
  # legacy ones with a scenarios/ subdir)
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

complete -o bashdefault -o default -F _complete_bash_wrapper bash
complete -o bashdefault -o default -F _pds_create_case_complete bin/pds-create-case pds-create-case
