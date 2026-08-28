.. _`case-metis-nice-inverse`:
.. _`case-105073-metis-nice-inverse`:

METIS with a NICE inverse solve
===============================

METIS transport from DINA input, followed by a NICE inverse solve that fits coil currents
to the equilibrium METIS produced. Available for DINA shot 105073.

The coupling order is the reverse of the design cases. There, NICE solves first and a
transport code fills a hole inside an outer loop; here METIS leads, runs the transport over
the whole trace, and NICE is a single downstream pass over its equilibrium. There is no
outer iteration and no convergence criterion -- METIS runs once, NICE runs once.

:Workflow: ``metis_nice_inverse_from_dina`` -- :src:`workflows/metis_nice_inverse_from_dina/README.md`
:Scenario: DINA shot 105073, in ``pds-scenarios``
:Output: ``<run_dir>/out_metis`` and ``<run_dir>/out_nice``

This is the case-based form of the old ``metis_interpretative_nice_inverse_from_dina`` and
``metis_predictive_nice_inverse_from_dina`` templates. Their graphs were identical --
interpretative versus predictive is five ``metis_external_data_*`` settings, not a separate
workflow -- so the two collapse into one workflow with the choice made in the case.

Running it
----------

.. code-block:: bash

   bin/pds-create-case metis_nice_inverse_from_dina 105084
   sbatch bin/pds-run-case.sbatch cases/metis_nice_inverse_from_dina_105084

Substitute another shot number to run one of the others. See
:ref:`running_cases` for what a case directory holds and where the output goes.

Coupling
--------

.. coupling-diagram:: workflows/metis_nice_inverse_from_dina/workflow.ymmsl

   ``source_metis`` supplies the pulse schedule and the profiles and sources that constrain
   METIS. METIS's equilibrium goes three ways: to its own sink, to ``nice`` as the target
   boundary, and to ``source_nice``, which uses its timestamps to re-slice the static
   machine description onto the same time base.

Input data
----------

Unlike the design cases, this one needs a scenario prepared two ways:

``data/metis_in``
   METIS does not take a plasma state the way TORAX does -- it builds its input from a
   ``pulse_schedule`` IDS, which a plain ``data/in`` does not carry. Produced by the
   separate ``tools/prepare 105073 --metis`` step, which needs MATLAB and the METIS module.
   ``METIS_MODE`` (``interpretative``, the default, or ``predictive``) is baked into what it
   writes, so switching mode means rebuilding the input as well as flipping the settings.

``data/in`` with ``MD_LAYOUT=combined``
   ``source_nice`` is a ``sink_source``: it re-emits all four machine-description lanes out
   of a single entry, so that entry's ``pf_active`` has to keep DINA's coil currents. A
   scenario prepared the default ``separate`` way splits the machine description off into
   ``data/in_md`` and leaves ``data/in`` with geometry only.

105073 is the case shot because it is the one scenario currently prepared ``combined``.

.. note::

   ``metis.metis_psioffset`` is a per-scenario calibration constant, applied when
   ``psi_LCFS`` is a constraint in the inverse solve. The old workflow read it from a
   ``tmp/PSI_OFFSET`` file that nothing in the repository ever wrote. The workflow's
   ``preprocess.sh`` now computes it from the run's own DINA equilibrium and passes it
   back through ``preprocess_settings.ymmsl``, and the workflow is exercised in CI. Where
   that computation cannot run, the generic settings fall back to a fixed value, which
   needs calibrating before the output means anything.
