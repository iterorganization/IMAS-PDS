.. _`usage`:

Using the IMAS PDS
==================

Setting up actors
-----------------
Each actor (IMAS-MUSCLE3, NICE, METIS, TORAX-MUSCLE3, Waveform-Editor, PCS, ...) is built once
into a shared ``PDS-<Name>`` module by its own ``build_*.sh`` script in
``setup_files/custom_modules/``. Loading the PDS meta-module (``module load PDS``) sets up
IMAS-Python and PDS-IMAS-MUSCLE3; each workflow actor then loads its own ``PDS-<Name>``
module itself when MUSCLE3 spawns it. Either way, there is nothing to install per-checkout.

.. code-block:: bash

  module use /home/ITER/blokhus/public/modules  # or wherever PDS.lua was deployed
  module load PDS


Test workflows
--------------

Test workflows can be run to check if everything is working as expected.
These workflows can be used as a template for your own workflows.

.. code-block:: bash

  # generate runnable .ymmsl files from the .template sources
  bash setup_files/setup_test_files.sh
  module use /home/ITER/blokhus/public/modules
  module load PDS
  # run test workflow of choice
  muscle_manager --start-all ymmsl_files/test_sink_source_actor.ymmsl

Example cases
-------------
Example cases for actual ITER scenarios can be run for validation of the PDS workflows.
The shell script currently assumes it is being run from the base directory of the PDS repository.
The different workflows are contained in the ``workflows`` directory.
The different scenarios for these workflows are contained in the ``workflows/<my_workflow>/scenarios`` directory.
To run a preconfigured workflow, run the ``run_workflow.sh`` file with the desired workflow and scenario as arguments.
Note that this way of running the PDS workflows will change in the future as more developments are being made.

.. code-block:: bash

  # run_workflow.sh requires the PDS module stack to already be loaded
  module use /home/ITER/blokhus/public/modules
  module load PDS
  # to enable tab completion of the workflows and scenarios
  source completion.sh
  # run test workflow of choice, in this case:
  # workflow: inverse_convergence
  # scenario: 105084
  bash run_workflow.sh inverse_convergence 105084
