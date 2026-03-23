.. _`basic/setup`:

PDS Setup
=========

For these training exercises you will need an installation of the PDS repository and access to IMAS-Python.
The training material currently expects the user to be on SDCC.
You will need read access to the repositories:

- `IMAS-MUSCLE3 <https://github.com/iterorganization/IMAS-MUSCLE3>`_
- `NICE <https://gitlab.inria.fr/blfauger/nice>`_
- `TORAX <https://github.com/google-deepmind/torax>`_
- `WAVEFORM-EDITOR <https://github.com/iterorganization/Waveform-Editor>`_

First clone the project.

A setup script ``pds_setup.sh`` is provided with an installation of the necessary repositories.
The script expects to be run from the repo root directory
Make sure you have access rights to all the relevant codes.
The setup script will detect if codes are not yet available and install the missing ones.
It is also configurable to enable or disable the installation of specific codes. 
In case the installed codes are outdated, you can either update them by hand in the ``run/`` folder
or remove directories from the ``run/`` folder and run the setup script again.

Load a base environment ``run/imas_base_env`` with the necessary modules for the PDS workflows.
Some actors currently require a specific virtual environment, this will be taken into account in the workflow configurations.

.. code-block:: console

    git clone ssh://git@git.iter.org/scen/pds.git
    cd pds
    bash pds_setup.sh
    source run/imas_base_env

For this training you will need access to a graphical environment to visualize
the simulation results. If you are on SDCC, it is recommended to follow this training
through the NoMachine client, and using chrome as your default browser (there have been
issues when using firefox through NoMachine).
