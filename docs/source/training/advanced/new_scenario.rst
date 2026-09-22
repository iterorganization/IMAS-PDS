.. _`training/new_scenario`:

Adding a new scenario
======================

Running a workflow on your own data
-------------------------------------

Every exercise so far ran against an existing shot in ``pds-scenarios`` or the small training
dataset. If you want to be able to run the PDS using your own scenarios, the following 
exercise will give you some pointers on how you can go about doing so.


.. md-tab-set::

    .. md-tab-item:: Exercise

        Take a ``prescribed_transport`` case, copy it, and make the copy run on data of your
        own our own IMAS entry.

        .. code-block:: bash

            bin/pds-create-case prescribed_transport 105084
            cp -r cases/prescribed_transport_105084 cases/prescribed_transport_custom

        From here it is yours to work out. In outline, what has to happen in the copy:

        #. **Find every place the old scenario is named.** A case is a frozen snapshot, so it
           holds literal, already-resolved paths in different files.
           Some of them point at the case's own ``config/``
           directory and still carry the old case name after the copy.
        #. **Repoint the data it reads.** Two DBEntries matter: the pulse data and the
           machine description. Both are named in ``workflow_settings.ymmsl``, and both are
           named again, under different setting names, in the waveform editor's config.
        #. **Run the case and look at what it produced** The validation plots in the run
           directory, and ``configuration.ymmsl`` to confirm your edits are what the run
           really used.

        .. note::

            Ensure that the input requirements for the different actors are met. These
            can be found in the actor's documentation. In this case, the NICE input requirements can be found
            in the `NICE documentation <https://blfauger.gitlabpages.inria.fr/nice/imasm3pds.html>`_.

