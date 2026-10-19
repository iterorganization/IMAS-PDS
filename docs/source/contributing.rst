.. _`contributing`:

Contributing
============

Development environment
-----------------------

The module stack is only needed to *run* a workflow. For the Python, the docs or the CI
scripts:

.. code-block:: bash

  uv venv
  source .venv/bin/activate
  uv sync --all-extras

Without ``uv``, either ``pip install uv`` or let ``setup_files/ensure_uv.sh`` bootstrap
one into ``.uv-bootstrap/``.

Before you push
---------------

CI runs these. Run them locally first:

.. code-block:: bash

  ruff format --check --diff .        # formatting
  ruff check .                        # linting
  uv run ty check .                   # type checking
  uv run python ci/check_ymmsl.py     # every case resolves and flattens
  uv run make -C docs html            # documentation

``ruff format .`` and ``ruff check --fix .`` apply the first two automatically. See
:ref:`code style and linting` for the rules.

.. note::

   CI runs Ruff through ``astral-sh/ruff-action``, not ``uv``, so it uses its own Ruff
   version and a locally pinned one can disagree over a rule added between the two. If
   CI complains about something that passes locally, check the versions first.

Building the documentation
--------------------------

.. code-block:: bash

  uv sync --extra docs
  uv run make -C docs clean html

Warnings are errors (``-W --keep-going`` in ``docs/Makefile``) -- that is what catches
a broken ``:ref:``, a page missing from a toctree, or a dead intersphinx inventory. Do
not relax it to get a build through.

Run ``clean`` after adding or removing a page: a stale ``_build`` can hide an orphaned
document that CI, building from scratch, will fail on. The HTML lands in
``docs/_build/html``.

.. _`docs-freshness-check`:

Keeping the docs true
---------------------

A green docs build proves the *markup* is valid, not that the prose is true -- it
cannot tell that a page describes a script that was deleted, which is how the
documentation drifted so far behind the code before. So when you change a path, a script
name or a workflow name, grep the docs for it. This catches retired vocabulary:

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

Dependencies (deps.yaml)
------------------------

``deps.yaml`` at the repository root is the single place where external versions are
pinned: for each component the module name, the easyconfig that builds it and, for a
source build, an optional git URL, ref and install step. There is one combination,
``intel-2025b-dd4``.

``ci/resolve_deps.sh`` is sourced by ``ci/run_test_workflows.sh`` and by the ``bin/``
scripts when the environment is not set up. It exports one ``PDS_MOD_<NAME>`` variable
per component, and ``workflows/lib/easybuild_programs.ymmsl`` references them as
``${PDS_MOD_NAME:?...}``, so changing a module is a one-line change in ``deps.yaml``.

Promotion rule: a line naming a ``.dev`` module or a PR head (``refs/pull/N/head``) is
temporary and is switched back to the release module once it exists.
``grep -n 'refs/pull\|\.dev' deps.yaml`` lists the pending ones.

``module load PDS`` (the umbrella module PDS/1.0) remains a convenience; its dependency
list must match the manifest's manager-side modules (its future is still to be decided).

Running the integration tests
-----------------------------

The end-to-end tests are **not** on GitHub -- they need the module stack, MATLAB and
real IMAS data, so they run on the ITER cluster under Bamboo, which calls:

.. code-block:: bash

  bash ci/run_test_workflows.sh

That sets up the environment from ``deps.yaml`` (``ci/resolve_deps.sh`` + ``ci/pds_env.sh``), then runs eight single-actor smoke tests followed
by five full cases end to end. It is slow and needs a scenarios checkout. If your change
touches ``workflows/``, ``bin/`` or the easyconfigs, that suite -- not GitHub CI -- is
what will catch a regression.

``ci/check_ymmsl.py`` is the cheap subset: it resolves and flattens every case
statically, with no data and no MUSCLE3. It is not wired into CI, so run it
yourself after changing a workflow or a case override.

Repository layout
-----------------

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Directory
     - Contents
   * - ``bin/``
     - The user-facing entry points: ``pds-configure``, ``pds-tendencies``,
       ``pds-create-case``, ``pds-run-case``, ``pds-run-case.sbatch``.
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
     - The Python package. Deliberately tiny; the module puts the repo root on
       ``PYTHONPATH``, so there is no install step.
   * - ``controllers/``
     - MATLAB/Simulink sources for the PCSSP magnetic controller.
   * - ``visualization/``
     - Recorder configurations, referenced by workflow settings.
   * - ``pds_validation_tests/``
     - IMAS-Validator rulesets, loaded by the validator actor.
   * - ``docs/``
     - This documentation.
