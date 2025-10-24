.. _`basic/build`:

Building your own workflows
===========================

In this section we explore building our own workflow step by step.

We start with the simplest workflow; loading IDS data, sending it to another actor and saving the data. 

A small custom IDS has been prepared on SDCC so that the workflow is fast and iterative development is easy. 
You can swap this out with your own data, although it is advised to go through the exercises with the custom data first.

The URI for the custom IDS is ``imas:hdf5?path=/home/ITER/sanderm/public/imasdb/ITER/training_ids``.

For more information on the sink and source actors read the `IMAS-MUSCLE3 docs <https://imas-muscle3.readthedocs.io/en/latest/usage.html>`_.

.. tip::
   The solution YMMSL files for all exercises, containing the correct relative paths 
   have been made available in the
   ``pds/ymmsl_files/training`` directory. It is recommended to attempt the
   exercises yourself first. If you get stuck, you can try running the provided 
   solution files and see if you understand how it works.

Exercise 1
----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Build a workflow connecting a data source actor to a data sink actor.
        Run it and check if the data output makes sense.

    .. md-tab-item:: Tip

        You can look at the test workflows in the ymmsl_files directory for inspiration.

    .. md-tab-item:: Solution

        The YMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../../ymmsl_files/training/.source_sink.ymmsl
           :language: yaml


We add the first actual simulation code, NICE, to the workflow.
We use the inverse mode actor to calculate the needed coil currents to obtain the desired plasma shape.
For more information on the NICE code read the `NICE docs <https://blfauger.gitlabpages.inria.fr/nice/>`_.
A NICE config file has been defined at ``pds/run/nice/run/input/param.xml``.

Exercise 2
----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Insert the NICE inverse mode actor between the sink and source actors in your workflow.
        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        The YMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../../ymmsl_files/training/.source_nice_sink.ymmsl
           :language: yaml

Sometimes a simulation can take a long time and you don't want to wait until the end to see if your output makes sense. 
We now add the runtime visualization actor to the workflow.
For more information on the visualization actor read the `IMAS-MUSCLE3 docs <https://imas-muscle3.readthedocs.io/en/latest/usage.html>`_.
A visualization actor config file has been defined at ``pds/run/IMAS-muscle3/imas_muscle3/visualization/examples/pds/pds.py``.

Exercise 3
----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Connect the NICE output to the visualization actor in addition to the existing connections.
        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        The YMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../../ymmsl_files/training/.source_nice_viz_sink.ymmsl
           :language: yaml


Instead of using the premade IDS values, might want to define certain waveforms for easy testing.
We now add the Waveform Editor actor to the workflow.
For more information on the waveform editor actor read the `WAVEFORM-EDITOR docs <https://waveform-editor.readthedocs.io/en/latest/muscle3.html>`_.
A simple waveform editor config file has been defined at ``/pds/ymmsl_files/training/waveform_config.yaml``.

Exercise 4
----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Insert the waveform editor actor between the source actor and the nice actor.
        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        The YMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../../ymmsl_files/training/.source_waveform_nice_viz_sink.ymmsl
           :language: yaml

Instead of checking if the data is valid by hand, we might want to automate the process 
of checking whether the data output is valid.
We now add the IMAS-validator actor to the workflow.
For more information on the IMAS-validator actor read the `IMAS-VALIDATOR docs <https://imas-muscle3.readthedocs.io/en/latest/usage.html>`_.

A simple IMAS-validator ruleset has been defined at ``pds/pds_validation_test/training/valid_eq``. This ruleset contains only a single example rule, checking that the plasma current remains
below 17 MA. This should always be valid, since we set the plasma current to be 15 MA in 
the previous exercise.

Exercise 5a
-----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Connect the IMAS-validator actor to the waveform editor actor in addition to the existing connections.
        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        The YMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../../ymmsl_files/training/.source_waveform_val_nice_viz_sink.ymmsl
           :language: yaml


Exercise 5b
-----------


.. md-tab-set::

    .. md-tab-item:: Exercise

        Now replace the IMAS-Validator ruleset to the one defined at ``pds/pds_validation_test/training/invalid_eq``. This ruleset contains only a single example rule, checking that the plasma current remains above 17 MA. This will not be valid, since we set it to be 15 MA in previous exercise. 

        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        The YMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../../ymmsl_files/training/.source_waveform_val_nice_viz_sink_invalid.ymmsl
           :language: yaml

As a final step we want to run the transport code TORAX based on the NICE output.
We now add the TORAX actor to the workflow.
For more information on TORAX read the `docs <https://torax.readthedocs.io/en/v1.1.1/>`_.
A TORAX config file has been defined at ``pds/scenario_configs/torax_default/config_torax.py``.

Since TORAX expects a full IDS with all timeslices present for its initialization, we cannot use the NICE output outright.
We first need to make sure that all the separate timeslices that are being sent around in MUSCLE3 are gathered into a single IDS before sending it to TORAX.
For this we use the accumulator actor.
For more information on the accumulator actor read the `IMAS-MUSCLE3 docs <https://imas-muscle3.readthedocs.io/en/latest/usage.html>`_.

Exercise 6
----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Insert the accumulator actor and TORAX actor between the nice actor and the sink actor.
        You can potentially also add a second visualization actor to more easily check the progress of your simulation.
        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        The YMMSL file below shows the solution for this exercise.  
        It uses ``[PWD_PLACEHOLDER]`` markers for directory paths and will not run as-is.  
        To execute the workflow, use the corresponding ready-to-run file from the
        ``pds/ymmsl_files/training`` directory.

        .. literalinclude:: ../../../../ymmsl_files/training/.source_waveform_val_nice_torax_viz_sink.ymmsl
           :language: yaml
