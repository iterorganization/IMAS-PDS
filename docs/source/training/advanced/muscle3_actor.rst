.. _`training/build_own_actor`:

Setting up a MUSCLE3 actor for the PDS
=======================================

Building your own actor
------------------------

Like :ref:`training/advanced`, this section is aimed at developers rather than end users of PDS
workflows. The exercises in :ref:`training/workflow_from_scratch` combine existing actors. Sooner or later you
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
