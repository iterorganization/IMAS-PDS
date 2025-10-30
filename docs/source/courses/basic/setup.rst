.. _`basic/setup`:

PDS 101: Setup
==============

For these training exercises you will need an installation of the PDS repo and access to IMAS-Python.
The training material currently expects the user to be on SDCC.
You will need read access to the repositories:

- `IMAS-MUSCLE3 <https://github.com/iterorganization/IMAS-muscle3>`_
- `NICE <https://gitlab.inria.fr/blfauger/nice>`_
- `TORAX <https://github.com/google-deepmind/torax>`_
- `WAVEFORM-EDITOR <https://github.com/iterorganization/Waveform-Editor>`_


.. code-block:: console

    git clone ssh://git@git.iter.org/scen/pds.git
    cd pds

    # a setup script is provided with an installation of the necessary repositories.
    # make sure you have access rights to all the relevant codes.
    # expects to be run from the repo root directory
    . pds_setup.sh
    # load a base environment with the necessary modules for the PDS workflows.
    # some actors currently require a specific virtual environment, this will be taken
    # into account in the workflow configurations
    source run/imas_base_env

For this training you will need access to a graphical environment to visualize
the simulation results. If you are on SDCC, it is recommended to follow this training
through the NoMachine client, and using chrome as your default browser (there have been
issues when using firefox through NoMachine).

