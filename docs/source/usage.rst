.. _`usage`:

Using the IMAS PDS
==================

Setting up actors
-----------------
Each actor (IMAS-MUSCLE3, NICE, METIS-IRFM, TORAX-MUSCLE3, Waveform-Editor, PCS, ...) is an
EasyBuild module, built once with ``setup_files/easyconfigs/build.sh``. Loading the PDS
meta-module (``module load PDS``) sets up IMAS-Python and IMAS-MUSCLE3; each workflow actor
then loads its own module itself when MUSCLE3 spawns it. Either way, there is nothing to
install per-checkout.

Most of these come straight from upstream easyconfigs -- see
``setup_files/easyconfigs/README.md`` for which ones, and why a handful are still built here.

.. code-block:: bash

  module use /home/ITER/dejongy/projects/modules/all  # or wherever build.sh installed it
  module load PDS


Test workflows
--------------

Test workflows can be run to check if everything is working as expected.
These workflows can be used as a template for your own workflows.

.. code-block:: bash

  # generate runnable .ymmsl files from the .template sources
  bash setup_files/setup_test_files.sh
  module use /home/ITER/dejongy/projects/modules/all
  module load PDS
  # run test workflow of choice
  muscle_manager --start-all ymmsl_files/test_sink_source_actor.ymmsl

Example cases
-------------

A run pairs a **workflow** -- how something is simulated, in ``workflows/`` -- with a
**scenario** -- what is simulated, in the separate ``pds-scenarios`` repository. That
pairing is a **case**, in ``cases/``, and the case is the only file you pass to the manager.

.. code-block:: bash

  module use /home/ITER/dejongy/projects/modules/all
  module load PDS

  export PDS_REPO=/path/to/pds
  export SCENARIOS_REPO=/path/to/pds-scenarios
  export YMMSL_PATH=$PDS_REPO/workflows

  muscle_manager --start-all $PDS_REPO/cases/105084_prescribed.ymmsl

To change something for a single run, put it in a second file and stack it after the case.
The last value given for a key wins:

.. code-block:: bash

  muscle_manager --start-all $PDS_REPO/cases/105084_prescribed.ymmsl ./cold-start.ymmsl

The run directory receives ``input/``, holding the yMMSL files exactly as passed, and
``configuration.ymmsl``, the fully resolved configuration that was executed.

Sink outputs land directly in the run directory, ``<run_dir>/<name>``. Relative IMAS URIs
resolve against the instance's own work directory (``<run_dir>/instances/<sink>/workdir``),
so the cases write to ``../../../<name>`` to climb back out to the run directory.

Setting keys and resources keys are written differently, which is worth knowing before you
edit a case. Settings are matched by walking instance prefixes, so the short instance name
is enough (``solve.nice.xml_path``). Resources are looked up by exact match, and the key
must start with the root model name -- which for a case that imports its workflow is the
full dotted import path
(``prescribed_transport.workflow.prescribed_transport.solve.nice``). A resources key that
matches nothing is not an error: that component silently gets one thread.
``ci/check_ymmsl.py`` rejects both mistakes.

Two unmerged upstream patches are required; ``setup_files/apply_patches.sh`` applies and
verifies them.

Legacy path
~~~~~~~~~~~

The four ``metis_*_from_dina`` workflows have not been migrated and still use
``run_workflow.sh`` with a scenario from ``workflows/<workflow>/scenarios/``:

.. code-block:: bash

  source completion.sh    # tab completion for workflows and scenarios
  bash run_workflow.sh metis_interpretative_from_dina 105084
