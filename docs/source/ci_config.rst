.. _`ci configuration`:

CI configuration
================

PDS is tested in two places, and it is worth knowing which is which: the fast
checks run on GitHub, and everything that actually executes a simulation runs on
the ITER cluster.

GitHub Actions
--------------

Configured in ``.github/workflows/ci.yml``. Runs on every push to ``master`` and
on every pull request, as two jobs in sequence:

Linting
    ``ruff check``, ``ruff format --check`` and the ``ty`` type checker over the
    whole repository, plus ``ci/check_ymmsl.py``, which resolves and flattens
    every case statically. See :ref:`code style and linting`.

Docs
    Builds the Sphinx documentation and uploads the rendered HTML as a build
    artifact. ``docs/Makefile`` defaults ``SPHINXOPTS`` to ``-W --keep-going``,
    so any warning fails the build.

Neither job needs the module stack, IMAS data or a cluster -- which is exactly
why they can run on GitHub at all.

Integration tests
-----------------

These are **not** on GitHub. They need the module environment, MATLAB and real
IMAS data, so they run on SDCC CI nodes through Bamboo, which calls
``ci/run_test_workflows.sh``.

That script builds the module environment, then runs, in order:

- **Eight single-actor smoke tests** --  ``test_sink_source_actor``,
  ``test_accumulator_actor``, ``test_olc_actor``, ``test_waveform_editor``,
  ``test_torax_actor``, ``test_nice_actor``, ``test_metis_actor``,
  ``test_chease_actor``. These catch a broken actor environment in seconds,
  before any expensive run starts.
- **Five full cases**, created and run end to end: ``prescribed_transport
  105099``, ``inverse_convergence 105073``, ``evolutive_controller 105073``,
  ``metis_from_dina 105084`` and ``metis_nice_inverse_from_dina 105084``.

If a change touches ``workflows/``, ``bin/`` or the easyconfigs, this suite --
not GitHub CI -- is what will catch a regression. See :ref:`contributing` for
running it yourself.

Publishing
----------

The docs job uploads the built HTML as an artifact with a one-day retention, so
GitHub CI proves the documentation *builds* but does not publish it. Read the
Docs builds from ``.readthedocs.yml``, which invokes ``sphinx-build`` directly
rather than through ``docs/Makefile`` -- so the Makefile's ``-W`` does not apply
there, and ``fail_on_warning`` in that file is what keeps the two in agreement.
