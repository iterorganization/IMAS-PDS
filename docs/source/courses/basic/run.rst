.. _`basic/run`:

Running existing PDS simulations
================================

In this section we show how to run pre existing workflows in this repo.
You can use the actor specific test workflows or the iter scenario workflows.


.. note::

    You can previsualize a scenario before running it to see which time slices will be most relevant.
    Make sure to point to where the input for the simulation is located.
    For the PDS scenarios, these can be found in the ``workflows/*my_workflow*/scenarios/*my_scenario*/scenario_config.env`` file.
    For more information on the Scenario Database, see the `documentation <https://confluence.iter.org/spaces/IMP/pages/151422626/Scenario+Database>`_.

    .. code-block:: console

        module load IMAS
        plotscenario --uri "imas:hdf5?path=/work/imas/shared/imasdb/ITER/3/105084/1"


.. note::

    To make sure you are not overloading the login nodes on SDCC, it is best to run the PDS simulations on compute nodes whenever possible.
    The easiest way to do this is to open a bash terminal on a compute node and work interactively from there.
    For more information on using compute nodes, see the `confluence page <https://confluence.iter.org/spaces/IMP/pages/316083236/How+to+work+interactively+on+a+batch+node+of+the+ITER+cluster>`_.
    Do keep in mind that certain graphical features like the IMAS-MUSCLE3 visualization actor are no longer immediately available from a compute node.

    .. code-block:: console

        srun --pty bash


Exercise 1
----------

First we look at some ITER scenarios:
These workflows are made to demonstrate and validate the performance of the PDS actors.
The different scenarios can be found in the ``workflows`` directory.
The workflow can be run by running the ``run_workflow.sh`` shell script.
The shell script:

- preprocesses the DINA input data so that it is compatible with the used MUSCLE3 actors.
- rewrites the path placeholders in the template yMMSL configuration files for the user.
- runs the prebuilt workflow using the muscle_manager.
- makes some default plots of the data saved in ``workflows/*my_workflow*/scenarios/*my_scenario*/tmp/*my_figure*.png``.

The shell script currently expects to be run from the repository base directory.

.. code-block:: console

    # run_workflow.sh requires the PDS module stack to already be loaded
    module use /home/ITER/blokhus/public/modules/all  # or wherever build.sh installed it
    module load PDS
    # to enable tab completion of the workflows and scenarios
    source completion.sh
    # to run the premade workflow
    bash run_workflow.sh <my_workflow> <my_scenario>

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run the ``inverse_convergence`` workflow for scenario ``105092``.
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
            in ``workflows/*my_workflow*/scenarios/*my_scenario*/scenario_config.env``. For 7-11 timeslices the general behavior is still very recognisable.


    .. md-tab-item:: Solution

        .. code-block:: console

            bash run_workflow.sh inverse_convergence 105092

        Check if results look as expected using the visualization tool.
        You can also check the default plots: 
        
        ``workflows/inverse_convergence/scenarios/105092/tmp/pds_coils_105092.png``
        ``workflows/inverse_convergence/scenarios/105092/tmp/pds_equilibrium_0D_105092.png``
        ``workflows/inverse_convergence/scenarios/105092/tmp/pds_equilibrium_1D_105092.png``

        .. image:: pds_coils_105092.png
        .. image:: pds_equilibrium_0D_105092.png
        .. image:: pds_equilibrium_1D_105092.png

You can also run some other workflows for different workflows and scenarios.

Exercise 2
----------

Next we look at actor specific test workflows.
They are saved in the ``ymmsl_files`` directory.
Test workflows can be run to check if everything is working as expected.
These workflows can be used as a template for your own workflows.
This exercise is mostly relevant for developers.

.. code-block:: console

    bash setup_files/setup_test_files.sh  # generate runnable .ymmsl files from the .template sources
    module use /home/ITER/blokhus/public/modules/all  # or wherever build.sh installed it
    module load PDS
    muscle_manager --start-all path/to/my/workflow.ymmsl

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run some of the actor specific test workflows.
        The main use case of these test workflows is to make sure the actors can run without crashing.

        ``ymmsl_files/test_sink_source_actor.ymmsl`` tests if data is properly loaded from a given DBEntry and saved in the next.

        ``ymmsl_files/test_waveform_editor.ymmsl`` tests if the waveform editor is sending the defined waveforms to the next actor.

        ``ymmsl_files/test_nice_actor.ymmsl`` tests if the different nice actors are properly calculating the equilibrium and coil
        currents based on the given desired plasma shape.


    .. md-tab-item:: Solution

        .. code-block:: console

            muscle_manager --start-all ymmsl_files/test_sink_source_actor.ymmsl

        ``test_sink_source_actor.ymmsl`` simply loads data from 1 Data Entry and saves it in a new one.
        The input and output are expected to be the same.

        ``test_waveform_editor.ymmsl`` takes the timestamp of an incoming message and sets a waveform for 
        the ec_launchers/beam(1)/power_launched/data to ramp up to 50 kW over 10 seconds, remain constant for 30 seconds,
        and ramp down to 0 over 10 seconds again.

        ``test_nice_actor.ymmsl`` sends the desired plasma shape from a given IDS to NICE inverse mode to calculate the coil currents
        needed to realize this plasma shape. The equilibrium output is expected to be close to the input.

        Optionally, you can check if the results look as expected using the standard IMAS exploration tools.
