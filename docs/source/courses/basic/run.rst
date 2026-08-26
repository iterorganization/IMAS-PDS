.. _`basic/run`:

Running existing PDS simulations
================================

In this section we show how to run pre existing workflows in this repo.
You can use the actor specific test workflows or the ITER scenario workflows.


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
    Some of the workflows are automatically run on the compute nodes.

    .. code-block:: console

        srun --pty bash


First we look at some ITER scenarios:
These workflows are made to demonstrate and validate the performance of the PDS actors.
The different scenarios can be found in the ``workflows`` directory.
The workflow can be run by running the ``run_workflow.sh`` shell script.

.. warning::

   ``run_workflow.sh`` and the per-scenario ``scenarios/<shot>/tmp/`` output layout are the
   legacy invocation, kept for the workflows that have not been migrated yet. The exercises
   below use the migrated form instead: a **case** file in ``cases/``, run through
   ``bin/run_case.sbatch``. See :doc:`../../usage` for what a case is.

The shell script:

- preprocesses the DINA input data so that it is compatible with the used MUSCLE3 actors.
- rewrites the path placeholders in the template yMMSL configuration files for the user.
- runs the prebuilt workflow using the muscle_manager.
- makes some default plots of the data saved in ``workflows/*my_workflow*/scenarios/*my_scenario*/tmp/*my_figure*.png``.

The shell script currently expects to be run from the repository base directory.

.. code-block:: console

    # run_workflow.sh requires the PDS module stack to already be loaded
    module use /work/projects/pds/modules/all  # or wherever build.sh installed it
    module load PDS
    # to enable tab completion of the workflows and scenarios
    source completion.sh
    # to run the premade workflow
    bash run_workflow.sh <my_workflow> <my_scenario>


Exercise 1
----------

Before running a full equilibrium+transport workflow, it is useful to first look at the
``prescribed_transport`` workflow. This is the simplest workflow available: a
minimal chain of ``source -> waveform_editor -> nice_inv -> sink``.
Transport is **not** solved here: the plasma shape, Ip(t)/B0 and profile
shape (``p'``, ``FF'``) are all fixed externally in ``waveforms.yaml``, and NICE-inverse solves
the free-boundary equilibrium independently for each time slice, with no time coupling and no
outer iteration. This makes it a quick way to check the equilibrium/coil side of the pipeline on
its own, before adding the extra complexity of a self-consistently coupled transport solver.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run the ``prescribed_transport`` workflow for scenario ``105092``.
        This uses the same DINA-derived boundary/target trace as the
        ``inverse_convergence`` workflow in the next exercise, but without a
        TORAX transport solve, so NICE only needs to reproduce the prescribed equilibrium shape
        and coil currents.

    .. md-tab-item:: Solution

        .. code-block:: console

            bash bin/run_case.sbatch 105092_prescribed

        Check if the results look as expected using the visualization tool. The solved
        equilibrium and coil currents are written to
        ``run/out/105092_prescribed/out_nice``.

        Since transport is not solved, there are no profile comparison plots here, unlike
        in the self-consistent transport workflow below.


Exercise 2
----------

Next we look at the self-consistent transport workflow, which couples the equilibrium
calculated by NICE to a transport solve using TORAX.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run the ``inverse_convergence`` workflow for scenario ``105092``.
        This is a simple scenario for an L-mode limiter plasma with low ECH power,
        a short ramp-up phase from t=0 to t=9,
        a flattop phase at ~ 3 MA from t=9 to t=147
        and ramp-down phase from t=147 to t=170.
        The workflow uses DINA output for the 105092 scenario as a target to give a desired plasma shape to NICE,
        which calculates the coil currents needed to get the best approximation of this shape. This shape,
        together with the core_profiles and core_sources IDS is then used to calculate the current, ion and electron transport using TORAX.

        .. note::
            This run might take a while and will only show feedback through the visualization actor
            after NICE has returned its first output.
            To run this scenario faster, you can lower ``N_TIMESLICES``, the amount of timeslices to be run in NICE,
            in ``workflows/*my_workflow*/scenarios/*my_scenario*/scenario_config.env``. For 7-11 timeslices the general behavior is still very recognisable.


    .. md-tab-item:: Solution

        .. code-block:: console

            bash bin/run_case.sbatch 105092_convergence

        Check if results look as expected using the visualization tool. The solved
        equilibrium and coil currents are written to
        ``run/out/105092_convergence/out_nice``, and the converged pulse to
        ``run/out/105092_convergence/out_torax``.

        .. image:: pds_coils_105092.png
        .. image:: pds_equilibrium_0D_105092.png
        .. image:: pds_equilibrium_1D_105092.png

You can also run some other workflows for different workflows and scenarios.

Bonus Exercise
--------------

Next we look at actor specific test workflows.
They are saved in the ``ymmsl_files`` directory.
Test workflows can be run to check if the individual actors are working as expected.
These workflows can be used as a template for your own workflows.
This exercise is mostly relevant for developers.

.. code-block:: console

    bash setup_files/setup_test_files.sh  # generate runnable .ymmsl files from the .template sources
    module use /work/projects/pds/modules/all  # or wherever build.sh installed it
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
