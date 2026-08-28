.. _`case-evolutive-controller`:
.. _`case-105073-evolutive-controller`:

Evolutive co-simulation under magnetic control
==============================================

TORAX and NICE stepping forward together in lockstep, with a PCSSP magnetic controller
closing the coil-current feedback loop. Available for DINA shot 105073.

.. warning::

   This coupling has not yet been run to completion, so none of its runtime behaviour
   (timestep stability, controller response, dt matching) has been observed. The case below
   is wired correctly and resolves.

The other cases are inverse designs: they ask what coil currents produce a wanted boundary.
This one is forward. Each internal step TORAX evolves current and temperature and hands
``equilibrium`` + ``core_profiles`` to ``nice_evo_rd`` -- NICE's resistive-diffusion
evolutive free-boundary solver -- which returns the updated equilibrium for TORAX's next
geometry. There is no outer loop and no convergence criterion; the two simply advance
together until the time window ends.

:Workflow: ``evolutive_controller`` -- :src:`workflows/evolutive_controller/README.md`
:Scenario: DINA shot 105073, in ``pds-scenarios``
:Output: ``<run_dir>/out_nice_evo_rd``, ``<run_dir>/out_torax`` and ``<run_dir>/out_controller``

Running it
----------

.. code-block:: bash

   bin/pds-create-case evolutive_controller 105073
   sbatch bin/pds-run-case.sbatch cases/evolutive_controller_105073

Substitute another shot number to run one of the others. See
:ref:`running_cases` for what a case directory holds and where the output goes.

Coupling
--------

``source`` and the waveform editor assemble the F_INIT state and hand it to ``torax``,
``nice_evo_rd`` and ``magnetic_controller`` at once. ``torax`` and ``nice_evo_rd`` then
exchange through ``temporal_coupler``, which accumulates timeslices so each side sees a
whole trace rather than a single step, while ``magnetic_controller`` reads NICE's
``equilibrium`` and ``pf_active`` each step and returns a corrected ``pf_active``. Three
sinks and two recorders tap the outputs.

.. coupling-diagram:: docs/source/cases/evolutive_controller.svg

   ``source`` seeds the F_INIT state through the waveform editor; ``torax`` and
   ``nice_evo_rd`` then step forward against each other through ``temporal_coupler``, with
   ``magnetic_controller`` correcting the coil currents on every step.

.. note::

   This diagram is committed rather than drawn from the workflow file on each build.
   ``ymmsl2svg`` cannot lay this model out yet: ``temporal_coupler`` has only S and O_I
   ports and no F_INIT conduit, so the timeline resolver cannot place it and reads every
   conduit feeding it as a mismatched call/release pair. Drawing it needs the O_I/S
   timeline annotations arriving in ymmsl 0.18.

Why the controller is not optional
----------------------------------

``nice_evo_rd`` receives on ``pf_active_s`` unconditionally on every internal step, and
nothing else in this workflow feeds that port. The controller is therefore what keeps the
coupled system running past the first step -- removing it does not give you an
uncontrolled run, it gives you a stalled one.

The F_INIT bootstrap
--------------------

``source`` reads a NICE-*reconstructed* equilibrium, not raw DINA. TORAX's geometry builder
needs flux-surface quantities -- ``r_inboard``/``r_outboard``, ``gm1`` through ``gm9``,
``dvolume_dpsi``, ``j_phi`` -- that only a real Grad-Shafranov solve computes, and DINA's
own equilibrium record never populates them. So this case depends on a completed
:ref:`inverse convergence <case-inverse-convergence>` run for the same shot, whose NICE
output is staged in the scenario as ``data/from_inverse_convergence``.

The waveform editor passes that equilibrium through whole -- an ``equilibrium/*: {ref: eq}``
wildcard, so every field survives rather than a hand-picked few -- and overlays the static
machine description, ``core_profiles`` and the ECRH trace from the scenario's own data.

Two fields in that overlay are load-bearing rather than cosmetic, both because NICE indexes
them without a size check and segfaults on an empty one:
``core_profiles/profiles_1d/conductivity_parallel`` (with ``j_non_inductive``), and
``pf_active/coil(*)/voltage/data``, which the currentless machine-description ``pf_active``
leaves empty.

.. note::

   ``torax.fixed_dt``, ``nice_evo_rd.dt``, ``nice_evo_rd.t_interval`` and
   ``config_nice.xml``'s ``<dt>`` are all assumed to be a consistent 0.01s. That is a
   starting point carried over from the workflow's defaults, not a value tuned for this
   scenario or validated for solver stability.
