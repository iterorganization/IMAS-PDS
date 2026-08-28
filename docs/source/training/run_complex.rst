.. _`training/run_complex`:

Running existing workflows
==========================

.. TODO: the case gallery (docs/source/cases/) is not part of this branch; link the
   per-case pages from the exercises here if it lands.

In this section we run the premade ITER workflows. Every case here follows the same two
steps: build the case folder, then submit it. As in the previous sections, you need a
terminal with an active PDS environment.

.. code-block:: bash

    # Open the directory in which you cloned the PDS
    cd <your PDS install>
    # Load the PDS module
    module use /work/projects/pds/modules/all
    module load PDS

Running on a compute node
-------------------------

Everything so far ran on the login node. That is fine for the small test workflows, but not
for the real cases in the next section: they require more resources than a login node
should be asked for.



Before you can submit anything, you need a case to submit. That is what
``bin/pds-create-case`` is for: it pairs a workflow with a scenario and writes the result to
``cases/<workflow>_<shot>/``.

.. code-block:: bash

    bin/pds-create-case <workflow> <shot>

It takes the workflow's ``workflow.ymmsl`` and ``settings.ymmsl``, fills in the paths for
that shot, adds the per-shot override from ``cases/overrides/`` if there is one, and copies
every config file those settings point at into the case's own ``config/``. The result is the
frozen snapshot described in :ref:`training/understanding`.

You only do this once per workflow and shot. After that the case folder is yours to submit
as often as you like, which is the second step:

.. code-block:: bash

    sbatch bin/pds-run-case.sbatch cases/<workflow>_<shot>


``sbatch`` hands the job to the queue and returns immediately with a job number. 
Some useful commands when you're working with SLURM:

.. code-block:: bash

    squeue --me                  # Check if the simulation is waiting, or running?
    scancel <jobid>              # Stop it
    tail -f slurm-<jobid>.out    # Check the job script itself printed

The MUSCLE3 dashboard from the previous section works exactly the same way when
you submit to a compute node. The run directory lands in ``cases/runs/`` on the shared filesystem, 
so a dashboard you started on the login node picks the run up and follows it live, 
while the simulation itself runs on a compute node.


Exercise 1
----------

Before running a full equilibrium+transport workflow, it is useful to first look at the
``prescribed_transport`` workflow. This is a very simple  workflow: a
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
        a flattop phase at ~ 3 MA from t=9 to t=147,
        and a ramp-down phase from t=147 to t=170.

        After the run has finished, take a look at the results using the equilibrium 
        recorder in MUSCLE3 dashboard, are they what you expect?

    .. md-tab-item:: Solution

        .. code-block:: bash

            bin/pds-create-case prescribed_transport 105092
            sbatch bin/pds-run-case.sbatch cases/prescribed_transport_105092

        Check if the results look as expected using the recorder actor plots in muscle3-dashboard.
        You can disable the ``Live View`` checkbox to scroll through the time line of the results.
        The solved equilibrium and coil currents are written to ``out_nice`` in the run
        directory, ``cases/runs/prescribed_transport_105092/``, so you can also open them with
        the standard IMAS exploration tools.



Watching a run while it happens
-------------------------------

An ``inverse_convergence`` run is long enough that you do not want to sit and wait for it in
silence. Two things are worth having open while it goes.

The first is the dashboard graph you already know from :ref:`training/run_first`: it tells
you which actor is busy right now, and it is the fastest way to notice that something has
stalled or died.

The second is new. These workflows carry a **recorder** actor, which listens in on the data
travelling between the other actors and visualizes it as it goes.
When you open the run in the dashboard and you get an extra tab per recorder for the 
NICE and TORAX output


Exercise 2
----------

Next we look at the self-consistent transport workflow, which couples the equilibrium
calculated by NICE to a transport solve using TORAX.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run the ``inverse_convergence`` workflow for scenario ``105092``, this is the 
        same scenario that we used in the previous exercise.
        The workflow uses DINA output for the 105092 scenario as a target to give a desired plasma shape to NICE,
        which calculates the coil currents needed to get the best approximation of this shape. This shape,
        together with the core_profiles and core_sources IDS is then used to calculate the current, ion and electron transport using TORAX.

        Are the results what you expect?

        .. hint::
            You can take a look at the results of the recorder actor for NICE and TORAX 
            while the run is still going, or after the run is finished, you can check out the
            post-processed plots. These are available in the created run folder under:
            ``cases/runs/inverse_convergence_105092/plots``



    .. md-tab-item:: Solution

        .. code-block:: bash

            bin/pds-create-case inverse_convergence 105092
            sbatch bin/pds-run-case.sbatch cases/inverse_convergence_105092


        Check if results look as expected using the recorder actor plots in muscle3-dashboard.
        The solved equilibrium and coil currents are written to ``out_nice`` in the run
        directory, ``cases/runs/inverse_convergence_105092/``, and the converged pulse to
        ``out_torax``.

        .. image:: images/pds_coils_105092.png
        .. image:: images/pds_equilibrium_0D_105092.png
        .. image:: images/pds_equilibrium_1D_105092.png


