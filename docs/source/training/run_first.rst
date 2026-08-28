.. _`training/run_first`:

Running your first PDS workflow
===============================

.. _`training/muscle3_dashboard`:

Before we run a workflow, it is useful to have the MUSCLE3 dashboard open. 
`muscle3-dashboard <https://github.com/multiscale/muscle3-dashboard>`_
is a web-based dashboard for inspecting and debugging MUSCLE3 simulations.
It shows you the workflow diagrams, the live status and logs of each MUSCLE3 actor,
and it can show live visualizations during a run.
Keeping it open while you run the exercises in the next section makes it much easier to see what 
is going on, and to figure out what went wrong if a run crashes.

The MUSCLE3 dashboard was automatically installed when you loaded the PDS module.

Opening the dashboard
----------------------

The dashboard runs as a web-server that keeps going while you run and re-run
workflows, so it is useful to open it in its own terminal. Let's open a new terminal
and load up the PDS environment again:

.. code-block:: bash

    # Open the directory in which you cloned the PDS
    cd <your PDS install>
    # Load the PDS module
    module use /work/projects/pds/modules/all
    module load PDS

Now, let's start up the MUSCLE3 dashboard, and have it look for PDS runs in the current
working directory. This will automatically open the MUSCLE3 dashboard in a new browser tab.

.. code-block:: bash

    m3dash open .

If you have done any PDS runs before in this directory, they will show up it 
the list. If you have just freshly cloned the repository, it will show ``No runs found yet``.
In the next part, we will run a workflow, which we will be able to visualize in the MUSCLE3 dashboard.

Running your first workflow
---------------------------

Now that we have the dashboard open, let's start a PDS run and see if it will show up in there.
For this example, we will run a very simple workflow to get to know the MUSCLE3 dashboard.


.. md-tab-set::

    .. md-tab-item:: Exercise

        We will have a look at the workflow called ``test_sink_source_actor``. 
        The yMMSL file is located in the ``ymmsl_files/test_sink_source_actor`` directory.
        
        Open the ``ymmsl_files/test_sink_source_actor.ymmsl`` file and have a look at
        the contents. Do you understand what this workflow does?

    .. md-tab-item:: Hint

        You can have a look at the `documentation <https://imas-muscle3.readthedocs.io/en/latest/usage.html>`_
        of the IMAS-MUSCLE3 actors to see what the sink and source actors do.

    .. md-tab-item:: Solution

        This workflow will first read an equilibrium IDS from disk using the Source actor.
        It will then send it to the Sink actor, which will write it back to disk under
        a new URI.

Let's now run the workflow you looked at in the previous exercise.


.. md-tab-set::

    .. md-tab-item:: Exercise

        Ensure you have a terminal open where you have loaded the PDS environment. 
        Take a look at `training/setup` if you need a reminder.

        Now, let's start the run by providing it to the muscle manager

        .. code-block:: bash

            muscle_manager --start-all ymmsl_files/test_sink_source_actor.ymmsl
        
        Keep an eye at the MUSCLE3 Dashboard after you start the run, what do you see?

    .. md-tab-item:: Solution

        After the MUSCLE3 Manager has started the run, the run will appear in the MUSCLE3
        Dashboard. You can click it to see further information about the run.

Overview of MUSCLE3 Dashboard
-----------------------------

Let's open the run that you just completed and go over what each of the elements in the 
MUSCLE3 dashboard means.


- The Simulation graph: a simulation graph of the MUSCLE3 actor coupling, built from the yMMSL file.
  Each component is colored by the status of the MUSCLE3 actor in real time. You can 
  click on any of the components to see more information about this actor.

  .. image:: images/muscle3_dashboard_graph.png
      :width: 60%

- Component information: This shows information about the selected actor: its ports, program, settings
  and description. Any referenced text files are shown as linkss that open in a read-only viewer.

  .. image:: images/muscle3_dashboard_component.png

