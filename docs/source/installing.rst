.. _`installing`:

Installing PDS
==============

PDS orchestrates existing simulation codes -- NICE, TORAX, METIS, the
Waveform-Editor, PCS -- through MUSCLE3. It has no build of its own. Each code is
a separate EasyBuild module that MUSCLE3 loads when it spawns that actor, and the
``PDS`` meta-module wires a checkout into the environment. Installation is
therefore a clone and one module load: nothing to compile, and no
``pip install -e .`` step.

.. note::

   This page assumes access to the ITER cluster, where the module stack is
   published at ``/work/projects/pds/modules/all``. Without it you have to build
   the tools yourself -- see :ref:`local_install`.

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

  cd /path/to/pds

  module use /work/projects/pds/modules/all
  module load PDS

The module resolves the checkout in two steps: an exported ``PDS_REPO`` takes
precedence, and otherwise the current directory is used if it is a PDS checkout.
Loading the module from inside the checkout satisfies the second case, so no
variables need setting.

If neither applies, the load fails with ``PDS: could not determine which PDS
checkout to use``. Every path the module sets is relative to the checkout, so it
reports the error rather than guessing. See :ref:`troubleshooting`.

Set the variables explicitly where the defaults do not apply:

.. code-block:: bash

  # load the module without being in the checkout
  export PDS_REPO=/path/to/pds

  # use your own scenarios checkout rather than the published copy
  export SCENARIOS_REPO=/path/to/pds-scenarios

``PDS_REPO`` must be exported *before* the module load, since that is when it is
read. ``SCENARIOS_REPO`` is read later, by ``pds-create-case`` and
``pds-run-case.sbatch``, so it can be set at any point before you create a case.

What the module does
--------------------

``PDS`` is a meta-module: it installs nothing itself. It pulls in IMAS-Python,
IMAS-MUSCLE3 and ymmsl2svg as dependencies, and then sets up your checkout:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Variable
     - Effect
   * - ``PDS_REPO``
     - Set to the resolved checkout. Workflow settings and the ``bin/`` scripts
       all resolve paths from it.
   * - ``PATH``
     - Gains ``$PDS_REPO/bin``, so ``pds-create-case`` is on your path.
   * - ``PYTHONPATH``
     - Gains ``$PDS_REPO``, so ``import pds`` works with no install step.
   * - ``YMMSL_PATH``
     - Gains ``$PDS_REPO/workflows``, which is what lets a workflow resolve
       ``from lib.easybuild_programs import ...``.
   * - ``IMAS_VERSION``
     - Set to ``4.0.0``.
   * - ``MPLBACKEND``
     - Unset, so actors that plot pick their own backend.
   * - stack limit
     - ``ulimit -s unlimited``, which several of the Fortran actors need.

The tool stack
--------------

Only the first three are dependencies of ``PDS``. The rest are loaded by MUSCLE3
when it starts the actor that needs them, which is why loading ``PDS`` is enough
to run a workflow that uses any of them.

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
  command -v muscle_manager   # should resolve inside the IMAS-MUSCLE3 module
  echo $PDS_REPO              # should be your checkout

For an end-to-end check, run one of the single-actor smoke tests. These need no
scenario data and finish in seconds:

.. code-block:: bash

  bash setup_files/setup_test_files.sh
  muscle_manager --start-all ymmsl_files/test_sink_source_actor.ymmsl

``setup_files/setup_test_files.sh`` generates the runnable ``.ymmsl`` files from
the templates in ``ymmsl_files/``, filling in the path to your checkout. Run it
once after cloning, and again whenever you move the checkout.

Then continue with :ref:`running_cases`.

Building the module stack yourself
----------------------------------

If you need a tool built from a branch, or you are working somewhere the
published stack is not available, ``setup_files/easyconfigs/build.sh`` builds the
whole stack from the easyconfigs in this repository:

.. code-block:: bash

  module load EasyBuild/5.4.0
  bash setup_files/easyconfigs/build.sh              # everything not already installed
  bash setup_files/easyconfigs/build.sh NICE CHEASE  # or just these

It installs into ``$EASYBUILD_PREFIX`` (default ``$HOME/public``), so point
``module use`` at that instead. Building a single tool from your own branch, and
the from-source alternative, are covered in :ref:`local_install`.
