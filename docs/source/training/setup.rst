.. _`training/setup`:

Setting up the PDS
==================

For these training exercises you will need an installation of the PDS repository. 
The `PDS repository <https://github.com/iterorganization/IMAS-PDS>`_ is publicly available on GitHub. 
As a first step, let's clone it.

.. code-block:: bash

    git clone https://github.com/iterorganization/IMAS-PDS.git
    cd IMAS-PDS

On SDCC, Easybuild modules are made available which can be used to run the exercises in
this training. The PDS modules live in a shared folder that SDCC does not look in by default, 
so you first point it there. 

.. code-block:: bash

    module use /work/projects/pds/modules/all

That same folder also holds custom PDS builds of the simulation codes the PDS workflows use.
You normally do not load these yourself, each workflow states which modules its actors
need and loads them for you when it runs.

You can run the following to see which PDS modules are available:

.. code-block:: bash

    module avail

Look at the available modules under the ``/work/projects/pds/modules/all`` section.
Which modules are available? You can recognise them by the ``-pds`` at the end of their name.


As a first step, let's load the PDS module:

.. code-block:: bash

    module load PDS

Lastly, we will use some of the test workflows as examples during this training, so let's quickly 
set these up as well:

.. code-block:: bash

    bash setup_files/setup_test_files.sh

Now we are all set up to run a PDS workflow!

