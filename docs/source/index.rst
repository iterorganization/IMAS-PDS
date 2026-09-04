.. _`index`:

..
   Main "index". This will be converted to a landing index.html by sphinx. The
   toctrees are hidden: the theme renders them in the sidebar, and repeating them
   in the page body just duplicates the navigation.

===============
IMAS PDS Manual
===============

The **Pulse Design Simulator** couples multiple different codes used to design a pulse, exchanging IMAS data through `MUSCLE3 <https://muscle3.readthedocs.io/en/latest/>`_.

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

Related documentation
---------------------

PDS couples different codes, so most of what you will
need to read is maintained elsewhere. Below is an overview of what each tool does here, and where its
own documentation and training live.

MUSCLE3 and coupling
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 22 40 38

   * - Module
     - Role in PDS
     - Documentation
   * - ``IMAS-MUSCLE3``
     - Collection of helper actors and for working with IMAS data in MUSCLE3 simulations.
     - `Documentation <https://imas-muscle3.readthedocs.io/en/latest/>`__,
       `Training <https://imas-muscle3.readthedocs.io/en/latest/training.html>`__
   * - ``MUSCLE3``
     - The coupling framework itself: it starts the actors, connects their ports and
       carries the messages between them.
     - `Documentation <https://muscle3.readthedocs.io/en/latest/>`__,
       `Training <https://esciencecenter-digital-skills.github.io/lesson-model-coupling/index.html>`__
   * - ``yMMSL``
     - The file format a workflow is written in.
     - `Documentation <https://ymmsl-python.readthedocs.io/en/latest/>`__
   * - ``MUSCLE3 dashboard``
     - Follows a running MUSCLE3 workflow live, and shows the recorder plots.
     - `Repository <https://github.com/multiscale/muscle3-dashboard>`__
   * - ``ymmsl2svg``
     - Renders a MUSCLE3 workflow's coupling graph as SVG.
     - `Repository <https://github.com/multiscale/ymmsl2svg>`__

IMAS and data
^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 22 40 38

   * - Module
     - Role in PDS
     - Documentation
   * - ``IMAS Data Dictionary``
     - The data model itself: which IDSs exist and what is in them.
     - `Documentation <https://imas-data-dictionary.readthedocs.io/en/latest/>`__
   * - ``IMAS-Python``
     - Reading and writing the IMAS data that flows between the actors using Python.
     - `Documentation <https://imas-python.readthedocs.io/en/latest/>`__,
       `Training <https://imas-python.readthedocs.io/en/latest/courses/basic_user_training.html>`__
   * - ``IMAS-Validator``
     - Rule-based checks on IDS contents; PDS uses it for the operational limit checks.
     - `Documentation <https://imas-validator.readthedocs.io/en/latest/index.html>`__,
       `Training <https://imas-validator.readthedocs.io/en/latest/courses/basic_user_training.html>`__

Physics codes and pulse design
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 22 40 38

   * - Module
     - Role in PDS
     - Documentation
   * - ``NICE``
     - Free-boundary equilibrium, in inverse, direct and evolutive (resistive
       diffusion) mode.
     - `Documentation <https://blfauger.gitlabpages.inria.fr/nice/>`__
   * - ``TORAX``
     - A core transport solver.
     - `Documentation <https://torax.readthedocs.io/en/latest/>`__
   * - ``TORAX-MUSCLE3``
     - The MUSCLE3 actor wrapping TORAX, with its IMAS couplings.
     - `Documentation <https://torax-muscle3.readthedocs.io/en/latest/>`__
   * - ``METIS-IRFM``
     - Fast integrated transport that does a whole pulse on its own.
     - `Repository <https://git.iter.org/projects/SCEN/repos/metis>`__ (ITER internal),
       `Documentation <https://github.com/IRFM/METIS/blob/main/doc/METIS_inputs_from_IMAS_IDSs.pdf>`__
   * - ``Waveform-Editor``
     - Turns a ``waveforms.yaml`` into the target waveforms the solvers are driven
       with, and carries the machine description.
     - `Documentation <https://waveform-editor.readthedocs.io/en/latest/>`__,
       `Training <https://waveform-editor.readthedocs.io/en/latest/training/training.html>`__
   * - ``PCS``
     - The PCSSP magnetic controller (MATLAB/Simulink).
     - `Repository <https://git.iter.org/projects/PCS/repos/pcs>`__ (ITER internal)
   * - ``CHEASE``
     - Fixed-boundary equilibrium.
     - `Repository <https://gitlab.epfl.ch/spc/chease>`__

New to all of this? The trainings are the fastest way in: start with the
:ref:`PDS training <training/intro>`.

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
