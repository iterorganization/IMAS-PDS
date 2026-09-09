.. _`running_cases`:

Running a case
==============

Workflows, scenarios and cases
------------------------------

A run pairs two things:

**Workflow**
  *How* something is simulated: which codes are coupled, in what order, over
  which ports. Workflows live in ``workflows/`` and contain no shot data.

**Scenario**
  *What* is simulated: the machine description, the input equilibrium, the
  waveforms for one shot. Scenarios live in the separate ``pds-scenarios``
  repository, keyed by shot number.

**Case**
  The pairing of the two, materialised as a directory -- under ``cases/`` unless you say
  otherwise. This is what you actually run, and its runs land inside it.

You do not write a case by hand: ``bin/pds-create-case`` builds one and
``bin/pds-run-case.sbatch`` submits it.

Creating a case
---------------

.. code-block:: bash

  bin/pds-create-case <workflow> <shot> [case-dir]

  bin/pds-create-case inverse_convergence 105073

That writes ``cases/inverse_convergence_105073``. A third argument puts the case wherever
you want it instead, and ``PDS_CASES_DIR`` moves the default for every case you build:

.. code-block:: bash

  bin/pds-create-case inverse_convergence 105073 /scratch/$USER/my-case

  export PDS_CASES_DIR=/scratch/$USER/cases     # -> /scratch/$USER/cases/<workflow>_<shot>

``source completion.sh`` gives tab completion over the available workflows and the shots
in your ``$SCENARIOS_REPO``. :ref:`workflows` lists what is available.

A shot that is neither in your ``$SCENARIOS_REPO`` nor covered by a file in
``cases/overrides/`` is refused here, with the shots that are available -- a typo in a
shot number costs you an error message rather than a case whose every input path points
at nothing.

What is in a case directory
---------------------------

A case is a **frozen snapshot**, not a set of references: its own copy of every file it
needs, with all variables already substituted. Editing a workflow afterwards does not
change a case created earlier, and re-running an old case reproduces what it did the
first time.

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - File
     - Contents
   * - ``workflow.ymmsl``
     - The workflow's structure: components, conduits, implementations.
   * - ``workflow_settings.ymmsl``
     - The workflow's generic settings.
   * - ``scenario_settings.ymmsl``
     - Per-shot overrides, if ``cases/overrides/<workflow>_<shot>.ymmsl`` exists.
   * - ``preprocess_settings.ymmsl``
     - Values only ``preprocess.sh`` could compute, if it wrote any.
   * - ``config/``
     - Local copies of every NICE XML, TORAX config and waveform file the
       settings point at.
   * - ``preprocess/``
     - Output of the workflow's ``preprocess.sh``, which runs once, here.
   * - ``case.env``
     - The workflow name and shot, for ``postprocess.sh``.
   * - ``env.sh``, ``postprocess.sh``
     - Copied from the workflow, if it has them.

Submitting the run
------------------

.. code-block:: bash

  sbatch bin/pds-run-case.sbatch cases/inverse_convergence_105073

The job defaults to one node, 16 CPUs and two hours. Override on the ``sbatch`` line:

.. code-block:: bash

  sbatch --time=00:20:00 --cpus-per-task=8 \
      bin/pds-run-case.sbatch cases/prescribed_transport_105084

The script stacks the case's ymmsl files -- ``workflow.ymmsl``,
``workflow_settings.ymmsl``, ``scenario_settings.ymmsl``,
``preprocess_settings.ymmsl``, in that order -- and hands them to ``muscle_manager``,
loading the module stack itself if you have not.

``bin/pds-run-case`` checks the case before it submits anything: a path that does not
exist, or one that is not a case folder (no ``case.env`` -- a workflow directory, say),
is refused rather than queued and left to fail once the job starts.

Changing one setting for one run
--------------------------------

Put it in its own ymmsl file and stack it after the case. The last value given
for a key wins:

.. code-block:: bash

  sbatch bin/pds-run-case.sbatch cases/inverse_convergence_105073 ./cold-start.ymmsl

The case is untouched, so the change applies to that run only. For something a shot
always needs, use ``cases/overrides/`` instead.

Per-shot overrides
------------------

``cases/overrides/<workflow>_<shot>.ymmsl`` holds what one shot needs beyond the
workflow's generic settings -- a pulse window, a calibrated transport config, a
different waveform set. ``pds-create-case`` stacks it in automatically if it exists.

Keep them small: numbers that genuinely differ per shot, not a second copy of the
workflow.

Where the output goes
---------------------

Each run lands in ``<case-dir>/runs/<timestamp>/``, and ``<case-dir>/runs/latest``
symlinks to the most recent one -- so a case carries its own history, and everything one
case produced can be copied or deleted as a unit.

.. note::

   Runs accumulate: nothing prunes them, and rebuilding the case with
   ``pds-create-case`` keeps them. Delete the ones you no longer need yourself.

It also receives all the ymmsl files exactly as passed. 
When a run does something unexpected, read ``configuration.ymmsl`` as it shows the 
values at the end of the stack.

Sink outputs land directly in the run directory, ``<run_dir>/<name>``. Relative
IMAS URIs resolve against the instance's own work directory
(``<run_dir>/instances/<sink>/workdir``), which is why the cases write to
``../../../<name>`` to climb back out to the run directory.

Settings keys and resources keys
--------------------------------

The two use different matching rules. Settings are matched by walking instance
prefixes, so the short instance name is enough
(``equilibrium.nice.xml_path``). Resources are looked up by exact match, and the
key must be ``<root model>.<instance>`` in full
(``prescribed_transport.equilibrium.nice``).

A resources key that matches nothing is **not** an error: that component silently
gets one thread, and the run is simply slow. ``ci/check_ymmsl.py`` rejects both
mistakes, and runs in CI.

Running an actor on its own
---------------------------

Each actor has a smoke test under ``ymmsl_files/``, for when you suspect one tool
rather than the coupling. They need no scenario data:

.. code-block:: bash

  bash setup_files/setup_test_files.sh
  muscle_manager --start-all ymmsl_files/test_nice_actor.ymmsl

Available tests: ``test_sink_source_actor``, ``test_accumulator_actor``,
``test_olc_actor``, ``test_waveform_editor``, ``test_torax_actor``,
``test_nice_actor``, ``test_metis_actor``, ``test_chease_actor``. CI runs all
eight before it runs any full case.
