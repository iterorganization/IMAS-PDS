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

Each actor is built once into a shared ``PDS-<Name>`` module by its own ``build_*.sh``
script in ``setup_files/custom_modules/``. Loading the PDS meta-module (``module load PDS``)
sets up IMAS-Python and PDS-IMAS-MUSCLE3; each workflow actor then loads its own
``PDS-<Name>`` module itself when MUSCLE3 spawns it. Either way, there is nothing to
install per-checkout. Some actors require a specific virtual environment; this is already
taken care of by each actor's own module.

.. code-block:: console

    git clone https://github.com/iterorganization/IMAS-PDS.git
    cd IMAS-PDS
    module use /home/ITER/blokhus/public/modules  # or wherever PDS.lua was deployed
    module load PDS

For this training you will need access to a graphical environment to visualize
the simulation results. If you are on SDCC, it is recommended to follow this training
through the NoMachine client, and using chrome as your default browser (there have been
issues when using firefox through NoMachine).
