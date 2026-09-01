.. _`case-evolutive-controller`:
.. _`case-105073-evolutive-controller`:

Evolutive co-simulation under magnetic control
==============================================

TORAX and NICE running in lockstep, with a PCSSP magnetic controller
closing the coil-current feedback loop. Available for DINA shot 105073.

.. warning::

   This coupling has not yet been run to completion, so none of its runtime behaviour
   -- timestep stability, controller response, dt matching -- has been observed. The
   case below is wired correctly and resolves.

The other workflows are inverse designs, asking what coil currents produce a wanted
boundary. This workflow is forward. On each internal step TORAX evolves current and
temperature and hands ``equilibrium`` + ``core_profiles`` to ``nice_evo_rd`` -- NICE's
resistive-diffusion evolutive free-boundary solver -- which returns the updated
equilibrium for TORAX's next geometry. No outer loop and no convergence criterion: the
two simply advance together until the time window ends.

:Workflow: ``evolutive_controller`` -- :src:`workflows/evolutive_controller/README.md`
:Scenario: DINA shot 105073, in ``pds-scenarios``
:Output: ``<run_dir>/out_nice``, ``<run_dir>/out_torax`` and ``<run_dir>/out_controller``

Running it
----------

.. code-block:: bash

   bin/pds-create-case evolutive_controller 105073
   sbatch bin/pds-run-case.sbatch cases/evolutive_controller_105073

Substitute another shot number for the others. :ref:`running_cases` covers what a case
directory holds and where the output goes.

Coupling
--------

``source`` and the waveform editor assemble the F_INIT state and hand it to ``torax``,
``nice_evo_rd`` and ``magnetic_controller`` at once. ``torax`` and ``nice_evo_rd`` then
exchange through ``temporal_coupler``, which accumulates timeslices so each side sees a
whole trace rather than a single step, while ``magnetic_controller`` reads NICE's
``equilibrium`` and ``pf_active`` each step and returns a corrected ``pf_active``.

.. coupling-diagram:: docs/source/workflow_pages/evolutive_controller.svg

   ``source`` seeds the F_INIT state through the waveform editor; ``torax`` and
   ``nice_evo_rd`` then step forward against each other through ``temporal_coupler``, with
   ``magnetic_controller`` correcting the coil currents on every step.

.. note::

   This diagram is committed rather than drawn from the workflow file on each build,
   because ``ymmsl2svg`` cannot lay this model out yet: ``temporal_coupler`` has only S
   and O_I ports and no F_INIT conduit, so the timeline resolver cannot place it and
   reads every conduit feeding it as a mismatched call/release pair. Drawing it needs
   the O_I/S timeline annotations arriving in ymmsl 0.18.

Why the controller is not optional
----------------------------------

``nice_evo_rd`` receives on ``pf_active_s`` unconditionally on every internal step and
nothing else feeds that port, so the controller is what keeps the coupled system running
past the first step. Removing it does not give you an uncontrolled run, it gives you a
stalled one.

The F_INIT bootstrap
--------------------

``source`` reads a NICE-*reconstructed* equilibrium, not raw DINA. TORAX's geometry builder
needs flux-surface quantities -- ``r_inboard``/``r_outboard``, ``gm1`` through ``gm9``,
``dvolume_dpsi``, ``j_phi`` -- that only a real Grad-Shafranov solve computes, and DINA's
own equilibrium record never populates them. So this case reads the output of a completed
:ref:`inverse convergence <case-inverse-convergence>` run for the same shot, directly from
that run's directory: ``source.source_uri`` points at
``$PDS_REPO/cases/runs/inverse_convergence_${SHOT}/out_nice``. Run that case first, and do
not clear its run directory before running this one.

The waveform editor passes that equilibrium through an``equilibrium/*: {ref: eq}`` wildcard, 
so every field survives rather than a hand-pickedfew, and overlays the static machine 
description, ``core_profiles`` and the ECRH trace from the scenario's own data.

Two fields in that overlay are load-bearing, both because NICE indexes them without a
size check and segfaults on an empty one:
``core_profiles/profiles_1d/conductivity_parallel`` (with ``j_non_inductive``), and
``pf_active/coil(*)/voltage/data``, which the currentless machine-description
``pf_active`` leaves empty.

.. note::

   ``torax.fixed_dt``, ``nice_evo_rd.dt``, ``nice_evo_rd.t_interval`` and
   ``config_nice.xml``'s ``<dt>`` are all assumed to be a consistent 0.01s -- a starting
   point carried over from the workflow's defaults, not a value tuned for this scenario
   or validated for solver stability.

Workflow reference
------------------

.. include:: ../../../workflows/evolutive_controller/README.md
   :parser: myst_parser.sphinx_
