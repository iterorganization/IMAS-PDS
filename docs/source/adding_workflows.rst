.. _`adding_workflows`:

Adding new workflows
====================

Here we provide an explanation for how add new workflows to the PDS.
Note that this process will change in the future as more developments are being made.

General
-------

Runnable scenarios are found in the ``scenario_configs`` directory in the PDS repository.
A runnable scenario is contained in a named directory like ``105092_torax_nice``
and is executed by moving to the directory and running the ``automate_runs.sh``
script like:

.. code-block:: bash

  # prepare base environment and loaded modules
  cd scenario_configs/105092_torax_nice
  # run test workflow of choice
  bash automate_runs.sh

Many of the scenarios run the same structure, which can be found in a separate directory
like ``torax_nice_utils``.
In the utils directories are the default configuration and workflow files that are reused between scenarios.
If a scenario needs its own config or workflow files, they should be added to the scenario subdirectory.

A scenario run consists of 4 steps, all of which should be integrated in the workflow:

- data preprocessing
- file prepping
- running
- plotting

Data Preprocessing
------------------

The input data for the simulation needs to be complete for the actors that will be using it.
Check the documentation of the actors to see which IDSs are needed and which IDS fields are mandatory.
Make sure that the IMAS DD version is compatible with the used actors.
If the used input data is already compatible, this step can be skipped.

File Prepping
-------------

A workflow needs to have configuration files for all the used actors,
as well as a ymmsl workflow file for MUSCLE3.
These files are prepended with a dot (i.e. ``.my_workflow.ymmsl``)
and should have placeholders for the paths to files, since those are user specific.
If a scenario has its own specific files that have priority over the default ones, 
those should be added to the scenario subdirectory.
The files should then be copied and rewritten to actually runnable files in the scenario subdirectories 
where the placeholders are filled in.

Running the Workflow
--------------------

The workflow should be run using 

.. code-block:: bash

  muscle_manager --start-all "my_workflow.ymmsl" --run_dir "tmp/my_run_dir"

Result Processing
-----------------

The results from the simulation should be processed, plots and analyses should be made.
The relevant quantities and plots depend on the workflow.
