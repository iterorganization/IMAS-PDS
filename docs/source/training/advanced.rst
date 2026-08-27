.. _`training/advanced`:

Advanced: Building your own workflows
=====================================

Building your own workflows
---------------------------

In this section we explore building our own muscle3 workflow step by step.
If needed, make sure to refresh your knowledge on `MUSCLE3 <https://muscle3.readthedocs.io/en/latest/>`_.
It is recommended to do these exercises in the ``cases`` directory or make your own directory.
These exercises are mostly relevant for developers.

.. code-block:: bash

    module use /work/projects/pds/modules/all  # or wherever build.sh installed it
    module load PDS
    module load IDStools

Exercise 1
----------

We start with the simplest workflow; loading IDS data, sending it to another actor and saving the data. 
The workflow and data is prepared for showcasing the different actors and is not indended to lead to a fully physical solution.

A small custom IDS has been prepared on SDCC so that the workflow is fast and iterative development is easy. 
You can swap this out with your own data, although it is advised to go through the exercises with the custom data first.

The URI of the prepared training data is as follows (note: you will need to update the path to your local PDS install): 

.. code-block::

    imas:hdf5?path=<pds root>/training_data/training_ids


For more information on the sink and source actors read the `IMAS-MUSCLE3 docs <https://imas-muscle3.readthedocs.io/en/latest/usage.html>`_.

.. note::
    MUSCLE3 uses the locally set environment variables by default.
    ``base_env: clean`` discards them and gives the actor a purged environment instead, into
    which MUSCLE3 loads exactly the modules listed under ``modules:`` -- so that list is the
    actor's complete environment. Name the module with its full version, as below; a bare name
    could resolve to a different build of the same code.
    An example for the source actor from the IMAS-MUSCLE3 code is shown below.

    .. code-block:: yaml

        implementations:
        source:
            base_env: clean
            modules: IMAS-MUSCLE3/1.0.0-intel-2025b-pds
            executable: python
            args: "-u -m imas_muscle3.actors.source_component"

    As explained in :ref:`training/setup`, an actor implementation can point at either an
    EasyBuild module or a local installation. For a local installation you instead point at the
    virtual environment ``pds_setup.sh`` created for it, replacing the ``base_env`` and
    ``modules`` lines with ``virtual_env: $PDS_REPO/run/IMAS-MUSCLE3/venv``.

    The premade workflows already set this correctly per actor (see
    ``workflows/lib/easybuild_programs.ymmsl`` and ``workflows/lib/local_programs.ymmsl``);
    you'll only need to write it out by hand like this when defining a new implementation
    for your own workflow.

.. tip::
   The solution yMMSL files for all exercises, containing the correct relative paths 
   have been made available in the
   ``pds/ymmsl_files/training`` directory. It is recommended to attempt the
   exercises yourself first. If you get stuck, you can try running the provided 
   solution yMMSL files and see if you understand how they are implemented.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Copy the file at ``ymmsl_files/training/source_sink.ymmsl`` to your running directory, most likely the ``cases`` directory.
        This is a workflow connecting a data source actor to a data sink actor. 
        This will be your starting point for this section of the exercises. We will gradually expand it by adding new MUSCLE3 actors every exercise.
        Ensure the equilibrium IDS from the URI shown above will be sent.
        Run it using the muscle-manager and check if the input equilibrium IDS is the same as the output IDS.

        To check whether the two IDSs are identical, you can use the python function ``imas.util.idsdiff()`` (`IMAS-PYTHON docs <https://imas-python.readthedocs.io/en/stable/generated/imas.util.idsdiff.html#imas.util.idsdiff>`_)
        or the command line tool ``idsdiff`` (from IDStools) and compare the two outputs.
        Alternatively, you can calculate the hashes the two IDSs,
        and check if they are the same using ``imas.util.calc_hash()``.

    .. md-tab-item:: Solution

        .. code-block:: bash

            cp ../ymmsl_files/training/source_sink.ymmsl .
            muscle_manager --start-all ./source_sink.ymmsl

        The yMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../ymmsl_files/training/.source_sink.ymmsl
           :language: yaml

        To check the whether the input and output are the same:

        .. code-block:: bash

            idsdiff --uri 'imas:hdf5?path=/<pds_root>/training_data/training_ids/' 'imas:hdf5?path=/<pds_root>/cases/output/training/source_sink'


Exercise 2
----------

