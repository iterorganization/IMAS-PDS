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
    fails the build both here and locally. This job runs only once linting has passed.

Test workflows
    
    # TODO: Still to be migrated to GitHub Actions
