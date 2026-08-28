.. _`training/advanced`:

Advanced: Building your own workflows
=====================================

.. TODO: reformat and clean up

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

    An actor implementation can point at either an EasyBuild module, as above, or at a local
    installation -- the virtual environment ``pds_setup.sh`` builds under
    ``$PDS_REPO/local_installs/``. The local form is not simply ``virtual_env:`` in place of
    ``base_env``/``modules``: it needs ``$PDS_REPO``, which ``base_env: clean`` would purge
    away, so ``workflows/lib/local_programs.ymmsl`` uses a ``script:`` block that activates
    the venv itself. If you need a local build, copy one of those definitions rather than
    writing it from scratch -- the header comment in that file explains what goes wrong
    otherwise.

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

Exercise 7: an actor that writes core_sources
----------------------------------------------

Time to write one. We will keep the physics trivial on purpose -- the point is the shape of
an actor, not what it computes.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Write an actor that receives an ``equilibrium`` and a ``core_profiles`` IDS, and
        sends out a ``core_sources`` IDS built from them. What it puts in the source is up to
        you; a flat electron heating profile is plenty.

        Follow the port naming from :ref:`writing_actors`: ``equilibrium_in`` and
        ``core_profiles_in`` on ``F_INIT``, ``core_sources_out`` on ``O_F``.

    .. md-tab-item:: Hint

        Every PDS actor has the same skeleton -- create an ``Instance`` with its ports, then
        loop on ``instance.reuse_instance()``. Inside the loop you receive, deserialize, do
        your work, serialize, and send.

        Two details are easy to forget and annoying to debug. IDSs travel as bytes, so every
        received message needs ``deserialize`` and every sent one needs ``serialize``. And
        pass ``next_timestamp`` on, so whatever comes after you knows whether more messages
        are coming.

    .. md-tab-item:: Solution

        .. code-block:: python

            import imas
            from libmuscle import Instance, Message
            from ymmsl import Operator


            def main():
                instance = Instance(
                    {
                        Operator.F_INIT: ["equilibrium_in", "core_profiles_in"],
                        Operator.O_F: ["core_sources_out"],
                    }
                )
                factory = imas.IDSFactory()

                while instance.reuse_instance():
                    eq_msg = instance.receive("equilibrium_in")
                    eq = factory.new("equilibrium")
                    eq.deserialize(eq_msg.data)

                    cp_msg = instance.receive("core_profiles_in")
                    cp = factory.new("core_profiles")
                    cp.deserialize(cp_msg.data)

                    sources = factory.new("core_sources")
                    # ... fill sources from eq and cp ...

                    instance.send(
                        "core_sources_out",
                        Message(
                            eq_msg.timestamp,
                            next_timestamp=eq_msg.next_timestamp,
                            data=sources.serialize(),
                        ),
                    )


            if __name__ == "__main__":
                main()

        To run it, add it to a workflow the way you added the existing actors in the earlier
        exercises: a component, an implementation pointing at your script, and conduits
        feeding its two input ports.

        Start it against the small training dataset rather than a real case. The loop is
        fast, so a mistake costs you seconds instead of a queue slot.

Exercise 8: a density source
-----------------------------

Now make it do something that depends on time, which is where actors usually start getting
interesting.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Extend your actor into a density source: on each message, add a fixed *percentage per
        second* to the electron density taken from the incoming ``core_profiles``, and put the
        resulting particle source in the ``core_sources`` you send on.

        Make the percentage a setting rather than a number in the code, so it can be changed
        from a case.

    .. md-tab-item:: Hint

        The rate is per second, so you need to know how much time a message covers. Two
        consecutive messages tell you: ``next_timestamp - timestamp``.

        Guard the last message, where ``next_timestamp`` is ``None`` -- that is the signal
        that nothing follows, and it will otherwise fail in an unhelpful way.

    .. md-tab-item:: Solution

        .. code-block:: python

            rate = instance.get_setting("density_rate")  # fraction per second

            dt = None
            if cp_msg.next_timestamp is not None:
                dt = cp_msg.next_timestamp - cp_msg.timestamp

            if dt:
                n_e = cp.profiles_1d[0].electrons.density
                # particle source that raises n_e by `rate` per second over this interval
                added = n_e * rate

        and in a case or override file:

        .. code-block:: yaml

            settings:
              my_density_source.density_rate: 0.02

        Making the rate a setting rather than a constant is what turns a script into an
        actor other people can reuse. It also means you can sweep it without touching the
        code -- three override files, three runs.

Exercise 9: point an actor at a different build
------------------------------------------------

The two exercises above wrote an actor. This one is about running a different build of one
that already exists -- which is what you will be doing constantly once you are developing one
of the physics codes rather than just using it.