We add the first actual simulation code, NICE, to the workflow.
We use the inverse mode actor to calculate the coil currents required to obtain a desired plasma shape.
For more information on the NICE code read the `NICE docs <https://blfauger.gitlabpages.inria.fr/nice/>`_.
A NICE config file has been defined at ``<pds root>/training_data/nice_param.xml``.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Insert the NICE inverse mode actor between the sink and source actors in your workflow.
        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Tip

        You can look at the test workflows in the ``ymmsl_files`` directory for inspiration.

    .. md-tab-item:: Solution

        The yMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../ymmsl_files/training/.source_nice_sink.ymmsl
           :language: yaml

Exercise 3
----------

Sometimes a simulation can take a long time and you don't want to wait until the end to see if your output makes sense.
We now add a recorder actor to the workflow. Unlike the sink actors we have used so far, the recorder is a tap:
wired onto conduits that already exist, it does not change the coupling, it just also writes a distilled copy of
the data flowing past to disk. Point the :ref:`muscle3-dashboard <training/muscle3_dashboard>` at the run and it gets
an extra tab, rendering that data live while the run is still going, or afterwards.
For a full walkthrough of how the recorder and its config file work, see :ref:`training/visualization`.

A config file for the recorder has been defined at
``<pds root>/visualization/nice_inv.py``. It expects the following IDSs
connected to its S port:

- `equilibrium_in`: equilibrium output IDS from NICE, for time dependent results and 1D profiles
- `pf_active_in`: pf_active output IDS from NICE, for coil current plots

Unlike the ports above, the coil geometry and vessel outline it also plots do not change over the course of a run,
so they are not streamed to the recorder over a port at all: they are loaded once from a static URI via the
recorder's ``md`` setting (``<ids_name>=<uri>`` pairs), pointing directly at the same training data the source
actor reads from.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Connect the NICE output to a recorder actor in addition to the existing connections.
        Run it, then in a separate terminal with the dashboard's virtual environment activated
        (see :ref:`muscle3-dashboard <training/muscle3_dashboard>`), open the dashboard on the run and check the recorder's
        tab once it has written its first store.

        .. code-block:: bash

            m3dash open run/

    .. md-tab-item:: Solution

        The yMMSL file below shows the solution for this exercise.
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../ymmsl_files/training/.source_nice_rec_sink.ymmsl
           :language: yaml


Exercise 4a
-----------

Instead of using the premade IDS values, you might want to define certain waveforms for quick and flexible testing.
We now add the Waveform Editor actor to the workflow.
For more information on the waveform editor actor read the `Waveform Editor docs <https://waveform-editor.readthedocs.io/en/latest/muscle3.html>`_.
You can also look at the `Waveform Editor training material <https://waveform-editor.readthedocs.io/en/latest/training/training.html>`_,
which shows how to use the GUI and CLI for the Waveform Editor, how to configure the Waveform Editor, how to set up waveforms
and how to export waveforms to an IDS.
A simple waveform editor config file has been prepared for you, located at ``<pds root>/ymmsl_files/training/waveform_config.yaml``.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Inspect the given waveform editor config file.
        What does the waveform configuration define? 
        
    .. md-tab-item:: Solution

        The Waveform Editor configuration defines 2 waveforms.
        1 for the plasma current (Ip) which is set to be a constant value at 15 MA.
        1 for the toroidal magnetic field in vacuum (b0) which is set to be a constant value at 2.65 T.

Exercise 4b
-----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Insert the waveform editor actor between the source actor and the nice actor.
        Does the output IDS of the sink actor reflect the expected behavior from the configuration?
        
    .. md-tab-item:: Solution

        The yMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../ymmsl_files/training/.source_waveform_nice_rec_sink.ymmsl
           :language: yaml

Exercise 5a
-----------

Instead of checking if the data is valid by hand, we might want to automate the process 
of checking whether the data output is valid.
We now add the IMAS-validator actor to the workflow. This allows us to validate an IDS
against a pre-defined ruleset.
For more information on the IMAS-Validator actor read the `IMAS-Validator docs <https://imas-validator.readthedocs.io/en/latest/usage.html>`_
or the `OLC actor docs <https://imas-muscle3.readthedocs.io/en/latest/actor_olc.html>`_.

A simple IMAS-validator ruleset has been defined at ``<pds root>/pds_validation_test/training``. This ruleset contains only a single simple rule checking that the plasma current remains
below 17 MA. This should always be valid, since we set the plasma current to be 15 MA in 
the previous exercise, by using the Waveform Editor actor.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Connect the IMAS-validator actor to the waveform editor actor in addition to the existing connections.
        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        The yMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../ymmsl_files/training/.source_waveform_val_nice_rec_sink.ymmsl
           :language: yaml