.. tip::
    The run from the previous exercise might take a while and will only show feedback through the recorder actor
    after NICE has returned its first output.
    To run it faster, you can add an override that lowers the number of time slice,
    for example ``loop.max_slices: 11``. For 7-11 timeslices the general
    behavior is still very recognisable.

    To do that, put the setting in a small yMMSL file of your own, say
    ``fewer_slices.ymmsl``:

    .. code-block:: yaml

        ymmsl_version: v0.2
        settings:
          loop.max_slices: 11

    and pass it after the case folder on the ``sbatch`` line. e.g.

    .. code-block:: bash

        sbatch bin/pds-run-case.sbatch cases/inverse_convergence_105092 ./fewer_slices.ymmsl

Looking at the results afterwards
---------------------------------

When the job finishes, everything it produced is in one place:

.. code-block:: text

    cases/runs/inverse_convergence_105092/
        muscle3_manager.log     # what the manager did
        configuration.ymmsl     # the settings this run actually used, fully resolved
        instances/              # per-actor logs and working directories
        out_nice/               # the solved equilibrium and coil currents
        out_torax/              # the transport solution (transport workflows only)
        plots/                  # validation figures, see below

Two of these are worth getting into the habit of opening.

``configuration.ymmsl`` is the record of what you ran. When a run behaves differently from
the last one and you are not sure why, comparing this file between the two run directories
usually answers it in a few seconds.

``plots/`` is filled in automatically after the simulation finishes. Each workflow ships a
``postprocess.sh``, which the job runs once the manager is done. This is commonly used
to generate output plots, so this is a good place to look for results.

Exercise 3
----------

So far both cases solved an equilibrium with NICE. ``metis_from_dina`` is a different kind of
workflow: METIS is a fast integrated transport code that does the whole pulse on its own, so
this case is a short chain of ``source -> metis -> sink`` with no equilibrium solver and no
outer loop.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run ``metis_from_dina`` for shot ``105084`` and look at the plots it produces.

        .. note::

            Building this case takes longer than the others. METIS needs its input in its own
            layout, so ``pds-create-case`` runs a MATLAB preprocessing step for this workflow,
            and that step is where most of the waiting happens. It
            runs once, when the case is created, not on every run.

    .. md-tab-item:: Solution

        .. code-block:: bash

            bin/pds-create-case metis_from_dina 105084
            sbatch bin/pds-run-case.sbatch cases/metis_from_dina_105084

        The output DBEntry is ``metis_out`` rather than ``out_nice``, and the validation plots
        in ``plots/`` compare METIS against DINA.

Exercise 4
----------

The last of the premade workflows is ``evolutive_controller``. Where ``inverse_convergence``
asks "which coil currents produce this shape?", this one runs the pulse forward the way the
machine would: a controller adjusts the coil voltages as the plasma evolves, and NICE follows
it in evolutive mode.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run ``evolutive_controller`` for shot ``105073``.

        There is a catch, and it is worth understanding rather than working around: this
        workflow needs a completed ``inverse_convergence`` run for the *same shot* before it
        can start. Why would that be?

    .. md-tab-item:: Hint

        Look at what the ``source`` component reads in
        ``workflows/evolutive_controller/README.md``. What does the raw DINA equilibrium not
        contain that a solved one does?

    .. md-tab-item:: Solution

        .. code-block:: bash

            # first, if you have not already run it for this shot
            bin/pds-create-case inverse_convergence 105073
            sbatch bin/pds-run-case.sbatch cases/inverse_convergence_105073

            # then, once that has finished
            bin/pds-create-case evolutive_controller 105073
            sbatch bin/pds-run-case.sbatch cases/evolutive_controller_105073

        The forward solve needs flux-surface quantities that only a real equilibrium solve
        computes, and the raw DINA equilibrium in the scenario does not carry them. The
        ``inverse_convergence`` output does, so that run's ``out_nice`` is what this workflow
        starts from.

Exercise 5
----------

.. TODO: these pointed at the case gallery (docs/source/cases/), which is not part of
   this branch; restore those links if the gallery lands.

There are more shots available than the ones used above. The workflows they are built on
are documented in :ref:`available_workflows`.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Pick two or three shots you have not run yet, ``cases/overrides/`` shows which
        ones each workflow has been tuned for, and run them. Work out first what each one
        couples and what it will write, then check afterwards whether the results hold up
        against the questions above.

    .. md-tab-item:: Solution

        For example the ``prescribed_transport`` case for shot 105099, which is the same
        ``source -> waveform_editor -> solve -> sink`` chain you ran in Exercise 1:

        .. code-block:: bash

            bin/pds-create-case prescribed_transport 105099
            sbatch bin/pds-run-case.sbatch cases/prescribed_transport_105099

        Check the recorder actor plots in muscle3-dashboard and the sink output in the run
        directory, as in the exercises above.

Exercise 6
----------

This exercise is mostly relevant for developers.
Next we look at actor specific test workflows, they are saved in the ``ymmsl_files`` directory.
Test workflows can be run to check if the individual actors are working as expected.
These workflows can be used as a template for your own workflows.

.. code-block:: bash

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
