.. _`troubleshooting`:

Troubleshooting
===============

Several of these are silent: the run completes, and the result is wrong or slow rather
than absent.

``PDS: could not determine which PDS checkout to use``
------------------------------------------------------

``module load PDS`` could not work out which checkout to wire in: it looks at
``$PDS_REPO`` first, then your current directory. Do one of:

.. code-block:: bash

  export PDS_REPO=/path/to/pds && module load PDS
  # or
  cd /path/to/pds && module load PDS

Every path the module sets is relative to the checkout, so it errors rather than
guessing and writing run output somewhere unexpected.

``PDS_REPO=... is not a PDS checkout``
--------------------------------------

``$PDS_REPO`` is set but is not a PDS clone -- usually a typo, or a stale export from a
checkout since moved or deleted. Check with ``ls $PDS_REPO/bin``.

``Failed to find a file lib/easybuild_programs.ymmsl``
------------------------------------------------------

A workflow's ``imports:`` cannot resolve because ``YMMSL_PATH`` does not include
``$PDS_REPO/workflows``. Both the PDS module and ``bin/pds-run-case.sbatch`` set it, so
this generally only appears when invoking ``muscle_manager`` by hand:

.. code-block:: bash

  export YMMSL_PATH=$PDS_REPO/workflows

``Instance already has a directory``
------------------------------------

A leftover ``instances/`` directory from a previous run. ``bin/pds-run-case.sbatch``
clears the run directory each time, so this only bites hand-rolled ``muscle_manager``
invocations. Remove the run directory, or pass a fresh ``--run-dir``.

``IMAS-MUSCLE3/... not loaded and could not be loaded automatically``
---------------------------------------------------------------------

``pds-run-case.sbatch`` tried to load the module stack itself and could not. Load it
first:

.. code-block:: bash

  module use /work/projects/pds/modules/all
  module load PDS

On a compute node that has never seen that module path, Lmod's cache may not know about
it. Add ``--ignore_cache``:

.. code-block:: bash

  module --ignore_cache load PDS

This is why ``ci/run_test_workflows.sh`` uses ``--ignore_cache`` unconditionally.

The run is far slower than it should be
---------------------------------------

Most likely a ``resources`` key that matches nothing. Resources are looked up by
**exact** match on ``<root model>.<instance>``, whereas settings are matched by walking
instance prefixes. A resources key matching nothing is not an error -- that component
silently gets one thread.

.. code-block:: bash

  uv run python ci/check_ymmsl.py

That rejects both this and settings keys at the wrong depth. :ref:`running_cases`
explains the difference between the two key forms.

A setting appears to be ignored
-------------------------------

Read ``configuration.ymmsl`` in the run directory: the fully resolved configuration
that actually executed, after all the stacking, showing which value won. ``input/`` next
to it holds the ymmsl files exactly as they were passed.

The stacking order is ``workflow.ymmsl``, ``workflow_settings.ymmsl``,
``scenario_settings.ymmsl``, ``preprocess_settings.ymmsl``, then any command-line
overlays. The last value for a key wins.

HDF5 errors on networked storage
--------------------------------

Spurious file-locking failures when the run directory is on networked storage:

.. code-block:: bash

  export HDF5_USE_FILE_LOCKING=FALSE

``ci/run_test_workflows.sh`` sets this for the same reason.

A case does not pick up a change I made
---------------------------------------

A case is a frozen snapshot, so editing ``workflows/`` afterwards does not affect one
already created. Recreate it:

.. code-block:: bash

  bin/pds-create-case <workflow> <shot>

This **deletes and rebuilds** the case directory, so anything edited inside it is lost.
For a one-off change, stack an overlay file on the ``sbatch`` line instead.
