.. _`basic/setup`:

PDS 101: setup
==============

For these training exercises you will need an installation of the PDS repo and access to IMAS-Python.

.. code-block:: console

    git clone ssh://git@git.iter.org/scen/pds.git
    cd pds

    # a setup script is provided with an installation of the necessary repositories.
    # make sure you have access rights to all the relevant codes.
    # expects to be run from the repo root directory
    . pds_setup.sh
    source run/imas_base_env
