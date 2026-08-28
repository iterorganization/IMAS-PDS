.. _`workflows`:

Available workflows
===================

A workflow describes *how* something is simulated: which codes are coupled, in
what order, over which ports. It carries no shot data -- that comes from the
scenario you pair it with when you create a case. See :ref:`running_cases`.

.. toctree::
   :hidden:

   workflow_pages/prescribed_transport
   workflow_pages/inverse_convergence
   workflow_pages/metis_from_dina
   workflow_pages/metis_nice_inverse
   workflow_pages/evolutive_controller

The workflows
-------------

.. grid:: 1 2 3 3
   :gutter: 2

   .. grid-item-card:: Prescribed transport
      :img-top: workflow_pages/diagrams/prescribed_transport.svg
      :link: case-prescribed-transport
      :link-type: ref

      One NICE inverse solve against a boundary fixed up front. No transport, no outer
      loop.

   .. grid-item-card:: Inverse convergence against TORAX
      :img-top: workflow_pages/diagrams/inverse_convergence.svg
      :link: case-inverse-convergence
      :link-type: ref

      NICE and TORAX alternating until the coil currents stop moving, then an
      ``imas-validator`` pass over the result.

   .. grid-item-card:: METIS with a NICE inverse solve
      :img-top: workflow_pages/diagrams/metis_nice_inverse.svg
      :link: case-metis-nice-inverse
      :link-type: ref

      METIS transport from DINA, then a single NICE pass fitting coil currents to the
      equilibrium it produced.

   .. grid-item-card:: METIS transport from DINA
      :img-top: workflow_pages/diagrams/metis_from_dina.svg
      :link: case-metis-from-dina
      :link-type: ref

      METIS alone, no equilibrium solve. The simplest coupling here: source, solver,
      sink.

   .. grid-item-card:: Evolutive co-simulation under magnetic control
      :img-top: workflow_pages/diagrams/evolutive_controller.svg
      :link: case-evolutive-controller
      :link-type: ref

      Forward, not inverse: TORAX and NICE step in lockstep while a PCSSP controller
      closes the coil-current loop.

Choosing one
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

Two caveats. ``evolutive_controller`` bootstraps from a completed
``inverse_convergence`` run **for the same shot**, so run that first. The two METIS
workflows build their own input from raw DINA at case-creation time, which makes
``pds-create-case`` noticeably slower for them.

Which shots work
----------------

Any shot in your ``$SCENARIOS_REPO`` can be tried with any workflow. A file in
``cases/overrides/`` is *not* a prerequisite -- it only exists for shots needing tuning
beyond the workflow's generic settings. So the two lists are worth separating:

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

Trust the CI column: those five combinations run end to end on every integration build
(``ci/run_test_workflows.sh``). Others may work and are simply not covered.

Input data requirements
-----------------------

All workflows need DDv4 input. The METIS workflows convert DINA data during
preprocessing if needed.

Anything running NICE also needs:

- ``equilibrium``, ``pf_active``, ``pf_passive``, ``iron_core`` and ``wall``
  IDSs, from a machine description.
- ``pf_active`` with exactly one element in the elements AoS per coil.
  Preprocessing generates this if needed.
- ``pf_active`` coil objects carrying resistance values.

Anything running METIS also needs:

- ``summary``, ``pulse_schedule``, ``equilibrium``, ``core_profiles`` (or
  ``plasma_profiles``) and ``core_sources`` (or ``plasma_sources``) IDSs.
- ``pulse_schedule`` filled. Preprocessing creates it from DINA data if needed. See the
  `METIS input documentation
  <https://github.com/IRFM/METIS/blob/main/doc/METIS_inputs_from_IMAS_IDSs.pdf>`_
  for what it expects.
