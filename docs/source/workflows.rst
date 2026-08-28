.. _`workflows`:

Available workflows
===================

A workflow describes *how* something is simulated: which codes are coupled, in
what order, over which ports. It carries no shot data -- that comes from the
scenario you pair it with when you create a case. See :ref:`running_cases`.

This page is the chooser: what each workflow couples, which shots are exercised,
and what input data it needs. Each one links on to its own page, where the
coupling is drawn out component by component.

The workflows
-------------

Each coupling below is drawn from its own ``workflow.ymmsl`` at build time, so the
diagrams cannot drift from the couplings they document.

.. grid:: 1 2 3 3
   :gutter: 2

   .. grid-item-card:: Prescribed transport
      :img-top: workflow_pages/diagrams/prescribed_transport.svg
      :link: case-prescribed-transport
      :link-type: ref

      A single NICE inverse solve against a boundary that is fixed up front. Transport is
      not solved at all, and each time slice is independent, so there is no outer loop.

   .. grid-item-card:: Inverse convergence against TORAX
      :img-top: workflow_pages/diagrams/inverse_convergence.svg
      :link: case-inverse-convergence
      :link-type: ref

      An outer loop alternating NICE free-boundary inverse equilibrium and TORAX transport
      until the coil currents stop moving, with an ``imas-validator`` pass over the
      converged coil currents.

   .. grid-item-card:: METIS with a NICE inverse solve
      :img-top: workflow_pages/diagrams/metis_nice_inverse.svg
      :link: case-metis-nice-inverse
      :link-type: ref

      METIS transport from DINA input, then a single NICE inverse pass fitting coil
      currents to the equilibrium it produced. No outer loop.

   .. grid-item-card:: METIS transport from DINA
      :img-top: workflow_pages/diagrams/metis_from_dina.svg
      :link: case-metis-from-dina
      :link-type: ref

      METIS alone, integrating the trace from DINA input with no equilibrium solve.
      The simplest coupling here: source, solver, sink, nothing feeding back.

   .. grid-item-card:: Evolutive co-simulation under magnetic control
      :img-top: workflow_pages/diagrams/evolutive_controller.svg
      :link: case-evolutive-controller
      :link-type: ref

      Forward, not inverse: TORAX and NICE step together in lockstep while a PCSSP
      controller closes the coil-current loop.

Side by side
------------

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

.. toctree::
   :hidden:

   workflow_pages/prescribed_transport
   workflow_pages/inverse_convergence
   workflow_pages/metis_from_dina
   workflow_pages/metis_nice_inverse
   workflow_pages/evolutive_controller
