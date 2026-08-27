.. _`adding_workflows`:

Adding a workflow
=================

A workflow describes structure only: which components exist, how they are wired,
and which implementation runs each one. It carries no shot data and no absolute
paths. Everything shot-specific arrives when ``bin/pds-create-case`` builds a
case from it -- see :ref:`running_cases` for the user's side of that.

Anatomy of a workflow directory
-------------------------------

.. code-block:: text

  workflows/<name>/
    workflow.ymmsl        required -- structure: components, conduits, imports
    settings.ymmsl        required -- generic settings and resources
    README.md             required -- what it does and what it assumes
    config_*.xml          tool configs referenced by settings keys
    config_torax.py
    waveforms.yaml
    preprocess.sh         optional -- runs once, at case creation
    postprocess.sh        optional -- runs after the manager exits
    env.sh                optional -- run-wide environment

``workflow.ymmsl``
  Components, conduits and the ``imports:`` block naming each implementation. No
  paths, no shot numbers, no tuning values. If you find yourself writing a number
  here, it probably belongs in ``settings.ymmsl``.

``settings.ymmsl``
  The workflow's generic settings, plus ``resources:``. Shot-dependent paths are
  written against ``${SHOT}`` and resolved per case.

``README.md``
  Treat this as required. It is included directly into :ref:`workflows`, so it is
  what users read -- not a paraphrase that can drift.

``preprocess.sh``
  Runs **once**, during ``pds-create-case``, not on every run. Use it when a
  workflow needs an input dataset that cannot be pre-baked into ``pds-scenarios``
  -- ``workflows/metis_from_dina/preprocess.sh`` builds METIS's own IMAS layout
  from raw DINA data this way. It receives ``PDS_REPO``, ``SCENARIOS_REPO``,
  ``SHOT`` and ``CASE_DIR``, and must write under ``$CASE_DIR/preprocess/``.

  If it needs to hand a value back that only it can compute, write a
  ``preprocess_settings.ymmsl`` into the case; ``pds-run-case.sbatch`` stacks it
  in last. ``metis_psioffset``, derived from the run's own DINA equilibrium, is
  the existing example.

``postprocess.sh``
  Runs after ``muscle_manager`` exits, with ``PDS_REPO``, ``SCENARIOS_REPO``,
  ``SHOT``, ``CASE_DIR``, ``RUN_DIR`` and ``PYTHON`` set. Write output into
  ``$RUN_DIR``. Use ``"$PYTHON"``, not ``python`` -- it is the same interpreter
  the manager resolved to, and the module environment may not put that first on
  ``PATH``.

``env.sh``
  Sourced before the manager starts, for a run-wide variable that an *imported*
  implementation needs and cannot set itself. This exists because a ymmsl
  overlay replaces a same-named implementation wholesale rather than merging
  field by field, so you cannot add an ``env:`` entry to an implementation you
  imported from ``imas_muscle3``. ``workflows/metis_from_dina/env.sh`` sets
  ``IMAS_AL_DISABLE_VALIDATE`` for the generic source and sink components this
  way.

Templating
----------

``pds-create-case`` substitutes exactly four variables when it copies files into
a case:

``${PDS_REPO}`` ``${SCENARIOS_REPO}`` ``${SHOT}`` ``${CASE_DIR}``

That is the whole vocabulary. There is no placeholder scheme beyond it, and
nothing else is expanded.

Any setting key ending in ``.xml_path``, ``.python_config_module``, ``.config``
or ``.waveforms`` gets special treatment: the file it names is copied into
``<case>/config/``, its own placeholders resolved, and the setting repointed at
the copy. That is what makes a case a frozen snapshot -- editing a workflow
afterwards cannot change a case built earlier.

.. warning::

   Config localisation keys the destination on the file's basename, so two
   settings pointing at different files with the same name will collide in
   ``config/``. Give tool configs distinct names within a workflow.

Declaring implementations
-------------------------

Implementations come from three places:

.. code-block:: yaml

  imports:
  # generic actors, straight from the installed package
  - from imas_muscle3 import implementation source_component
  - from imas_muscle3 import implementation sink_component
  # the coupled codes, as EasyBuild modules
  - from lib.easybuild_programs import implementation nice_inv
  - from lib.easybuild_programs import implementation torax

``lib.*`` resolves because ``YMMSL_PATH`` includes ``$PDS_REPO/workflows`` --
set by the PDS module and again by ``bin/pds-run-case.sbatch``. If an import
fails with *Failed to find a file lib/easybuild_programs.ymmsl*, that variable is
what is missing.

Adding a new coupled code means adding a program to
``workflows/lib/easybuild_programs.ymmsl`` (and, if a from-source build should
also work, to ``local_programs.ymmsl``). See :ref:`writing_actors` for the actor
side.

Adding a shot
-------------

Try it first without an override -- if the workflow's generic settings already
cover the shot, nothing more is needed. ``prescribed_transport`` runs in CI with
no override at all.

When a shot does need its own values, add
``cases/overrides/<workflow>_<shot>.ymmsl`` with just those keys: a pulse window,
a calibrated transport config, a different waveform set. Keep it to numbers that
genuinely differ per shot. An override that starts restating the workflow is a
sign the workflow's own settings need adjusting instead.

Validating it
-------------

``ci/check_ymmsl.py`` resolves and flattens every case statically -- no data, no
MUSCLE3, no cluster -- and runs in CI:

.. code-block:: bash

  uv run python ci/check_ymmsl.py

It catches the failures that are otherwise silent at runtime: a settings key that
matches no instance (``get_setting`` walks prefixes and falls through, so the key
is simply never seen), a ``resources`` key that is not exactly
``<root>.<instance>`` (the component quietly gets one thread), and a model port
declared but not wired inside the model (``flatten()`` drops the caller's conduit
without complaint).

A workflow with no override is checked structurally against a placeholder shot,
so a new workflow is covered from the moment it exists.

Once it resolves, add it to the integration suite by putting a line in
``ci/run_test_workflows.sh``:

.. code-block:: bash

  run_case_clean <workflow> <shot>

Checklist
---------

- ``workflow.ymmsl`` has no absolute paths, shot numbers or tuning values.
- ``settings.ymmsl`` declares ``resources:`` for every component that should get
  more than one thread.
- ``README.md`` exists and describes assumptions, not just structure.
- ``uv run python ci/check_ymmsl.py`` passes.
- A ``run_case_clean`` line is in ``ci/run_test_workflows.sh``.
- The workflow appears in the tables in :ref:`workflows`.
