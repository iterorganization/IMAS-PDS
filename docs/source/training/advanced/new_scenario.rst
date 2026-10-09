.. _`training/new_scenario`:

Adding a new scenario
======================

Running a workflow on your own data
-------------------------------------

Every exercise so far ran against an existing shot prepared into ``scenarios/`` from a
pulse file (``cases/pulses/<shot>.yaml``), or the small training dataset. Adding your own
shot means writing a new pulse file, not copying and hand-editing a case: a case is a
generated, frozen snapshot, and the pulse file is the one place everything shot-specific
is declared (see :src:`cases/pulses/README.md` and :src:`cases/pulses/TEMPLATE.yaml`).

.. md-tab-set::

    .. md-tab-item:: Exercise

        Make a new pulse file for your own DINA/IMAS entry, prepare its data, and build a
        ``prescribed_transport`` case from it.

        #. **Copy the template** and name it after your shot (the case name, unless the
           pulse file sets ``case:``):

           .. code-block:: bash

               cp cases/pulses/TEMPLATE.yaml cases/pulses/<shot>.yaml

        #. **Fill it in.** At minimum: ``shot``, ``workflows`` (keep just
           ``prescribed_transport`` for this exercise), ``prepare.source`` (your IMAS
           entry), ``prepare.machine_description``, one of ``prepare.n_timeslices`` /
           ``prepare.dt_step``, and the simulated ``time.t_start``/``time.t_end``. Every
           key is commented in the template; the full reference is the module docstring
           of ``pds/configure.py``.
        #. **Prepare the data and build the case:**

           .. code-block:: bash

               bin/pds-configure cases/pulses/<shot>.yaml --prepare
               bin/pds-create-case prescribed_transport <shot>
               sbatch bin/pds-run-case.sbatch cases/prescribed_transport_<shot>

           ``bin/pds-configure cases/pulses/<shot>.yaml --explain`` prints every effective
           setting of the case with its origin -- use it to check what you wrote actually
           took effect before submitting.
        #. **Run the case and look at what it produced.** The validation plots in the run
           directory, and ``configuration.ymmsl`` to confirm your edits are what the run
           really used.

        .. note::

            Ensure that the input requirements for the different actors are met. These
            can be found in the actor's documentation. In this case, the NICE input requirements can be found
            in the `NICE documentation <https://blfauger.gitlabpages.inria.fr/nice/imasm3pds.html>`_.

