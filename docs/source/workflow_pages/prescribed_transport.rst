.. _`case-prescribed-transport`:
.. _`case-105078-prescribed`:
.. _`case-105084-prescribed`:
.. _`case-105092-prescribed`:
.. _`case-105099-prescribed`:

Prescribed transport
====================

Boundary-prescribed pulse design, solved once with NICE inverse. Available for DINA shots
105078, 105084, 105092 and 105099.

The plasma shape, the ``Ip``/``B0`` waveforms and the profile shapes (``p'`` and ``FF'``)
are all fixed up front by the scenario's ``waveforms_no_transport.yaml``. No transport
model runs, and NICE solves the free-boundary equilibrium independently per time slice, so
there is no time coupling and no outer iteration -- one pass and done.

:Workflow: ``prescribed_transport`` -- :src:`workflows/prescribed_transport/README.md`
:Scenario: DINA shots 105078, 105084, 105092, 105099, in ``pds-scenarios``
:Output: ``<run_dir>/out_nice``

The four cases are the same run against different scenario data: apart from the shot number
in their paths, the case files are identical, so there is nothing to tune per shot.

Running it
----------

.. code-block:: bash

   bin/pds-create-case prescribed_transport 105099
   sbatch bin/pds-run-case.sbatch cases/prescribed_transport_105099

Substitute another shot number to run one of the others. See
:ref:`running_cases` for what a case directory holds and where the output goes.

Coupling
--------

.. coupling-diagram:: workflows/prescribed_transport/workflow.ymmsl

   ``source`` seeds the equilibrium trace, the waveform editor applies the designed
   waveforms and the static machine description, ``equilibrium`` runs the inverse solve,
   and the sink writes the result.

``equilibrium`` is not a single program but the ``nice_inverse`` sub-model, which load
balances the per-slice solves over N NICE workers:

.. coupling-diagram:: workflows/prescribed_transport/workflow.ymmsl
   :model: nice_inverse

   The load balancer scatters slices to the workers and gathers the results back.

Workflow reference
------------------

``workflows/prescribed_transport/README.md``, included here so the two cannot drift apart.

.. include:: ../../../workflows/prescribed_transport/README.md
   :parser: myst_parser.sphinx_
