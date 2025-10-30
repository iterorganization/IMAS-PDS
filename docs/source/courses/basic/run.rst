.. _`basic/run`:

Running existing PDS simulations
================================

In this section we show how to run pre existing workflows in this repo.
You can use the actor specific test workflows or the iter scenario workflows.
The `run` subdirectory can be used as a sandbox for installing and running many different codes.

.. code-block:: console

    cd run/
    source imas_base_env

Exercise 1
----------

First we look at some ITER scenarios:
These workflows are made to demonstrate and validate the performance of the PDS actors.
The different scenarios can be found in the ``scenario_configs`` directory.
The workflow can be run by running the ``automate_runs.sh`` shell script.
The shell script:

- rewrites the path placeholders in the template yMMSL configuration files for the user.
- preprocesses the DINA input data so that it is compatible with the used MUSCLE3 actors.
- runs the prebuilt workflow using the muscle_manager.
- makes some default plots of the data saved in ``scenario_configs/*my_scenario*/tmp/*my_figure*.png``.

The shell script currently expects to be run from the specific scenario directory itself.

.. code-block:: console

    cd path/to/my/scenario_config
    bash automate_runs.sh

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run the ``105092_torax_nice`` scenario workflow.
        This is a simple scenario for an L-mode limiter plasma with low ECH power,
        a short ramp-up phase from t=0 to t=9,
        a flattop phase at ~ 3 MA from t=9 to t=147
        and ramp-down phase from t=147 to t=170.
        The workflow uses DINA output for the 105092 scenario to give a desired plasma shape to NICE,
        which calculates the coil currents needed to get the best approximation of this shape. This shape, 
        together with the core_profiles and core_sources IDS is then used to calculate the current transport using TORAX.

        .. note::
            This run might take a while and will only show feedback through the visualization actor
            after NICE has returned its first output.
            To run this scenario faster, you can lower ``N_TIMESLICES``, the amount of timeslices to be run in NICE,
            in ``automate_runs.sh``. For 7-11 timeslices the general behavior is still very recognisable.


    .. md-tab-item:: Solution

        .. code-block:: console

            cd ../scenario_configs/105092_torax_nice
            bash automate_runs.sh

        Check if results look as expected using the visualization tool.
        You can also check the default plots: 
        
        ``scenario_configs/105092_torax_nice/tmp/pds_coils_105092.png``
        ``scenario_configs/105092_torax_nice/tmp/pds_equilibrium_0D_105092.png``
        ``scenario_configs/105092_torax_nice/tmp/pds_equilibrium_1D_105092.png``

        .. image:: pds_coils_105092.png
        .. image:: pds_equilibrium_0D_105092.png
        .. image:: pds_equilibrium_1D_105092.png


Exercise 2
----------

Next we look at actor specific test workflows.
They are saved in the ``ymmsl_files`` directory.
Test workflows can be run to check if everything is working as expected.
These workflows can be used as a template for your own workflows.
This exercise is mostly relevant for developers.

.. code-block:: console

    muscle_manager --start-all path/to/my/workflow.ymmsl

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run some of the actor specific test workflows.
        The main usecase of these test workflows is to make sure the actors can run without crashing.

        ``ymmsl_files/test_sink_source_actor.ymmsl`` tests if data is properly loaded from a given DBEntry and saved in the next.

        ``ymmsl_files/test_waveform_editor.ymmsl`` tests if the waveform editor is sending the defined waveforms to the next actor.

        ``ymmsl_files/test_nice_actor.ymmsl`` tests if the different nice actors are properly calculating the equilibrium and coil
        currents based on the given desired plasma shape.


    .. md-tab-item:: Solution

        .. code-block:: console

            muscle_manager --start-all ../ymmsl_files/test_sink_source_actor.ymmsl

        `test_sink_source_actor.ymmsl` simply loads data from 1 Data Entry and saves it in a new one.
        The input and output are expected to be the same.

        `test_waveform_editor.ymmsl` takes the timestamp of an incoming message and sets a waveform for 
        the ec_launchers/beam(1)/power_launched/data to ramp up to 50 kW over 10 seconds, remain constant for 30 seconds,
        and ramp down to 0 over 10 seconds again.

        `test_sink_source_actor.ymmsl` sends the desired plasma shape from a given IDS to NICE inverse mode to calculate the coil currents
        needed to realize this plasma shape. The equilibrium output is expected to be close to the input.

        Optionally, you can check if the results look as expected using the standard IMAS exploration tools.
