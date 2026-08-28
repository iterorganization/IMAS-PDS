.. _`local_install`:

Local (developer) install
=========================

.. warning::

   **Developers only.** If you are running PDS on the ITER cluster, use
   :ref:`installing` instead -- ``module load PDS`` gives you the whole stack
   with nothing to build.

When you need this
------------------

Building from source is worth the trouble in three situations:

- You are changing one of the coupled codes and need your working copy in the
  loop, not a released module.
- You are bisecting an upstream bug and need arbitrary revisions.
- You are working somewhere ``/work/projects/pds/modules/all`` is not published.

For the first two, consider :ref:`building a single EasyBuild module
<local-install-own-module>` instead. It is usually less work than a full
from-source build and it keeps the rest of the stack on the published modules.

pds_setup.sh
------------

``pds_setup.sh`` at the repository root is the entry point. Read it before you
run it -- it says so itself:

  This is only a means to guide users in the right way, not a maintained
  install script.

Every ``INSTALL_*`` flag at the top of the file ships set to ``"false"``, so
running it as committed does nothing. Turn on the components you actually need
and set the matching ``BRANCH_*`` variable:

.. code-block:: bash

  INSTALL_NICE="true"
  BRANCH_NICE="master"

Then:

.. code-block:: bash

  bash pds_setup.sh

It must be run, not sourced. Each step checks that the remote is reachable
before it starts, so components you have no access to are skipped rather than
failing the run.

The per-tool scripts
--------------------

``pds_setup.sh`` is a thin driver over the scripts in ``setup_files/``. You can
run any of them directly, from inside ``run/``. Each clones its tool and builds
it into ``run/<Tool>/``:

.. list-table::
   :header-rows: 1
   :widths: 34 20 46

   * - Script
     - Produces
     - Notes
   * - ``setup_imas_muscle3.sh``
     - ``run/IMAS-MUSCLE3/venv``
     - Editable install, plus ymmsl2svg.
   * - ``setup_muscle3.sh``
     - ``run/tmp/muscle3-0.10.0-intel/``
     - The MUSCLE3 **C++** library NICE links against. No module is published
       for 0.10.0, so this writes an env wrapper pointing at the site install.
   * - ``setup_nice.sh``
     - ``run/nice/run/nice_imas_*_muscle3``
     - The heaviest build. Requires ``setup_muscle3.sh`` to have run first.
   * - ``setup_torax.sh``
     - ``run/TORAX-MUSCLE3/venv``
     - Force-installs ``muscle3==0.10.0`` over the package's own pin, to match
       the manager.
   * - ``setup_metis.sh``
     - ``run/metis/``
     - MATLAB, no venv. Source is ssh-gated on ``git.iter.org``.
   * - ``setup_chease.sh``
     - ``run/chease/chease_m3/``
     - Builds through ``iwrap``.
   * - ``setup_pcs.sh``
     - ``run/pcs/``, ``run/pcs/pcssp/``
     - Clone only, no build. Also ssh-gated.
   * - ``setup_waveform_editor.sh``
     - ``run/Waveform-Editor/venv``
     - Installs the ``[muscle3]`` extra.
   * - ``setup_muscle3_dashboard.sh``
     - ``run/muscle3-dashboard/venv``
     - Optional; live view of a running coupling.

.. important::

   Order matters in one place: ``setup_muscle3.sh`` must run **before**
   ``setup_nice.sh``. NICE's binaries link against the MUSCLE3 C++ library and
   the build fails without it. ``pds_setup.sh`` already sequences this, which is
   the main reason to use it rather than calling the scripts yourself.

METIS and PCS clone over ``ssh://git@git.iter.org``, so you need working SSH
credentials for those two. The others are public.

Pointing a workflow at your build
---------------------------------

Building the tools is only half of it -- a workflow still has to be told to use
them. Program definitions live in two files:

``workflows/lib/easybuild_programs.ymmsl``
  Each program is an EasyBuild module plus an executable. **All five workflows
  import from here.**

``workflows/lib/local_programs.ymmsl``
  The same programs, defined as shell scripts that activate the corresponding
  ``run/<Tool>/venv``. This is the from-source counterpart, and it currently has
  no users in the tree.

So to run against your build, repoint the import in the workflow:

.. code-block:: yaml

  imports:
  - from lib.local_programs import implementation nice_inv

Both files resolve because the PDS module puts ``$PDS_REPO/workflows`` on
``YMMSL_PATH``; ``bin/pds-run-case.sbatch`` sets it too.

.. note::

   The local definitions use ``script:`` rather than the declarative
   ``executable``/``args`` form. ``base_env: clean`` runs ``module purge``, which strips ``$PDS_REPO``; and
   ``executable``/``args`` are expanded in the actor's own shell *after* that
   purge, so they would silently resolve to ``/workflows/...`` with an empty
   prefix. ``export`` lines inside a ``script:`` are expanded in the actor's
   shell, where ``$PDS_REPO`` still exists.

.. _`local-install-own-module`:

Building your own EasyBuild module
----------------------------------

Usually the better option: build the one tool you are changing as a module, and
leave everything else on the published stack.

.. code-block:: bash

  cd setup_files/easyconfigs/n/NICE
  cp NICE-3.0.0.dev258-intel-2025b-pds.eb NICE-mybranch-intel-2025b-pds.eb
  # edit the new file to point at your branch

  export EASYBUILD_PREFIX=$HOME/my-modules
  module load EasyBuild/5.4.0
  eb NICE-mybranch-intel-2025b-pds.eb --robot="$PWD"

  module use $HOME/my-modules/modules/all

Then point one implementation at it without disturbing the others: copy
``workflows/lib/local_programs.ymmsl`` to
``workflows/lib/local_programs_<you>.ymmsl``, change that actor's ``modules:``
line to your new module, and import just that one implementation from your copy:

.. code-block:: yaml

  imports:
  - from lib.easybuild_programs import implementation torax
  - from lib.local_programs_<you> import implementation nice_inv

METIS patches
-------------

``workflows/lib/metis_patches/`` holds MATLAB patches against METIS's
``metis4muscle3`` interface. They are not applied by any script -- if you are
building METIS from source and need them, apply them by hand against your
``run/metis`` checkout.