- The log files: This section shows the muscle manager logs and logs for the selected actor's stdout/stderr. 

  .. image:: images/muscle3_dashboard_logs.png


Debugging a PDS run
-------------------

The MUSCLE3 Dashboard is very useful for debugging failing runs. This will be covered in the next exercise.


.. md-tab-set::

    .. md-tab-item:: Exercise

        We will alter the workflow that we ran in the previous exercise and include a 
        small mistake. We will then run it to see what will happen in the MUSCLE3 Dashboard. 
        Open the ``ymmsl_files/test_sink_source_actor.ymmsl`` file that you ran in the previous exercise.

        Change the ``path`` of the ``source_component.source_uri`` to point to a non-existing URI, 
        for example: ``<your PDS directory>/cases/input/test_data_ids_DOES_NOT_EXIST``

        What do you think will happen when you run this workflow?

        Let's run the same workflow again:

        .. code-block:: bash

            muscle_manager --start-all ymmsl_files/test_sink_source_actor.ymmsl

        Keep an eye at the MUSCLE3 Dashboard after you start the run, what do you see?
        Can you figure out what is wrong from the dashboard?

    .. md-tab-item:: Solution

        After the MUSCLE3 Manager has started the run, the run will appear in the MUSCLE3
        Dashboard. It should quickly crash. You can click it to see further information about the run.
        You should see the following

        .. image:: images/crash_run.png
            :width: 60%

        This clearly shows that our source component crashed. In order to see what went wrong, let's
        take a look at the log files of the source component. Taking a look at the stderr of the 
        source component we can quickly found out what went wrong, taking a look at error message on the last line:
        ``ALBackendException = HDF5 master file not found``

        Our workflow failed because the source actor was not able to find the provided URI.

What a run leaves behind
------------------------

Whenever you run a PDS run, it creates its own directory, so nothing is ever overwritten by 
the next run. For example, for the workflow we ran in the previous exercise you will see 
the following folder being generated:

.. code-block:: text

    run_test_sink_source_actor_20260824_142122/
        muscle3_manager.log        # what the manager did: planning, starting, errors
        configuration.ymmsl        # the fully resolved configuration that was executed
        performance.sqlite         # timing data per actor and per message
        instances/
            source_component/
                run_script.sh      # the exact command used to start this actor
                stdout.txt         # everything the actor printed
                stderr.txt         # its error output
                workdir/           # the directory the actor ran in
            sink_component/
                ...


Unless you say otherwise, the MUSCLE3 manager creates it in the directory you started from and names it
after the model and the time it started, which is the line it printed when your first run
finished. You can use ``--run-dir`` if you want to choose the location yourself, for example to keep all your
runs together:

.. code-block:: bash

    mkdir -p runs/my_first_run
    muscle_manager --start-all --run-dir runs/my_first_run ymmsl_files/test_sink_source_actor.ymmsl

When the crash is not in the first actor
----------------------------------------

The crash above was the easy kind: the very first actor died, and the run was over before it
started. More often a run gets going, and something further down the chain gives up. The
dashboard is more useful then, because the graph shows you which crashed first while
the others were still working.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Undo the change from the previous exercise, so the source URI is valid again. This
        time break the other end: point ``sink_component.sink_uri`` at somewhere you are not
        allowed to write, for example ``imas:hdf5?path=/test_output``.

        Run it again and watch the graph. What happens?

        .. code-block:: bash

            muscle_manager --start-all ymmsl_files/test_sink_source_actor.ymmsl

    .. md-tab-item:: Solution

        The source reads its data and sends it, so it completes. The sink is the one that
        fails, when it tries to create the output DBEntry. In the graph the sink actor 
        is highlighted in bright red, which tells you where to look.

        Open the sink's ``stderr`` and you will find a permission error on the path you gave
        it.


Now that we have gotten our feet wet by running a simple example workflow, 
let's take a look at more complex workflows in the next section!
