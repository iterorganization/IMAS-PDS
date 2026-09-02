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

The tool stack
--------------

Only the first three are dependencies of ``PDS``. MUSCLE3 loads the rest when it starts
the actor that needs them, which is why loading ``PDS`` is enough to run a workflow
using any of them.

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Module
     - Role
   * - ``IMAS-Python``
     - Reading and writing IMAS data.
   * - ``IMAS-MUSCLE3``
     - The MUSCLE3 manager plus the generic actors (source, sink, recorder,
       validator, ...).
   * - ``ymmsl2svg``
     - Renders a workflow's coupling graph as SVG.
   * - ``NICE``
     - Free-boundary equilibrium: inverse, direct and evolutive solvers.
   * - ``TORAX-MUSCLE3``
     - Core transport.
   * - ``METIS-IRFM``
     - Fast integrated transport, driven through MATLAB.
   * - ``Waveform-Editor``
     - Turns a ``waveforms.yaml`` into the target waveforms sent to the solvers.
   * - ``PCS``
     - The PCSSP magnetic controller, MATLAB/Simulink.
   * - ``CHEASE``
     - Fixed-boundary equilibrium.
   * - ``IMAS-Validator``
     - Rule-based checks on IDS contents.

Verifying the install
---------------------

.. code-block:: bash

  module list                 # PDS and its dependencies should be listed
  m3dash                      # Should print help of the muscle3 dashboard
  echo $PDS_REPO              # should be your checkout

Then continue with :ref:`running_cases`.

