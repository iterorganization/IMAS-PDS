.. _`ci configuration`:

CI configuration
================

PDS uses `ITER Bamboo <https://ci.iter.org/>`_ for CI. This page provides an overview
of the CI Plan and deployment projects.

CI Plan
-------

The `PDS CI plan <https://ci.iter.org/browse/IC-PYM>`_ consists of 3 types of jobs:

Linting
    Run ``ruff`` (format check, lint and import sorting) and ``ty`` on the PDS code
    base. See :ref:`code style and linting`.

    The CI script executed in this job is ``ci/linting.sh``.

Build docs
    This job builds the Sphinx documentation.

    The CI script executed in this job is ``ci/build_docs.sh``.

Test workflows
    This runs the actor-specific test workflows and the example ITER scenario workflows
    end to end (see :ref:`available_workflows`).

    The CI script executed in this job is ``ci/run_test_workflows.sh``.
