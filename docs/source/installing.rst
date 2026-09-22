.. _`installing`:

Installing PDS
==============

.. note::

   This page assumes the ITER cluster, where the module stack is published at
   ``/work/projects/pds/modules/all``. Without it you have to build the tools
   yourself -- see :ref:`local_install`.

Requirements
------------

- An account on the ITER cluster, with read access to ``/work/projects/pds``.
- A checkout of this repository.
- The separate ``pds-scenarios`` repository, which holds the shot data. A copy is
  published at ``/work/projects/pds/pds-scenarios``, which is the default when
  ``SCENARIOS_REPO`` is unset. A private checkout is only needed to override it.

Loading the module
------------------

.. code-block:: bash

  git clone https://github.com/iterorganization/IMAS-PDS.git
  cd IMAS-PDS

  module use /work/projects/pds/modules/all
  module load PDS

Verifying the install
---------------------

.. code-block:: bash

  module list                 # PDS and its dependencies should be listed
  m3dash                      # Should print help of the muscle3 dashboard
  echo $PDS_REPO              # should be your checkout

Then continue with :ref:`running_cases`.

