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
The scenarios knows nothing about which codes will consume it, so the same scenario can be run 
through several workflows.

Case - The combination of a workflow and a scenario, these are available in ``cases/<shot>_<workflow>.ymmsl``. 
It imports a workflow, points at a scenario, and adds the settings for this particular combination. A case
is the single file you hand to ``muscle_manager``. You will directly interface with the case
files in the next chapter.

Run - The run is what you get when you execute a case: a run directory with the logs, the simulation
output, and a record of the exact configuration that was used.

Keeping them apart is what makes the pieces reusable.

Finding what is available
-------------------------

.. TODO: repointed from the case gallery when this branch was rebased onto
   feature/workflow-modularisation; revisit with the case-system doc update.

The workflows the cases are built on are documented in :ref:`available_workflows`, and
``cases/overrides/`` shows which shots each of them has a case for. Building and running a
case is covered in :ref:`usage`.

For a description of the physics each workflow covers, see :ref:`available_workflows`.

The scenarios and your own runs are not in the gallery, so for those:

.. code-block:: bash

    ls $SCENARIOS_REPO              # the scenarios, one directory per shot
    m3dash ls                       # the runs you have already produced

Reading a case
--------------

A case is short and worth reading before you run it. It has three blocks:

.. code-block:: yaml

    imports:
    - from prescribed_transport.workflow import implementation prescribed_transport

    resources:
      prescribed_transport.workflow.prescribed_transport.solve.nice: {threads: 2}

    settings:
      waveform_editor.waveforms: $SCENARIOS_REPO/105092/waveforms_no_transport.yaml
      source.source_uri: "imas:hdf5?path=$SCENARIOS_REPO/105092/data/in"
      solve.nice.xml_path: $PDS_REPO/workflows/lib/config_nice_inverse.xml
      sink.sink_uri: "imas:hdf5?path=../../../out_nice"

``imports`` says which workflow is being run, ``resources`` how many threads each component
gets, and ``settings`` everything else: which scenario data to read, which configuration each
solver uses, and where the output goes. Reading the ``settings`` block of a case tells you
most of what that run will do.


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

        Without running anything, work out for ``cases/105092_convergence.ymmsl`` which
        workflow it uses, which scenario data it reads, and where its output will be written.

    .. md-tab-item:: Solution

        Start from ``inverse_convergence`` in :ref:`available_workflows`, which describes
        the coupling and what the case produces, take a look at the relevant yMMSL file.


        The ``imports`` block names the workflow, the ``source.source_uri`` and
        ``waveform_editor.waveforms`` settings name the scenario data, and the
        ``sink_nice.sink_uri`` and ``sink_torax.sink_uri`` settings name the output entries,
        written into the run directory.

.. todo::

    - Say explicitly what a **run** is as a fourth concept next to workflow/scenario/case, and
      where its output lives
    - Add an exercise on previsualizing scenario input data before running it