Exercise 5b
-----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Now replace the plasma current value in the waveform configuration from 15 MA 
        to 20 MA, and rerun the pipeline from previous exercise. 

        What do you expect to happen?
        
        Read the summary report in the working directory of the muscle3 run.
        Does the summary report make sense?
        
    .. md-tab-item:: Solution

        Update the plasma current in the waveform configuration to 20 MA:

        .. code-block:: yaml

            [...]
            equilibrium:
              equilibrium/time_slice/global_quantities/ip:
              - {type: constant, value: -2.0e7}

        The OLC actor will fail, as this does not adhere to the ruleset defined in 
        previous exercise. It should look something like:
        
        .. literalinclude:: ../../../ymmsl_files/training/failed_validator_report.txt
           :language: bash


Exercise 6
----------

As a final step we want to run the transport code TORAX based on the NICE output.
We now add the TORAX actor to the workflow.
For more information on TORAX read the `TORAX docs <https://torax.readthedocs.io/en/v1.1.1/>`_.
A TORAX config file has been defined at ``<pds root>/training_data/config_torax.py``.

TORAX needs a full equilibrium IDS with multiple time slices for its initialization to create its internal geometry provider.
Since the NICE output consists of separate single timeslices, we cannot use it outright.
We first need to make sure that all the separate timeslices that are being sent around in MUSCLE3 are gathered into a single IDS before sending it to TORAX.
For this we use the accumulator actor. This gathers incoming IDSs and combines them into a big IDS with all timeslices at once.
Once it gets the last input from the actor before it, it sends the combined IDS on to the next actor, which is TORAX in this case.
For more information on the accumulator actor read the `IMAS-MUSCLE3 docs <https://imas-muscle3.readthedocs.io/en/latest/usage.html>`_.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Insert the accumulator actor and TORAX actor between the nice actor and the sink actor.
        Also send the core_profiles IDS output from the TORAX actor to the sink actor.
        You can potentially also add a second recorder actor on the TORAX output to more easily check
        the progress of your simulation -- ``<pds root>/visualization/kinetic_profiles.py`` plots
        core_profiles IDS radial profiles and is a suitable config file for it.
        Run it and check if the data output makes sense.

    .. md-tab-item:: Solution

        The yMMSL file below shows the solution for this exercise.
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../ymmsl_files/training/.source_waveform_val_nice_torax_rec_sink.ymmsl
           :language: yaml


.. _`training/build_own_actor`:

Building your own actor
------------------------

Like :ref:`training/advanced`, this section is aimed at developers rather than end users of PDS
workflows. The exercises in :ref:`training/advanced` combine existing actors. Sooner or later you
will want an actor that does not exist yet: a piece of custom physics, a data
transformation, or glue logic specific to your workflow.

Writing one is already documented elsewhere; rather than repeat it here, start with these
pages:

- `MUSCLE3 documentation <https://muscle3.readthedocs.io/en/latest/>`_: the underlying
  framework (``Instance``, ``Operator``, ``Message``) that every PDS actor is built on.
  Read this first if you have not written a MUSCLE3 actor before.
- :ref:`writing_actors`: PDS' own conventions for actor structure, port naming,
  propagating ``next_timestamp``, and the documentation template every PDS actor should
  follow.
- :ref:`code style and linting`: formatting, linting, type checking and docstring
  conventions PDS code (including actors) is expected to follow.

For real, working examples of these conventions applied end-to-end, read through one of
the smaller actors shipped with `IMAS-MUSCLE3
<https://imas-muscle3.readthedocs.io/en/latest/usage.html>`_ (``imas_muscle3/actors/``).
The passthrough actor (``passthrough_component.py``) is a good place to start: it is
compact but exercises port naming, ``next_timestamp`` handling, and a startup sanity check
all at once.

Try it yourself
----------------

Write a minimal actor that reads an IDS on ``<ids_name>_in``, applies a small
transformation, and writes it back out on ``<ids_name>_out``, then slot it into one of the
workflows from :ref:`training/advanced`.

.. todo::

    - Add the custom-actor exercises the schedule names: a small Python actor that reads
      ``equilibrium`` and ``core_profiles`` and writes a modified ``core_sources``, and a
      density source that adds x% per second.
    - Add a "code configuration" subsection: how an actor gets its own configuration file and
      settings.
    - Add a "workflow configuration" subsection covering time slice selection and the other
      knobs at workflow level, and how it relates to :ref:`training/configuring`.
