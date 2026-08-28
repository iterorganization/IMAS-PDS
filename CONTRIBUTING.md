# Contributing to IMAS PDS

Full guidance lives in the documentation, under **Contributing**:
<https://docs.iter.org/PDS>. Build it locally with
`uv sync --extra docs && make -C docs html`, or read the source at
[`docs/source/contributing.rst`](docs/source/contributing.rst).

The short version:

```bash
uv venv && source .venv/bin/activate
uv sync --all-extras

# the four checks CI runs
ruff format --check --diff .
ruff check .
uv run ty check .
uv run make -C docs html
```

- Branch off `master` and open the pull request against it.
- Keep a commit to one concern; anything that can break someone else's build
  belongs in its own commit so it can be reverted alone.
- Say *why* in the commit message — the diff already shows what.
- The end-to-end tests are not on GitHub. They need the module stack, MATLAB and
  real IMAS data, and run on the ITER cluster via `ci/run_test_workflows.sh`.
