.. _`training/understanding`:

Understanding the PDS
=====================

The PDS does not simulate anything by itself. It wires existing physics codes together as 
MUSCLE3 actors, and describes that wiring in yMMSL files. 
Before running anything it helps to know which file describes what, because the PDS
deliberately keeps three things apart.

Workflows, scenarios and cases
------------------------------

Workflow - The workflow describes *how* something is simulated. Which actors take part 
and how they are connected, in ``workflows/<name>/workflow.ymmsl``. it is structure only, 
so the same workflow can be used for multiple different scenarios.

Scenario - The scenario describes *what* is simulated. This includes the input data and the 
designed targets for one pulse, in the separate ``pds-scenarios`` repository, one directory 
per shot. This repository is available on SDCC on ``/work/projects/pds/pds-scenarios``.
You will see that path written as ``${SCENARIOS_REPO}`` in the settings files -- the PDS
scripts fill it in for you, and you only ever set it yourself if you keep your own copy of
the scenarios somewhere else.
The scenarios knows nothing about which codes will consume it, so the same scenario can be run 
through several workflows.

Case - The combination of a workflow and a scenario. You build one with
``bin/pds-create-case <workflow> <shot>``, which materializes ``cases/<workflow>_<shot>/``: a
frozen snapshot that takes the workflow's structure, fills in this scenario's paths, applies
any per-shot override from ``cases/overrides/``, and copies in every config file those
settings point at. ``bin/pds-run-case.sbatch`` is what you hand that folder to. You will
directly interface with case folders in the next chapter.

Run - The run is what you get when you execute a case: a run directory,
``cases/runs/<workflow>_<shot>/``, with the logs, the simulation output, and a record of the
exact configuration that was used.

Keeping them apart is what makes the pieces reusable.

Finding what is available
-------------------------

.. TODO: these pointed at the case gallery (docs/source/cases/), which is not part of
   this branch; restore those links if the gallery lands.

The workflows the cases are built on are documented in :ref:`available_workflows`, and
``cases/overrides/`` shows which shots each of them has a case for. Building and running a
case is covered in :ref:`usage`.

For a description of the physics each workflow covers, see :ref:`available_workflows`.

For the scenarios and your own runs:

.. code-block:: bash

    ls /work/projects/pds/pds-scenarios     # the scenarios, one directory per shot
    m3dash ls                               # the runs you have already produced

Reading a case
--------------

A case folder is short and worth reading before you run it. ``workflow.ymmsl`` holds the
structure -- which components exist and how they are wired -- and
``workflow_settings.ymmsl`` holds everything specific to this run:

.. code-block:: yaml

    resources:
      prescribed_transport.equilibrium.nice: {threads: 2}

    settings:
      waveform_editor.waveforms: /path/to/pds/cases/prescribed_transport_105092/config/waveforms_no_transport.yaml
      source.source_uri: "imas:hdf5?path=/work/projects/pds/pds-scenarios/105092/data/in"
      equilibrium.nice.xml_path: /path/to/pds/cases/prescribed_transport_105092/config/config_nice_inverse.xml
      sink.sink_uri: "imas:hdf5?path=../../../out_nice"

``resources`` says how many threads each component gets, and ``settings`` everything else:
which scenario data to read, which configuration each solver uses, and where the output goes.
Note that the config paths point into the case's own ``config/`` -- ``pds-create-case``
copied them there and rewrote the settings, so the case does not depend on
``workflows/`` or ``pds-scenarios`` still looking the same later. If the case has a
``scenario_settings.ymmsl`` as well, it is stacked after this file and wins on any key it
repeats. Reading these blocks tells you most of what that run will do.


Exercise 1: find out what is available
--------------------------------------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Using :ref:`available_workflows` and ``cases/overrides/``, find out which workflows have cases, which
        shots each of them covers, and which shots can be run both with prescribed transport
        and with a converged transport solve.


Exercise 2: find out what a case will do
----------------------------------------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Without running anything, build the case with
        ``bin/pds-create-case inverse_convergence 105092`` and work out from the folder which
        workflow it uses, which scenario data it reads, and where its output will be written.

    .. md-tab-item:: Solution

        Start from ``inverse_convergence`` in :ref:`available_workflows`, which describes
        the coupling and what the case produces, then read the case folder itself.

        ``workflow.ymmsl`` names the components and how they are wired, the
        ``source.source_uri`` and ``waveform_editor.waveforms`` settings name the scenario
        data, and the ``sink_nice.sink_uri`` and ``sink_torax.sink_uri`` settings name the
        output entries, written into ``cases/runs/inverse_convergence_105092/``.


Looking at the input before you run
-----------------------------------

A case tells you *which* data it reads, but not what is in it. Since a full run can take a
while, it pays to look at the input first -- an empty or unexpected IDS is much easier to
recognise now than halfway through a simulation.

Every scenario keeps its data in two DBEntries: ``data/in`` with the pulse itself, and
``data/in_md`` with the machine description, the parts of the machine that do 
not change during a pulse.

Exercise 3: look at a scenario before running it
------------------------------------------------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Take a look at the ``105092`` scenario, which lives in
        ``/work/projects/pds/pds-scenarios/105092/``.

        ``IDStools`` is a separate module with a set of ready-made IMAS plotting scripts. In
        this case, you can use the
        `plotscenario <https://imas-idstools.readthedocs.io/en/latest/plotscenario.html>`_
        script, which shows the equilibrium together with the kinetic profiles.
        Load it with ``module load IDStools`` and visualize the scenario.

        Without a time it plots the middle of the pulse. Try roughly the ramp-up, the flattop
        and the ramp-down. Over which time range does the pulse run, and does the plasma keep
        the same shape throughout?

    .. md-tab-item:: Solution

        .. code-block:: bash

            module load IDStools

            plotscenario --uri "imas:hdf5?path=/work/projects/pds/pds-scenarios/105092/data/in" -t 80

        Compare ``-t 5``, ``-t 80`` and ``-t 160``.
