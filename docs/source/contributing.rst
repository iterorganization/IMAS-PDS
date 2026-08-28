.. _`contributing`:

Contributing
============

Development environment
-----------------------

You do not need the module stack to work on the Python, the docs or the CI
scripts -- only to *run* a workflow. For everything else:

.. code-block:: bash

  uv venv
  source .venv/bin/activate
  uv sync --all-extras

If you do not have ``uv``, ``pip install uv`` first, or let
``setup_files/ensure_uv.sh`` bootstrap one into ``.uv-bootstrap/``.

Before you push
---------------

CI runs these four commands. Run them locally before pushing:

.. code-block:: bash

  ruff format --check --diff .   # formatting
  ruff check .                   # linting
  uv run ty check .              # type checking
  uv run make -C docs html       # documentation

``ruff check --fix .`` and ``ruff format .`` apply the first two automatically.
See :ref:`code style and linting` for what the rules are and why.

.. note::

   CI runs Ruff through ``astral-sh/ruff-action``, not through ``uv``, so it uses
   its own Ruff version. A locally pinned Ruff can disagree with CI over a rule
   added or changed between the two versions. If CI complains about something
   that passes locally, check the versions before anything else.

Building the documentation
--------------------------

.. code-block:: bash

  uv sync --extra docs
  uv run make -C docs clean html

Warnings are errors (``-W --keep-going`` in ``docs/Makefile``). That is
deliberate: it is what catches a broken ``:ref:``, a page missing from a
toctree, or a dead intersphinx inventory. Do not relax it to get a build
through.

Run ``clean`` first when you have added or removed a page. A stale ``_build``
can hide an orphaned document that CI, building from scratch, will fail on.

The built HTML lands in ``docs/_build/html``.

.. _`docs-freshness-check`:

Keeping the docs true
---------------------

A green docs build proves the *markup* is valid. It does not prove the prose is
true -- it cannot tell that a page describes a script that was deleted, which is
how the documentation drifted so far behind the code before.

So when you change a path, a script name or a workflow name, grep the docs for
it. This catches the retired vocabulary:

.. code-block:: bash

  ! grep -rniE 'run_workflow\.sh|scenario_config\.env|PLACEHOLDER\]|apply_patches\.sh|bin/pds-run[^-]' \
      docs/_build/html --include='*.html' \
      --exclude-dir=courses --exclude=contributing.html

And this catches prose naming a file that no longer exists:

.. code-block:: bash

  grep -rhoE '``[a-zA-Z0-9_./-]+\.(sh|py|ymmsl|xml|yaml|eb)``' docs/source --include='*.rst' \
    | tr -d '`' | sort -u | while read -r f; do
        [ -e "$f" ] || echo "MISSING: $f"
      done

Opening a pull request
----------------------

- Branch off ``master`` and open the pull request against it. Feature work that
  builds on another unmerged branch should target that branch instead, so the
  diff shows only your change.
- Keep a commit to one concern. A change that can break someone else's build --
  a dependency bump, a pinned version -- belongs in its own commit so it can be
  reverted alone.
- Say *why* in the commit message. The mechanics are visible in the diff; the
  reasoning is not, and it is what the next reader needs.
- CI runs linting, then the docs build. Both must pass.

Running the integration tests
-----------------------------

The end-to-end tests are **not** on GitHub. They need the module stack, MATLAB
and real IMAS data, so they run on the ITER cluster under Bamboo, which calls:

.. code-block:: bash

  bash ci/run_test_workflows.sh

That builds the module environment, then runs eight single-actor smoke tests
followed by five full cases end to end. It takes a long time and needs a
scenarios checkout. If your change touches ``workflows/``, ``bin/`` or the
easyconfigs, expect that suite -- not GitHub CI -- to be what actually catches a
regression.

``ci/check_ymmsl.py`` is the cheap subset of that: it resolves and flattens every
case statically, with no data and no MUSCLE3, and it does run in GitHub CI.

Repository layout
-----------------

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Directory
     - Contents
   * - ``bin/``
     - The user-facing entry points: ``pds-create-case``,
       ``pds-run-case.sbatch``.
   * - ``workflows/``
     - One directory per workflow, plus ``lib/`` (shared program definitions and
       in-repo actors) and the per-workflow utility directories.
   * - ``cases/overrides/``
     - Per-shot tuning. Generated cases and run output also land under
       ``cases/``, and are not tracked.
   * - ``setup_files/``
     - ``easyconfigs/`` for the module stack, and the ``setup_*.sh`` scripts for
       a from-source build.
   * - ``ci/``
     - The integration test driver and the static ymmsl checker.
   * - ``pds/``
     - The Python package. Deliberately tiny -- the module puts the repo root on
       ``PYTHONPATH`` so there is no install step.
   * - ``controllers/``
     - MATLAB/Simulink sources for the PCSSP magnetic controller.
   * - ``visualization/``
     - Recorder configurations, referenced by workflow settings.
   * - ``pds_validation_tests/``
     - IMAS-Validator rulesets, loaded by the validator actor.
   * - ``docs/``
     - This documentation.
