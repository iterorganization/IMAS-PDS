.. _`basic/build`:

Building your own workflows
===========================

In this section we explore building our own workflow step by step.

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
    MUSCLE3 uses the current environment by default.
    It also enables the user to pick a specific virtual environment for a given implementation.
    Many of the python based actors were installed in the `pds_setup.sh` script using virtual environments.
    Make sure to use those virtual environments when using these actors.

.. tip::
   The solution yMMSL files for all exercises, containing the correct relative paths 
   have been made available in the
   ``pds/ymmsl_files/training`` directory. It is recommended to attempt the
   exercises yourself first. If you get stuck, you can try running the provided 
   solution yMMSL files and see if you understand how they are implemented.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Build a workflow connecting a data source actor to a data sink actor. 
        Ensure the equilibrium IDS from the URI shown above will be send.
        Run it and check if the input equilibrium IDS is the same as the output IDS.

    .. md-tab-item:: Tip

        You can look at the test workflows in the ymmsl_files directory for inspiration.

    .. md-tab-item:: Solution

        The yMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../../ymmsl_files/training/.source_sink.ymmsl
           :language: yaml

        To check whether the two IDSs are identical, you can use ``imas print <URI> equilibrium``
        and compare the two outputs. Alternatively, you can calculate the hashes the two IDSs,
        and check if they are the same using ``imas.util.calc_hash()``.


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
        
    .. md-tab-item:: Solution

        The yMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../../ymmsl_files/training/.source_nice_sink.ymmsl
           :language: yaml

Exercise 3
----------

Sometimes a simulation can take a long time and you don't want to wait until the end to see if your output makes sense. 
We now add the runtime visualization actor to the workflow.
For more information on the visualization actor read the `IMAS-MUSCLE3 docs <https://imas-muscle3.readthedocs.io/en/latest/usage.html>`_.
A visualization actor config file has been defined at ``<pds root>/run/IMAS-muscle3/imas_muscle3/visualization/examples/pds/pds.py``.
This example config expects the following IDSs connected to the S port:

    - equilibrium: [equilibrium_in]
    - pf_active: [pf_active_in, pf_active_md_in]
    - wall: [wall_md_in]

.. md-tab-set::

    .. md-tab-item:: Exercise

        Connect the NICE output to the visualization actor in addition to the existing connections.

        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        The yMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../../ymmsl_files/training/.source_nice_viz_sink.ymmsl
           :language: yaml


Exercise 4
----------

Instead of using the premade IDS values, might want to define certain waveforms for easy testing.
We now add the Waveform Editor actor to the workflow.
For more information on the waveform editor actor read the `Waveform Editor docs <https://waveform-editor.readthedocs.io/en/latest/muscle3.html>`_.
A simple waveform editor config file has been prepared for you, located at ``<pds root>/ymmsl_files/training/waveform_config.yaml``.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Insert the waveform editor actor between the source actor and the nice actor.
        What does the waveform configuration define? Does the output IDS of the sink actor
        reflect this?
        
    .. md-tab-item:: Solution

        The yMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../../ymmsl_files/training/.source_waveform_nice_viz_sink.ymmsl
           :language: yaml

        The Waveform Editor configuration defines a single waveform for the plasma current (Ip),
        which is set to be a constant value at 15 MA.

Exercise 5a
-----------

Instead of checking if the data is valid by hand, we might want to automate the process 
of checking whether the data output is valid.
We now add the IMAS-validator actor to the workflow. This allows us to validate an IDS
against a pre-defined ruleset.
For more information on the IMAS-Validator actor read the `IMAS-Validator docs <https://imas-validator.readthedocs.io/en/latest/usage.html>`_.

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

        .. literalinclude:: ../../../../ymmsl_files/training/.source_waveform_val_nice_viz_sink.ymmsl
           :language: yaml


Exercise 5b
-----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Now replace the plasma current value in the waveform configuration from 15 MA 
        to 20 MA, and rerun the pipeline from previous exercise. 

        What do you expect to happen?
        
    .. md-tab-item:: Solution

        Update the plasma current in the waveform configuration to 20 MA:

        .. code-block:: yaml

            [...]
            equilibrium:
              equilibrium/time_slice/global_quantities/ip:
              - {type: constant, value: -2.0e7}

        The OLC actor will fail, as this does not adhere to the ruleset defined in 
        previous exercise.

Exercise 6
----------

As a final step we want to run the transport code TORAX based on the NICE output.
We now add the TORAX actor to the workflow.
For more information on TORAX read the `docs <https://torax.readthedocs.io/en/v1.1.1/>`_.
A TORAX config file has been defined at ``<pds root>/training_data/config_torax.py``.

Since TORAX expects a full IDS with all timeslices present for its initialization, we cannot use the NICE output outright.
We first need to make sure that all the separate timeslices that are being sent around in MUSCLE3 are gathered into a single IDS before sending it to TORAX.
For this we use the accumulator actor.
For more information on the accumulator actor read the `IMAS-MUSCLE3 docs <https://imas-muscle3.readthedocs.io/en/latest/usage.html>`_.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Insert the accumulator actor and TORAX actor between the nice actor and the sink actor.
        You can potentially also add a second visualization actor to more easily check the progress of your simulation.
        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        The yMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../../ymmsl_files/training/.source_waveform_val_nice_torax_viz_sink.ymmsl
           :language: yaml
