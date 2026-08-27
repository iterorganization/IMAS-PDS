.. _`training/run_complex`:

Running existing workflows
==========================

.. todo:: run on compute node

.. todo:: integrate case docs

In this section we show how to run simulations in the PDS repository. As in the
previous sections, you will need to have a terminal with an active PDS environment.

.. code-block:: bash

    # Open the directory in which you cloned the PDS
    cd <your PDS install>
    # Load the PDS module
    module use /work/projects/pds/modules/all
    module load PDS


Exercise 1
----------

Before running a full equilibrium+transport workflow, it is useful to first look at the
``prescribed_transport`` workflow. This is the simplest workflow available: a
minimal chain of ``source -> waveform_editor -> solve -> sink``.
Transport is **not** solved here: the plasma shape, Ip(t)/B0 and profile
shape (``p'``, ``FF'``) are all fixed externally in the scenario's waveform configuration, and
NICE-inverse solves the free-boundary equilibrium independently for each time slice, with no
time coupling and no outer iteration. This makes it a quick way to check the equilibrium/coil
side of the pipeline on its own, before adding the extra complexity of a self-consistently
coupled transport solver.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run the ``prescribed_transport`` workflow for scenario ``105092``.
        This is a simple scenario for an L-mode limiter plasma with low ECH power,
        a short ramp-up phase from t=0 to t=9,
        a flattop phase at ~ 3 MA from t=9 to t=147
        and a ramp-down phase from t=147 to t=170.
        This uses the same DINA-derived boundary/target trace as the
        ``inverse_convergence`` workflow in the next exercise, but without a
        TORAX transport solve, so NICE only needs to reproduce the prescribed equilibrium shape
        and coil currents.

        .. tip:: There is an existing case file which you can run

    .. md-tab-item:: Solution

        .. code-block:: bash

            muscle_manager --start-all $PDS_REPO/cases/105092_prescribed.ymmsl

        Check if the results look as expected using the recorder actor plots in muscle3-dashboard.
        The solved equilibrium and coil currents are written to ``out_nice`` in the run
        directory, so you can also open them with the standard IMAS exploration tools.

        Since transport is not solved, there are no profile comparison plots here, unlike in
        the self-consistent transport workflow below.


Exercise 2
----------

Next we look at the self-consistent transport workflow, which couples the equilibrium
calculated by NICE to a transport solve using TORAX.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run the ``inverse_convergence`` workflow for scenario ``105092`` (see the
        scenario description in Exercise 1 above).
        The workflow uses DINA output for the 105092 scenario as a target to give a desired plasma shape to NICE,
        which calculates the coil currents needed to get the best approximation of this shape. This shape,
        together with the core_profiles and core_sources IDS is then used to calculate the current, ion and electron transport using TORAX.

        .. note::
            This run might take a while and will only show feedback through the recorder actor
            after NICE has returned its first output.
            To run it faster, stack an override after the case that lowers the number of time
            slices, for example ``run.loop.max_slices: 11``. For 7-11 timeslices the general
            behavior is still very recognisable. 


    .. md-tab-item:: Solution

        .. code-block:: bash

            muscle_manager --start-all $PDS_REPO/cases/105092_convergence.ymmsl

        Check if results look as expected using the recorder actor plots in muscle3-dashboard.
        The solved equilibrium and coil currents are written to ``out_nice`` in the run
        directory, and the converged pulse to ``out_torax``.

        .. image:: images/pds_coils_105092.png
        .. image:: images/pds_equilibrium_0D_105092.png
        .. image:: images/pds_equilibrium_1D_105092.png

Exercise 3
----------

.. TODO: repointed from the case gallery when this branch was rebased onto
   feature/workflow-modularisation; revisit with the case-system doc update.

There are more cases available than the two used above. The workflows they are built on
are documented in :ref:`available_workflows`.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Pick two or three cases you have not run yet from ``cases/overrides/`` and
        run them. Read the page for each one first: what it couples, which shots it has, and
        what it writes.

    .. md-tab-item:: Solution

        For example the ``prescribed_transport`` case for shot 105099, which is the same
        ``source -> waveform_editor -> solve -> sink`` chain you ran in Exercise 1:

        .. code-block:: bash

            muscle_manager --start-all $PDS_REPO/cases/105099_prescribed.ymmsl

        Check the recorder actor plots in muscle3-dashboard and the sink output in the run
        directory, as in the exercises above.

Exercise 4
----------

Next we look at actor specific test workflows.
They are saved in the ``ymmsl_files`` directory.
Test workflows can be run to check if the individual actors are working as expected.
These workflows can be used as a template for your own workflows.
This exercise is mostly relevant for developers.

.. code-block:: bash

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

        .. code-block:: bash

            muscle_manager --start-all ymmsl_files/test_sink_source_actor.ymmsl

        ``test_sink_source_actor.ymmsl`` simply loads data from 1 Data Entry and saves it in a new one.
        The input and output are expected to be the same.

        ``test_waveform_editor.ymmsl`` takes the timestamp of an incoming message and sets a waveform for
        the ec_launchers/beam(1)/power_launched/data to ramp up to 50 kW over 10 seconds, remain constant for 30 seconds,
        and ramp down to 0 over 10 seconds again.

        ``test_nice_actor.ymmsl`` sends the desired plasma shape from a given IDS to NICE inverse mode to calculate the coil currents
        needed to realize this plasma shape. The equilibrium output is expected to be close to the input.

        Optionally, you can check if the results look as expected using the standard IMAS exploration tools.

.. todo::

    To match the training schedule

    - Add a METIS case and an evolutive-simulation case alongside the prescribed and
      self-consistent ones.
    - Add "how to visualize results during a run" -- currently the dashboard/recorder is
      only covered later, in :ref:`training/visualization`, that should should be about 
      creating your own visualization
    - Add "how to analyze/postprocess results after a run": which IMAS tools to open the
      sink output with, and what the scripts under ``visualization/`` produce.
    - Add a "do the results make sense?" subsection per case: what to look at, and what a
      good result looks like versus a converged-but-wrong one.