Each actor's program -- what to execute, and which modules to load first -- is defined in
``workflows/lib/easybuild_programs.ymmsl``. When you are developing one of the physics codes
yourself you will want your own build instead of the shared module, and you do not have to
touch the workflow to get it: an override file can redefine an implementation just like it
redefines a setting.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Look at how ``nice_inv`` is defined in ``workflows/lib/easybuild_programs.ymmsl`` and
        in ``workflows/lib/local_programs.ymmsl``. What is the difference between the two, and
        what would you write in an override file to run a build of your own?

    .. md-tab-item:: Solution

        The EasyBuild version names a module; the local version activates a virtual
        environment in your checkout. An override redefines the implementation by name:

        .. code-block:: yaml

            ymmsl_version: v0.2
            implementations:
              nice_inv:
                base_env: clean
                modules: <your NICE module>
                executable: <your executable>

        .. warning::

            An overlay replaces a same-named implementation **as a whole**, not field by
            field. You cannot add just a ``modules`` line to an existing implementation and
            keep the rest -- whatever you leave out is gone. Copy the original definition
            first and edit the copy.

        This is also why an actor's environment is worth reading before you override it. If
        the original had ``base_env: clean`` and a specific module version, and your
        replacement does not, the actor inherits your shell instead, and will behave
        differently for reasons that have nothing to do with your build.

Configuring your actor
-----------------------

The exercise above used ``instance.get_setting``, which is the whole story for actor
configuration in the PDS. Anything under ``settings:`` in a case reaches the actor that way,
matched by instance name -- exactly the keys you were overriding in
:ref:`training/configuring`, seen from the other side.

That covers a handful of numbers. When an actor needs more -- a solver configuration, a
plot definition, a mesh -- the convention is not to invent a new mechanism but to make the
setting a *path*, and let the actor read the file. You have already seen all three variants:

.. code-block:: yaml

    equilibrium.nice.xml_path: .../config_nice_inverse.xml       # NICE, an XML file
    transport.torax.python_config_module: .../config_torax.py    # TORAX, a Python module
    equilibrium.recorder_equilibrium.config: .../nice_inv.py                 # the recorder, a Python module

If you write an actor that needs its own configuration file, follow the same pattern. There
is a practical reason beyond consistency: ``bin/pds-create-case`` recognises settings whose
names end in ``xml_path``, ``python_config_module``, ``config`` or ``waveforms``, and copies
the file they point at into the case's ``config/``. Name your setting that way and your
actor's configuration is frozen into the case along with everything else. Name it something
else and the case will keep pointing at wherever the file happened to live, which will
eventually change under you.

Configuring the workflow around it
-----------------------------------

The last thing worth knowing is which knobs are not yours to implement, because the workflow
already provides them.

Time slice selection is the clearest example. It is tempting to give a new actor a "start
time" and "end time" setting, but you rarely need to: the ``source`` component decides which
timeslices enter the workflow at all, via ``source.t_min`` and ``source.t_max``, and an actor
downstream simply sees fewer messages. Similarly, how many slices a converging workflow
walks through is ``loop.max_slices`` on its outer loop, not something each actor decides for
itself. Both are covered in :ref:`training/configuring`.

The rule of thumb: settings that answer "which data flows through this workflow?" belong to
the components that produce or drive that data, and settings that answer "what does this
code do with the data it gets?" belong to the actor. Following it keeps a new actor usable in
a workflow you did not write, and stops two components from disagreeing about which part of
the pulse is being simulated.

Bringing a new scenario into the PDS
------------------------------------

Sooner or later you will want to run a pulse that is not in ``pds-scenarios`` yet -- a new
DINA output, say. The work splits in two, and it is worth knowing which half is which,
because most of it is not in this repository at all.

**In pds-scenarios.** A shot directory is not the raw DINA output; it is that output
converted into the layout every PDS workflow expects. Each shot carries a ``source.env``
naming where its raw data came from, and the repository's own ``tools/`` turn that into the
``data/in`` and ``data/in_md`` DBEntries you looked at in :ref:`training/understanding`. Adding
a shot means adding it there, following the shots already present as a template.

**In the PDS.** Usually nothing. The workflows take the shot number as a parameter -- every
path in ``workflows/<name>/settings.ymmsl`` is written with ``${SHOT}`` in it -- so as soon as
the scenario exists, ``bin/pds-create-case <workflow> <new-shot>`` works.

You only come back to this repository when the new shot needs something the generic settings
do not give it, and then it goes in one file:
``cases/overrides/<workflow>_<newshot>.ymmsl``. Look at the existing overrides to see what
that is in practice -- mostly a loop window that suits the pulse, and sometimes a calibrated
solver configuration.

There is one loose end that catches people out. The validation plotting in each workflow's
``postprocess.sh`` picks its comparison times from a per-shot list, and a shot that is not in
that list makes the job fail *after* a perfectly good simulation. If you add a shot, add it
there too.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Without adding anything, work out what would be needed to run ``prescribed_transport``
        on a shot that is currently only used by ``metis_nice_inverse_from_dina``.

    .. md-tab-item:: Solution

        The scenario data already exists, so ``bin/pds-create-case prescribed_transport
        <shot>`` builds a case straight away -- the generic settings fill in the shot number
        and it runs.

        Whether the *result* is any good is a separate question: no override has been tuned
        for that combination, so the loop window and the solver configuration are whatever the
        workflow's defaults are. And unless the shot happens to be in
        ``prescribed_transport/postprocess.sh``'s list, the run will finish and the plotting
        step will not.

With that, you have seen the whole path: running a premade case, configuring it, watching it,
building a workflow out of existing actors, writing an actor of your own, and adding the
scenario it runs on.
