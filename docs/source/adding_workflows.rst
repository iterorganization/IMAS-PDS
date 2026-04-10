.. _`adding_workflows`:

Adding new workflows
====================

This section explains how to add new workflows to the PDS.
Note that this process will change in the future as more developments are being made.

General
-------

Runnable scenarios are found in the ``workflows`` directory in the PDS repository.
A runnable scenario for a given workflow is contained in a named directory like
``workflows/torax_nice_self_consistent_transport/scenarios/105092``.
It is executed by running the ``run_workflow.sh`` script with the workflow name as first argument
and the scenario as second argument like:

.. code-block:: bash

  # run test workflow of choice, in this case:
  # workflow: torax-nice_self_consistent_transport
  # scenario: 105084
  bash run_workflow.sh torax_nice_self_consistent_transport 105084

In the workflow directories are the default configuration and workflow files that are reused between scenarios.
If a scenario needs its own config or workflow files, they should be added to the scenario subdirectory.
Many of the scenarios use the same tools for data preprocessing or result analysis,
which can be found in a separate directory like ``torax_nice_utils``.
A schematic of the directory structure is shown below:

.. code-block:: text
  :caption: Example directory structure for rule sets

  └── workflows/
     └── <workflow_name>/
         ├── .workflow.ymmsl
         ├── preprocess_data.sh
         ├── create_runnable_files.sh
         ├── run_simulation.sh
         ├── postprocess_data.sh
         └── scenarios/
             └── <scenario_id>/
                 ├── scenario_config.env
                 ├── info.txt
                 └── .<custom_overrides>  # Optional

A scenario run consists of 4 steps, all of which should be integrated in the workflow:

- Data Preprocessing (preprocess_data.sh)
- File Prepping (create_runnable_files.sh)
- Running the Simulation (run_simulation.sh)
- Result Processing (postprocess_data.sh)

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
These files are appended with '.template' (i.e. ``workflow.ymmsl.template``)
and serve as the default configuration for the given workflow.
If a scenario has its own specific files that have priority over the default ones, 
those should be added to the scenario subdirectory.
Since the pds installation cannot always handle relative paths well, the files should have
placeholders for the paths to files, since those are user specific.
The template files should then be copied and rewritten to actually runnable files in the scenario subdirectories 
where the placeholders are filled in. For example:

.. code-block:: bash

  # part of the .workflow.ymmsl template file in the workflow directory
  settings:
    sink.sink_uri: "imas:hdf5?path=[BASEDIR_PLACEHOLDER]/workflows/torax_nice_self_consistent_transport/scenarios/[SHOT_NR_PLACEHOLDER]/tmp/data/[SHOT_NR_PLACEHOLDER]_out/" 

.. code-block:: bash

  # part of the resulting workflow.ymmsl runnable file in the scenario directory
  settings:
    sink.sink_uri: "imas:hdf5?path=/home/ITER/sanderm/gitrepos/pds/workflows/torax_nice_self_consistent_transport/scenarios/105092/tmp/data/105092_out/" 

Running the Simulation
----------------------

The workflow should be run using 

.. code-block:: bash

  muscle_manager --start-all "path/to/my/workflow.ymmsl" --run_dir "tmp/my_run_dir"

Result Processing
-----------------

After the simulation is done, the results should be processed and plots and analyses should be made.
The relevant quantities and plots depend on the workflow.
