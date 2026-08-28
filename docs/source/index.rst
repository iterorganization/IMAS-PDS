.. _`index`:

..
   Main "index". This will be converted to a landing index.html by sphinx. We
   define TOC here, but it'll be put in the sidebar by the theme

===============
IMAS PDS Manual
===============

The **Pulse Design Simulator** couples the codes used to design an ITER pulse --
NICE for free-boundary equilibrium, TORAX and METIS for transport, the
Waveform-Editor for targets, PCSSP for magnetic control -- into simulations that
run as a single job, exchanging IMAS data through
`MUSCLE3 <https://muscle3.readthedocs.io/en/latest/>`_.

PDS itself builds nothing. Each code is a separate EasyBuild module that MUSCLE3
loads when it starts that actor, and this repository holds the couplings: which
codes talk to each other, over which ports, in what order. Those couplings are
*workflows*; pairing one with a shot's data gives you a *case*, which is what you
run.

Getting started
---------------

.. code-block:: bash

  cd /path/to/pds

  module use /work/projects/pds/modules/all
  module load PDS

  bin/pds-create-case inverse_convergence 105073
  sbatch bin/pds-run-case.sbatch cases/inverse_convergence_105073

That is the whole user path -- no environment to set up, as long as you load the
module from inside the checkout. :ref:`installing` explains what the module sets
up, :ref:`running_cases` what a case is and where its output goes, and
:ref:`workflows` which couplings are available.

.. toctree::
   :caption: Getting Started
   :maxdepth: 2

   self
   installing
   running_cases
   workflows
   troubleshooting

.. toctree::
   :caption: Developing PDS
   :maxdepth: 2

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

   courses/basic_user_training

Sitemap
-------

* :ref:`genindex`
* :ref:`search`

----

IMAS PDS is licensed under LGPL-3.0-or-later. The source is on
`GitHub <https://github.com/iterorganization/IMAS-PDS>`_.
