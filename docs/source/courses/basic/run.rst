.. _`basic/run`:

Running existing PDS simulations
================================

In this section we show how to run pre existing workflows in this repo.
You can use the actor specific test workflows or the iter scenario workflows.

.. code-block:: console

    cd run/
    source imas_base_env

We start with the actor specific test workflows.
They are saved in ymmsl_files directory.
Test workflows can be run to check if everything is working as expected.
These workflows can be used as a template for your own workflows.

.. code-block:: console

    muscle_manager --start-all path/to/my/workflow.ymmsl

.. note::

    Use the visualization tool from IMAS-MUSCLE3 to look at the data.

Exercise 1
----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run some of the actor specific test workflows.

    .. md-tab-item:: Solution

        .. code-block:: console

            muscle_manager --start-all ../ymmsl_files/test_sink_source_actor.ymmsl

        Check if results look as expected using the visualization tool.


Next we look at some ITER scenarios:
These workflows are made to demonstrate and validate the performance of the PDS actors.
The shell script:

- rewrites the paths in the template configuration files for the user.
- preprocesses the DINA input data so that it is compatible with the used MUSCLE3 actors.
- runs the prebuilt workflow using the muscle_manager.

The shell script currently expects to be run from the specific scenario directory itself.

.. code-block:: console

    cd path/to/my/scenario_config
    bash automate_runs.sh

Exercise 2
----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run scenario workflow.

    .. md-tab-item:: Solution

        .. code-block:: console

            cd ../scenario_configs/105092_torax_nice
            bash automate_runs.sh

        Check if results look as expected using the visualization tool.
            