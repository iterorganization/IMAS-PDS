.. _`workflows`:

Available workflows
===================

A workflow describes *how* something is simulated: which codes are coupled, in
what order, over which ports. It carries no shot data -- that comes from the
scenario you pair it with when you create a case. See :ref:`running_cases`.

Choosing a workflow
-------------------

.. list-table::
   :header-rows: 1
   :widths: 25 24 18 33

   * - Workflow
     - Couples
     - Outer loop
     - Use it when
   * - ``prescribed_transport``
     - NICE inverse
     - none
     - You have a plasma boundary already and just want the coil currents that
       produce it.
   * - ``inverse_convergence``
     - NICE inverse + TORAX
     - Picard, to convergence
     - You want a pulse that is self-consistent between the equilibrium and the
       transport solution.
   * - ``evolutive_controller``
     - NICE evolutive + TORAX + PCSSP
     - lockstep in time
     - You want a genuine forward simulation with the magnetic controller in the
       loop.
   * - ``metis_from_dina``
     - METIS
     - none
     - You want fast integrated transport from DINA input, without an
       equilibrium solve.
   * - ``metis_nice_inverse_from_dina``
     - METIS + NICE inverse
     - none
     - As above, then fit coil currents to the equilibrium METIS produced.

Two of these have a prerequisite:

- ``evolutive_controller`` bootstraps from a completed ``inverse_convergence``
  run **for the same shot** -- run that first.
- ``metis_from_dina`` and ``metis_nice_inverse_from_dina`` build their own METIS
  input from raw DINA data at case-creation time, so ``pds-create-case`` takes
  noticeably longer for them than for the others.

Which shots work
----------------

Any shot present in your ``$SCENARIOS_REPO`` can be tried with any workflow. A
file in ``cases/overrides/`` is *not* a prerequisite -- it only exists for shots
that need tuning beyond the workflow's generic settings.

Two lists are therefore worth separating:

.. list-table::
   :header-rows: 1
   :widths: 34 22 44

   * - Workflow
     - Exercised in CI
     - Has tuning overrides for
   * - ``prescribed_transport``
     - ``105099``
     - *(none needed)*
   * - ``inverse_convergence``
     - ``105073``
     - ``105073``, ``105099``, ``105084_literal``
   * - ``evolutive_controller``
     - ``105073``
     - ``105073``, ``105084``
   * - ``metis_from_dina``
     - ``105084``
     - ``105084``, ``105092``
   * - ``metis_nice_inverse_from_dina``
     - ``105084``
     - ``105073``, ``105078``, ``105084``, ``105092``, ``105099``

The "exercised in CI" column is the one to trust: those five combinations run
end to end on every integration build (``ci/run_test_workflows.sh``). Others may
work and are simply not covered.

Input data requirements
-----------------------

All workflows:

- DDv4 input data. The METIS workflows convert DINA data as part of
  preprocessing if needed.

For any workflow that runs NICE:

- ``equilibrium``, ``pf_active``, ``pf_passive``, ``iron_core`` and ``wall``
  IDSs, from a machine description.
- ``pf_active`` with exactly one element in the elements AoS per coil.
  Preprocessing generates this if needed.
- ``pf_active`` coil objects carrying resistance values.

For any workflow that runs METIS:

- ``summary``, ``pulse_schedule``, ``equilibrium``, ``core_profiles`` (or
  ``plasma_profiles``) and ``core_sources`` (or ``plasma_sources``) IDSs.
- ``pulse_schedule`` filled. Preprocessing creates it from DINA data if needed.
  See the `METIS input documentation
  <https://github.com/IRFM/METIS/blob/main/doc/METIS_inputs_from_IMAS_IDSs.pdf>`_
  for what it expects.

Per-workflow reference
----------------------

Each workflow's own ``README.md`` is the single source of truth for what it does,
its assumptions, and what its output looks like. They are included below rather
than paraphrased, so they cannot drift.

.. _`workflow-prescribed-transport`:

prescribed_transport
^^^^^^^^^^^^^^^^^^^^

.. include:: ../../workflows/prescribed_transport/README.md
   :parser: myst_parser.sphinx_

.. _`workflow-inverse-convergence`:

inverse_convergence
^^^^^^^^^^^^^^^^^^^

.. include:: ../../workflows/inverse_convergence/README.md
   :parser: myst_parser.sphinx_

.. _`workflow-evolutive-controller`:

evolutive_controller
^^^^^^^^^^^^^^^^^^^^

.. include:: ../../workflows/evolutive_controller/README.md
   :parser: myst_parser.sphinx_

.. _`workflow-metis`:

The METIS workflows
^^^^^^^^^^^^^^^^^^^

``metis_from_dina`` and ``metis_nice_inverse_from_dina`` do not yet have
READMEs. Until they do, the header comment at the top of each
``workflow.ymmsl`` is the best description:

- :src:`workflows/metis_from_dina/workflow.ymmsl`
- :src:`workflows/metis_nice_inverse_from_dina/workflow.ymmsl`

Both replaced earlier ``metis_interpretative_*`` and ``metis_predictive_*``
workflows. Interpretative versus predictive is now a setting on one workflow
rather than a separate directory: override the ``metis_external_data_*`` keys in
the case to run interpretatively.
