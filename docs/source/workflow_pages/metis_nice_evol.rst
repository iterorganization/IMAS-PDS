.. _`case-metis-nice-evol`:

METIS evolutive co-simulation under magnetic control
====================================================

METIS and NICE running in lockstep, with a PCSSP magnetic controller closing the
coil-current feedback loop. Overrides exist for DINA shots 105073 and 105084.

.. warning::

   This coupling has not yet been run end to end and is not exercised in CI.

This is :ref:`evolutive_controller <case-evolutive-controller>` with METIS in place of
TORAX. Instead of reading a completed ``inverse_convergence`` run, it bootstraps from
DINA the way :ref:`metis_nice_inverse_from_dina <case-metis-nice-inverse>` does: a
one-shot ``metis_init`` seeds ``nice_inv`` and ``nice_evo_rd``, then the in-loop
``metis`` and ``nice_evo_rd`` step forward against each other while
``magnetic_controller`` corrects the coil currents.

:Workflow: ``metis_nice_evol_from_dina`` -- :src:`workflows/metis_nice_evol_from_dina/README.md`
:Scenario: DINA shots 105073 and 105084
:Output: ``<run_dir>/metis_out``, ``<run_dir>/metis_init_out``, ``<run_dir>/nice_out`` and
   ``<run_dir>/controller_out``

Running it
----------

.. code-block:: bash

   bin/pds-create-case metis_nice_evol_from_dina 105073
   sbatch --cpus-per-task=24 bin/pds-run-case.sbatch cases/metis_nice_evol_from_dina_105073

The components need more than the default 16 CPUs of ``pds-run-case.sbatch``.
``pds-create-case`` runs the same MATLAB conversion as ``metis_nice_inverse_from_dina``,
so it is noticeably slower than for the design cases.

Coupling
--------

``source_metis`` bootstraps both METIS instances. ``metis_init``'s equilibrium seeds
``nice_inv`` and ``nice_evo_rd``; ``reference_rebase`` shifts the DINA reference trace onto
``nice_inv``'s solution at the start time and hands it to ``magnetic_controller``. In the
loop, ``metis`` sends ``equilibrium`` and ``core_profiles`` to ``nice_evo_rd``, which
returns its equilibrium to ``metis``, to the controller and to the two
``synchro_nice_metis_*`` actors. Those re-slice METIS's input trace at NICE's timestamp to
give ``metis`` its next ``pulse_schedule``, ``core_profiles`` and ``core_sources``.

.. note::

   There is no coupling diagram on this page: ``ymmsl2svg`` cannot lay this model out
   yet, for the same reason as ``evolutive_controller`` -- the timeline resolver cannot
   place the S/O_I loop between ``metis`` and ``nice_evo_rd`` without the O_I/S timeline
   annotations arriving in ymmsl 0.18.

Workflow reference
------------------

.. include:: ../../../workflows/metis_nice_evol_from_dina/README.md
   :parser: myst_parser.sphinx_
