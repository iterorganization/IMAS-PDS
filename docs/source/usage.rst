.. _`usage`:

Using the IMAS PDS
==================

Setting up actors
-----------------
A setup script is provided with an installation of the necessary repositories.
Make sure you have access rights to all the relevant codes.

.. code-block:: bash

  # install repos
  . pds_setup.sh


Test workflows
--------------

Test workflows can be run to check if everything is working as expected.
These workflows can be used as a template for your own workflows.

.. code-block:: bash

  # move to run folder where all the generated code is ignored by git
  cd run/
  # prepare base environment and loaded modules
  source imas_base_env
  # run test workflow of choice
  muscle_manager --start-all ../ymmsl_files/test_sink_source_actor.ymmsl

Example cases
-------------
Example cases for actual ITER scenarios can be run for validation of the PDS workflows.
The shell script currently assumes it is being run from the specific scenario config directory itself.

.. code-block:: bash

  # prepare base environment and loaded modules
  cd scenario_configs/105084
  # run test workflow of choice
  bash automate_runs.sh
