.. _`case-inverse-convergence`:
.. _`case-105073-convergence`:
.. _`case-105078-convergence`:
.. _`case-105084-convergence`:
.. _`case-105084-literal-convergence`:
.. _`case-105092-convergence`:
.. _`case-105099-convergence`:

Inverse convergence against TORAX
=================================

Inverse pulse design converged against TORAX transport. Available for DINA shots 105073,
105078, 105084, 105092 and 105099, plus a second pulse design for 105084.

An outer Picard loop alternates NICE free-boundary inverse equilibrium and TORAX
transport, and stops once the largest coil-current change between iterations falls below
``loop.tolerance`` / ``loop.rel_tolerance`` -- or after ``loop.max_iterations``. An
``imas-validator`` actor then checks the converged coil currents against the ``iter-olc``
ruleset.

:Workflow: ``inverse_convergence`` -- :src:`workflows/inverse_convergence/README.md`
:Scenario: DINA shots 105073, 105078, 105084, 105092, 105099, in ``pds-scenarios``
:Output: ``<run_dir>/out_nice``, ``<run_dir>/out_torax``


Running it
----------

.. code-block:: bash

   bin/pds-create-case inverse_convergence 105073
   sbatch bin/pds-run-case.sbatch cases/inverse_convergence_105073

Substitute another shot number to run one of the others. See
:ref:`running_cases` for what a case directory holds and where the output goes.

Coupling
--------

.. coupling-diagram:: workflows/inverse_convergence/workflow.ymmsl

   ``loop`` drives the design: each iteration it hands the current equilibrium and core
   profiles to the waveform editor, which feeds ``equilibrium`` and ``transport``; their
   results come back on ``loop``'s S ports. When it converges, ``loop`` releases the final
   state to the sinks and the validator.

``equilibrium`` and ``transport`` are both sub-models rather than single programs, so the
workflow can swap what sits behind them without touching the coupling above.
``equilibrium`` load balances the per-slice NICE solves over N workers:

.. coupling-diagram:: workflows/inverse_convergence/workflow.ymmsl
   :model: nice_inverse

   The load balancer scatters slices to the workers and gathers the results back.

Workflow reference
------------------

``workflows/inverse_convergence/README.md``, included here so the two cannot drift apart.

.. include:: ../../../workflows/inverse_convergence/README.md
   :parser: myst_parser.sphinx_
