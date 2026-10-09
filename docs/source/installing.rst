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
- Nothing else to check out for the shot data: it is prepared into this checkout's
  ``scenarios/`` directory (``SCENARIOS_REPO``, the default when the variable is unset)
  by :src:`preprocessing/prepare`, driven by ``bin/pds-configure cases/pulses/<shot>.yaml
  --prepare`` -- see :src:`cases/pulses/README.md`. Point ``SCENARIOS_REPO`` elsewhere to
  use another data root instead.

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

