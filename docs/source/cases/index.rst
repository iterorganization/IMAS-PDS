.. _`cases`:

============
Case gallery
============

A run pairs a **workflow** -- how something is simulated, in ``workflows/`` -- with a
**scenario** -- what is simulated, in the separate ``pds-scenarios`` repository. That
pairing is a **case**, in ``cases/``, and the case is the only file you pass to the
manager. See :ref:`running_cases` for how to create and submit one, and
:ref:`workflows` for the comparison table and the input-data requirements.

Each coupling below is drawn from its own ``workflow.ymmsl`` at build time, so the
diagrams cannot drift from the couplings they document.

.. grid:: 1 2 3 3
   :gutter: 2

   .. grid-item-card:: Prescribed transport
      :img-top: diagrams/prescribed_transport.svg
      :link: case-prescribed-transport
      :link-type: ref

      A single NICE inverse solve against a boundary that is fixed up front. Transport is
      not solved at all, and each time slice is independent, so there is no outer loop.

   .. grid-item-card:: Inverse convergence against TORAX
      :img-top: diagrams/inverse_convergence.svg
      :link: case-inverse-convergence
      :link-type: ref

      An outer loop alternating NICE free-boundary inverse equilibrium and TORAX transport
      until the coil currents stop moving, with an ``imas-validator`` pass over the
      converged coil currents.

   .. grid-item-card:: METIS with a NICE inverse solve
      :img-top: diagrams/metis_nice_inverse.svg
      :link: case-metis-nice-inverse
      :link-type: ref

      METIS transport from DINA input, then a single NICE inverse pass fitting coil
      currents to the equilibrium it produced. No outer loop.

   .. grid-item-card:: Evolutive co-simulation under magnetic control
      :img-top: diagrams/evolutive_controller.svg
      :link: case-evolutive-controller
      :link-type: ref

      Forward, not inverse: TORAX and NICE step together in lockstep while a PCSSP
      controller closes the coil-current loop.

.. toctree::
   :hidden:

   prescribed_transport
   inverse_convergence
   metis_nice_inverse
   evolutive_controller
