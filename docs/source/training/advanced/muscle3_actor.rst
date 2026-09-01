.. _`training/build_own_actor`:

Setting up a MUSCLE3 actor for the PDS
=======================================

Building your own actor
------------------------

The exercises in :ref:`training/workflow_from_scratch` combine existing actors. Sooner or later you
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

Exercise 1: an actor that writes core_sources
----------------------------------------------

Time to write one. We will keep the physics trivial on purpose -- the point is the shape of
an actor, not what it computes.

The workflow is the same ``source`` / ``sink`` pair from
:ref:`training/workflow_from_scratch`, with your actor wired in between: ``source`` ->
``my_actor`` -> ``sink``. The training dataset already has everything you need --
``training_data/training_ids`` contains ``equilibrium.h5`` and ``core_profiles.h5`` -- so
``source`` only needs a second output port wired up alongside ``equilibrium_out``, and
``sink`` needs to consume ``core_sources_in`` instead of ``equilibrium_in``.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Copy ``ymmsl_files/training/source_sink.ymmsl`` to your working directory and edit it:

        - Add ``core_profiles_out`` to ``source``'s ``o_i`` port list.
        - Add a component for your actor, with ``equilibrium_in`` and ``core_profiles_in`` on
          ``f_init`` and ``core_sources_out`` on ``o_f``, and an ``implementations`` entry
          pointing ``executable: python`` / ``args`` at your script.
        - Wire ``source.equilibrium_out`` and ``source.core_profiles_out`` to your actor's two
          input ports, and your actor's ``core_sources_out`` to a renamed
          ``sink.core_sources_in`` (``sink`` keeps its ``f_init`` port, just pointed at the new
          IDS name).

        Then write the actor itself: receive an ``equilibrium`` and a ``core_profiles`` IDS,
        and send out a ``core_sources`` IDS built from them. Fill the source with a flat
        electron heating profile of ``1e5`` W/m³ (100 kW/m³) at every point of the
        ``rho_tor_norm`` grid taken from the incoming ``core_profiles``. You do not need the
        equilibrium for that calculation -- receiving it is only there to practice a
        two-port ``F_INIT``.

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

            import numpy as np
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

                    rho = cp.profiles_1d[0].grid.rho_tor_norm

                    sources = factory.new("core_sources")
                    source = sources.source.resize(1)[0]
                    source.identifier.name = "ec"
                    p1d = source.profiles_1d.resize(1)[0]
                    p1d.grid.rho_tor_norm = rho
                    p1d.electrons.energy = np.full_like(rho, 1e5)  # flat 100 kW/m^3

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

        ``source_sink.ymmsl``, edited as above, becomes:

        .. code-block:: yaml

            ymmsl_version: v0.1
            model:
              name: my_actor
              components:
                source:
                  implementation: source
                  ports:
                    o_i: [equilibrium_out, core_profiles_out]
                my_actor:
                  implementation: my_actor
                  ports:
                    f_init: [equilibrium_in, core_profiles_in]
                    o_f: [core_sources_out]
                sink:
                  implementation: sink
                  ports:
                    f_init: [core_sources_in]
              conduits:
                source.equilibrium_out: my_actor.equilibrium_in
                source.core_profiles_out: my_actor.core_profiles_in
                my_actor.core_sources_out: sink.core_sources_in
            settings:
              source.source_uri: "imas:hdf5?path=[PWD_PLACEHOLDER]/training_data/training_ids/"
              sink.sink_uri: "imas:hdf5?path=[PWD_PLACEHOLDER]/cases/output/training/my_actor"
              sink.sink_mode: "x"
            implementations:
              source:
                base_env: clean
                modules: IMAS-MUSCLE3/1.0.0-intel-2025b-pds
                executable: python
                args: "-u -m imas_muscle3.actors.source_component"
              sink:
                base_env: clean
                modules: IMAS-MUSCLE3/1.0.0-intel-2025b-pds
                executable: python
                args: "-u -m imas_muscle3.actors.sink_component"
              my_actor:
                executable: python
                args: "-u [PWD_PLACEHOLDER]/my_actor.py"

        ``my_actor`` has no ``base_env``/``modules``, so it inherits the environment you
        already loaded (``module load PDS`` gives it ``imas`` and ``libmuscle``) instead of a
        purged one -- appropriate for a plain script, not an EasyBuild-installed actor.

        Run it with the muscle-manager, the same as in :ref:`training/workflow_from_scratch`:

        .. code-block:: bash

            muscle_manager --start-all ./my_actor.ymmsl

        Then check the output makes sense, e.g. with ``imas.util.idsdiff()`` or ``idsdiff``
        against ``training_data/training_ids`` for the fields you did not touch.

Exercise 2: a density source
-----------------------------

Now make it do something that depends on time, which is where actors usually start getting
interesting.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Add a density source alongside the heating source from Exercise 1:
        multiply the electron density taken from the incoming ``core_profiles``
        by a *fraction per second* rate, and put the result in ``electrons.particles`` of a
        second entry in ``core_sources.source``, so it raises the density by that fraction
        each second while the heating source keeps flowing unchanged.

        Make the rate a setting called ``density_rate`` rather than a number in the code, so
        it can be changed from a case. On the last message, where ``next_timestamp`` is
        ``None``, send an all-zero particle source instead of computing a rate.

    .. md-tab-item:: Hint

        ``electrons.particles`` is already a *rate* (m⁻³·s⁻¹), so multiplying the density by
        the fraction-per-second setting is the whole calculation -- you do not need to know
        how long the interval is to compute it.

        You do need ``next_timestamp`` for one thing: telling the last message apart from the
        rest. ``cp_msg.next_timestamp is None`` is that signal, and computing anything from a
        ``None`` timestamp fails in an unhelpful way, so check it before you touch the
        timestamps at all.

        ``sources.source.resize(2)`` gives you two entries in the array instead of one --
        keep the first for the Exercise 1 heating source and use the second for the new
        particle source. Each entry gets its own ``identifier`` and its own
        ``profiles_1d``.

    .. md-tab-item:: Solution

        .. code-block:: python

            import numpy as np
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
                    rate = instance.get_setting("density_rate")  # fraction per second

                    eq_msg = instance.receive("equilibrium_in")
                    eq = factory.new("equilibrium")
                    eq.deserialize(eq_msg.data)

                    cp_msg = instance.receive("core_profiles_in")
                    cp = factory.new("core_profiles")
                    cp.deserialize(cp_msg.data)

                    rho = cp.profiles_1d[0].grid.rho_tor_norm

                    n_e = cp.profiles_1d[0].electrons.density
                    added = np.zeros_like(n_e)
                    if cp_msg.next_timestamp is not None:
                        added = n_e * rate

                    sources = factory.new("core_sources")
                    heating, gas_puff = sources.source.resize(2)

                    heating.identifier.name = "ec"
                    heating_p1d = heating.profiles_1d.resize(1)[0]
                    heating_p1d.grid.rho_tor_norm = rho
                    heating_p1d.electrons.energy = np.full_like(rho, 1e5)  # flat 100 kW/m^3

                    gas_puff.identifier.name = "gas_puff"
                    gas_puff_p1d = gas_puff.profiles_1d.resize(1)[0]
                    gas_puff_p1d.grid.rho_tor_norm = rho
                    gas_puff_p1d.electrons.particles = added

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

        and in a case or override file:

        .. code-block:: yaml

            settings:
              my_density_source.density_rate: 0.02

        Making the rate a setting rather than a constant is what turns a script into an
        actor other people can reuse.
