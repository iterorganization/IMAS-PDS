.. _`case-metis-nice-inverse`:
.. _`case-105073-metis-nice-inverse`:

METIS with a NICE inverse solve
===============================

METIS transport from DINA input, followed by a NICE inverse solve that fits coil currents
to the equilibrium METIS produced. Overrides exist for DINA shots 105073, 105078,
105084, 105092 and 105099, and CI exercises 105084.

The coupling order is the reverse of the design cases. There, NICE solves first and a
transport code fills a hole inside an outer loop; here METIS leads, runs the transport over
the whole trace, and NICE is a single downstream pass over its equilibrium. METIS runs
once, NICE runs once.

:Workflow: ``metis_nice_inverse_from_dina`` -- :src:`workflows/metis_nice_inverse_from_dina/workflow.ymmsl`
:Scenario: DINA shots 105073, 105078, 105084, 105092 and 105099, in ``pds-scenarios``
:Output: ``<run_dir>/metis_out`` and ``<run_dir>/nice_out``

Running it
----------

.. code-block:: bash

   bin/pds-create-case metis_nice_inverse_from_dina 105084
   sbatch bin/pds-run-case.sbatch cases/metis_nice_inverse_from_dina_105084

Substitute another shot number for the others. :ref:`running_cases` describes what
a case directory contains and where the output goes.

.. note::

   ``pds-create-case`` takes noticeably longer for this workflow than for the design
   cases, because ``preprocess.sh`` runs a MATLAB conversion (see below).

Coupling
--------

.. coupling-diagram:: workflows/metis_nice_inverse_from_dina/workflow.ymmsl

   ``source_metis`` supplies the pulse schedule and the profiles and sources that constrain
   METIS. METIS's equilibrium goes three ways: to its own sink, to ``nice`` as the target
   boundary, and to ``source_nice``, which uses its timestamps to re-slice the static
   machine description onto the same time base.

Input data
----------

Both inputs are built from the shot's raw DINA source by the workflow's ``preprocess.sh``,
once, at ``pds-create-case`` time, and frozen into the case:

``$CASE_DIR/preprocess/metis_in``
   METIS's own dataset. METIS does not take a plasma state the way TORAX does -- it builds
   its input from a ``pulse_schedule`` IDS, in a DD layout that is workflow-specific, so
   nothing pre-bakes it into ``pds-scenarios``. Producing it needs MATLAB and the
   ``METIS-IRFM`` module.

``$CASE_DIR/preprocess/dina_in``
   NICE's DINA-derived machine description. ``source_nice`` is a ``sink_source``: it
   re-emits all four machine-description lanes out of a single entry, so that entry's
   ``pf_active`` has to keep DINA's coil currents.

Predictive is the default: the workflow's ``settings.ymmsl`` leaves all five
``metis_external_data_*`` switches off, so METIS computes its own profiles and sources.
Interpretative mode means enabling them in
``cases/overrides/metis_nice_inverse_from_dina_<shot>.ymmsl``. This is why the old
``metis_interpretative_...`` and ``metis_predictive_nice_inverse_from_dina`` templates
collapse into one workflow -- their graphs were identical.

.. note::

   ``metis.metis_psioffset`` is a per-shot calibration constant, applied when ``psi_LCFS``
   is a constraint in the inverse solve. ``preprocess.sh`` computes it from the shot's own
   DINA equilibrium and passes it back through ``preprocess_settings.ymmsl``. Where that
   MATLAB step cannot run, the generic settings fall back to a fixed ``9.0``, which needs
   calibrating before the output means anything.
