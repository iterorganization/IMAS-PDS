.. _`basic/build`:

Building your own workflows
===========================

In this section we explore building our own workflow step by step.

We start with the simplest workflow, loading IDS data and sending it to another actor. 
A small custom IDS has been prepared to that the wokflow is fast and iterative development is easy.
You can swap this out with your own data, although it is advised to go through the exercises with the custom data first.
The custom IDS can be found at path/to/custom/ids
*path to docs*

Exercise 1
----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Build a workflow connecting an data source actor to a data sink actor.
        Run it and check if the data output makes sense.

    .. md-tab-item:: Tip

        You can look at the test workflows in the ymmsl_files directory for inspiration.

    .. md-tab-item:: Solution

        bla bla


We add the first actual simulation code, NICE, to the workflow.
We use the inverse mode actor to calculate the needed coil currents to obtain the desired plasma shape.
*path to docs*  
A NICE config file has been defined at path/to/nice/config.

Exercise 2
----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Insert the NICE inverse mode actor between the sink and source actors in your workflow.
        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        bla bla

Sometimes a simulation can take a long time and you don't want to wait until the end to see if your output makes sense. 
We now add the runtime visualization actor to the workflow.
*path to docs*  
A visualization actor config file has been defined at path/to/visualization/config.
You can also make and try your own.

Exercise 3
----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Connect the NICE output to the visualization actor in addition to the existing connections.
        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        bla bla


Instead of using the premade IDS values, might want to define certain waveforms for easy testing.
We now add the Waveform Editor actor to the workflow.
*path to docs*  
A simple waveform editor config file has been defined at path/to/waveform-editor/config.
You can also make and try your own.

Exercise 4
----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Insert the waveform editor actor between the source actor and the nice actor.
        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        bla bla

Instead of handchecking, we might want to automate the process of checking whether the data output is valid.
We now add the IMAS-validator actor to the workflow.
*path to docs*  
An IMAS-validator ruleset has been defined at path/to/waveform-editor/config.
You can also make and try your own.

Exercise 5
----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Connect the IMAS-validator actor to the waveform editor actor in addition to the existing connections.
        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        bla bla

As a final step we want to run the transport code TORAX based on the NICE output.
We now add the TORAX actor to the workflow.
*path to docs*  
A TORAX config file has been defined at path/to/torax/config.
You can also make and try your own.
Since TORAX expects a full IDS with all timeslices present for its initialization, cannot use the NICE output outright.
We first need to make sure that all the separate timeslices that are being sent around in MUSCLE3 are gathered into a single IDS before sending it to TORAX.
For this we use the accumulator actor.
*path to docs*  

Exercise 6
----------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Insert the accumulator actor and TORAX actor between the nice actor and the sink actor.
        You can potentially also add a second visualization actor to more easily check the progress of your simulation.
        Run it and check if the data output makes sense.
        
    .. md-tab-item:: Solution

        bla bla
