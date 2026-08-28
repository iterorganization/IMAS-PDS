.. _`case-metis-from-dina`:

METIS transport from DINA
=========================

METIS run on its own from DINA input, with no equilibrium solve at all. Overrides
exist for DINA shots 105084 and 105092, and CI exercises 105084.

A source supplies METIS with the pulse schedule, profiles and sources; METIS
integrates the trace; a sink writes the result. There is no iteration and no
feedback path.

The graph is ``metis_nice_inverse_from_dina`` without the NICE branch, and is
otherwise identical to it. Use it where the transport solution is needed but coil
currents fitted to that equilibrium are not.

:Workflow: ``metis_from_dina`` -- :src:`workflows/metis_from_dina/workflow.ymmsl`
:Scenario: DINA shots 105084 and 105092, in ``pds-scenarios``
:Output: ``<run_dir>/metis_out``

Predictive or interpretative
----------------------------

The ``metis.metis_external_data_*`` settings control which quantities METIS takes
from the received IDSs rather than computing itself. This single workflow replaces
the former ``metis_predictive_from_dina`` and ``metis_interpretative_from_dina``,
whose graphs were identical and differed only in those settings.

The workflow's ``settings.ymmsl`` sets all of them to ``0``, making **predictive
the default**: METIS computes its own profiles and sources. Interpretative mode
means enabling the relevant settings in
``cases/overrides/metis_from_dina_<shot>.ymmsl``.

Running it
----------

.. code-block:: bash

   bin/pds-create-case metis_from_dina 105084
   sbatch bin/pds-run-case.sbatch cases/metis_from_dina_105084

Substitute another shot number for the others. :ref:`running_cases` describes what
a case directory contains and where the output goes.

.. note::

   ``pds-create-case`` takes noticeably longer for this workflow than for the
   others. METIS's IMAS layout is workflow-specific, so nothing pre-bakes it into
   ``pds-scenarios``; the workflow's ``preprocess.sh`` builds it from the shot's
   raw DINA source into ``$CASE_DIR/preprocess/metis_in``, once, at case-creation
   time. That step loads MATLAB and runs a conversion, and the case carries the
   result as a frozen snapshot.

Coupling
--------

.. coupling-diagram:: workflows/metis_from_dina/workflow.ymmsl

   ``source_metis`` supplies the pulse schedule, profiles and sources; ``metis``
   integrates the trace; ``sink_metis`` writes the equilibrium, pulse schedule,
   plasma profiles, plasma sources and summary it produced.

The pulse schedule goes to METIS twice, on both ``F_INIT`` and its ``_in_f`` port:
METIS re-reads its inputs on each reuse iteration, so a value sent only at
``F_INIT`` would not survive into later ones.

.. note::

   ``metis.metis_psioffset`` is a per-shot calibration constant. The workflow's
   generic settings carry a fixed fallback of ``9.0``, but ``preprocess.sh``
   computes this shot's real value from its own DINA equilibrium and overrides it
   through ``preprocess_settings.ymmsl``. If that MATLAB step cannot run, the
   fallback applies and needs calibrating before the output means anything.
