.. _`ci configuration`:

CI configuration
================

PDS uses `GitHub Actions <https://docs.github.com/actions>`_ for linting and the
documentation build, configured in ``.github/workflows/ci.yml``. It runs on every push
to ``master`` and on every pull request, and has two jobs which run in sequence:

Linting
    Runs ``ruff check``, ``ruff format --check`` and the ``ty`` type checker over the
    repository. See :ref:`code style and linting`.


Docs
    Builds the Sphinx documentation and uploads the rendered HTML as a build artifact.
    ``docs/Makefile`` defaults ``SPHINXOPTS`` to ``-W --keep-going``, so any warning
    fails the build.

Test workflows
    The tests currently run on SDCC CI nodes through Bamboo, which call the
    ``ci/run_test_workflows.sh`` shell script. These tests need the SDCC module environment 
    and the IMAS data and run a number of specific actor and workflow tests.
