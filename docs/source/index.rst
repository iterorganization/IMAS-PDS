.. _`index`:

..
   Main "index". This will be converted to a landing index.html by sphinx. The
   toctrees are hidden: the theme renders them in the sidebar, and repeating them
   in the page body just duplicates the navigation.

===============
IMAS PDS Manual
===============

The **Pulse Design Simulator** couples the codes used to design an ITER pulse --
NICE for free-boundary equilibrium, TORAX and METIS for transport, the
Waveform-Editor for targets, PCSSP for magnetic control -- into simulations that
run as a single job, exchanging IMAS data through
`MUSCLE3 <https://muscle3.readthedocs.io/en/latest/>`_.

Getting started
---------------

.. code-block:: bash

  git clone https://github.com/iterorganization/IMAS-PDS.git
  cd IMAS-PDS

  module use /work/projects/pds/modules/all
  module load PDS

  bin/pds-create-case inverse_convergence 105073
  sbatch bin/pds-run-case.sbatch cases/inverse_convergence_105073

:ref:`installing` describes what the module sets up, :ref:`running_cases`, what a
case contains and where its output goes, and :ref:`workflows` which couplings are
available.

.. toctree::
   :caption: Getting Started
   :maxdepth: 2
   :hidden:

   self
   installing
   running_cases
   workflows
   troubleshooting

.. toctree::
   :caption: Developing PDS
   :maxdepth: 2
   :hidden:

   contributing
   local_install
   adding_workflows
   writing_actors
   documenting_actors
   code_style
   ci_config

.. toctree::
   :caption: Training
   :maxdepth: 1
   :hidden:

   training/intro
   training/advanced/intro

----

IMAS PDS is licensed under LGPL-3.0-or-later. The source is on
`GitHub <https://github.com/iterorganization/IMAS-PDS>`_.
