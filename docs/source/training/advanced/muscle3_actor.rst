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
``training_data/training_ids`` contains ``equilibrium.h5`` and ``core_profiles.h5``.

Unlike the previous section, you will not be hand-editing yMMSL wiring here. A ready-to-run
``workflow.ymmsl`` for this exercise is provided at
``ymmsl_files/training/source_my_actor_sink.ymmsl`` -- ``source`` already has a second output
port alongside ``equilibrium_out``, and ``sink`` already consumes ``core_sources_in``. Set up
a case directory for it and the only thing left to build is the actor.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Set up the case directory:

        .. code-block:: bash

            mkdir -p cases/my_actor
            cp ymmsl_files/training/source_my_actor_sink.ymmsl cases/my_actor/workflow.ymmsl

        Open ``cases/my_actor/workflow.ymmsl`` and look at how ``my_actor`` is wired in --
        ``equilibrium_in`` and ``core_profiles_in`` on ``f_init``, ``core_sources_out`` on
        ``o_f``, fed from ``source`` and consumed by ``sink``. Its ``programs`` entry already
        points ``executable: python`` / ``args`` at ``$PDS_REPO/cases/my_actor/my_actor.py`` --
        that is the file you are about to write.

        Write ``cases/my_actor/my_actor.py``: receive an ``equilibrium`` and a
        ``core_profiles`` IDS, and send out a ``core_sources`` IDS built from them. Fill the
        source with a flat electron heating profile of ``1e5`` W/m³ (100 kW/m³) at every point
        of the ``rho_tor_norm`` grid taken from the incoming ``core_profiles``. You do not need
        the equilibrium for that calculation -- receiving it is only there to practice a
        two-port ``F_INIT``.

        Follow the port naming from :ref:`writing_actors`: ``equilibrium_in`` and
        ``core_profiles_in`` on ``F_INIT``, ``core_sources_out`` on ``O_F``.

        Run it with ``bin/pds-run-case``, not ``muscle_manager`` directly:

        .. code-block:: bash

            bin/pds-run-case cases/my_actor

        This submits a Slurm job (``squeue --me`` to watch it) and writes its own
        ``slurm-<jobid>.out`` at the repo root; the run itself lands under
        ``cases/runs/my_actor_<timestamp>/`` (``cases/runs/my_actor`` symlinks to the latest
        one). If no ``sbatch`` is on your ``PATH``, ``bin/pds-run-case`` falls back to running
        the same script directly instead, no Slurm needed.

        ``sink.sink_mode`` is ``"x"`` (exclusive create), so a second attempt fails unless you
        remove the previous output first: ``rm -rf cases/output/training/my_actor``.

        Then check the output makes sense, e.g.:

        .. code-block:: python

            import imas
            with imas.DBEntry(
                "imas:hdf5?path=cases/output/training/my_actor", "r"
            ) as db:
                cs = db.get("core_sources")
            print(cs.source[0].identifier.name, cs.source[0].profiles_1d[0].electrons.energy)

    .. md-tab-item:: Hint

        Every PDS actor has the same skeleton -- create an ``Instance`` with its ports, then
        loop on ``instance.reuse_instance()``. Inside the loop you receive, deserialize, do
        your work, serialize, and send.

        A few details are easy to forget and annoying to debug:

        - IDSs travel as bytes, so every received message needs ``deserialize`` and every sent
          one needs ``serialize``.
        - Pass ``next_timestamp`` on, so whatever comes after you knows whether more messages
          are coming.
        - ``resize(n)`` on an array of structures (e.g. ``sources.source``) mutates it in place
          and returns ``None`` -- it does not hand you back the new elements. Call it, then
          index the array separately: ``sources.source.resize(1); source = sources.source[0]``.
        - A freshly created IDS needs ``ids_properties.homogeneous_time`` (and a ``time``
          array) set before you can ``serialize()`` it, or you get
          ``ValueError: IDS is found to be EMPTY (homogeneous_time undefined)``.

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
                    sources.ids_properties.homogeneous_time = 1
                    sources.time = np.array([eq_msg.timestamp])
                    sources.source.resize(1)
                    source = sources.source[0]
                    source.identifier.name = "ec"
                    source.profiles_1d.resize(1)
                    p1d = source.profiles_1d[0]
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

        For reference, this is what ``cases/my_actor/workflow.ymmsl`` looks like -- the version
        you copied from ``ymmsl_files/training/source_my_actor_sink.ymmsl`` already has the
        paths below resolved (that file is generated from the ``.template`` below by
        ``setup_files/setup_test_files.sh``, see :ref:`training/setup`; the
        ``[PWD_PLACEHOLDER]`` markers here will not run as-is):

        .. literalinclude:: ../../../../ymmsl_files/training/source_my_actor_sink.ymmsl.template
           :language: yaml

        ``my_actor`` has no ``base_env``/``modules``, so it inherits the environment you
        already loaded (``module load PDS`` gives it ``imas`` and ``libmuscle``) instead of a
        purged one -- appropriate for a plain script, not an EasyBuild-installed actor. Its
        ``args`` uses ``$PDS_REPO`` rather than ``$CASE_DIR``: ``$PDS_REPO`` (set by
        ``module load PDS``) is always an absolute path, while ``$CASE_DIR`` stays whatever
        (possibly relative) path you gave ``bin/pds-run-case`` -- and each actor runs from its
        own per-instance working directory, so a relative script path resolves against the
        wrong place there.

Exercise 2: a density source
-----------------------------

Now make it do something that depends on time, which is where actors usually start getting
interesting.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Same case directory as Exercise 1 -- keep editing ``cases/my_actor/my_actor.py`` in
        place. ``cases/my_actor/workflow.ymmsl`` already has a ``my_actor.density_rate: 0.02``
        setting waiting for you (unused until now), so there is nothing to change there either.

        Add a density source alongside the heating source from Exercise 1:
        multiply the electron density taken from the incoming ``core_profiles``
        by a *fraction per second* rate, and put the result in ``electrons.particles`` of a
        second entry in ``core_sources.source``, so it raises the density by that fraction
        each second while the heating source keeps flowing unchanged.

        Read the rate from the ``density_rate`` setting rather than hard-coding a number, so
        it can be changed from the case. On the last message, where ``next_timestamp`` is
        ``None``, send an all-zero particle source instead of computing a rate.

        ``sink.sink_mode`` is ``"x"`` (exclusive create), so the sink refuses to write into
        the output directory Exercise 1 already created. Clear it, then rerun the same way as
        before:

        .. code-block:: bash

            rm -rf cases/output/training/my_actor
            bin/pds-run-case cases/my_actor

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
        ``profiles_1d``. As in Exercise 1, ``resize()`` returns ``None``: call it, then index
        ``sources.source[0]`` and ``sources.source[1]`` separately.

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
                    sources.ids_properties.homogeneous_time = 1
                    sources.time = np.array([eq_msg.timestamp])
                    sources.source.resize(2)
                    heating, gas_puff = sources.source[0], sources.source[1]

                    heating.identifier.name = "ec"
                    heating.profiles_1d.resize(1)
                    heating_p1d = heating.profiles_1d[0]
                    heating_p1d.grid.rho_tor_norm = rho
                    heating_p1d.electrons.energy = np.full_like(rho, 1e5)  # flat 100 kW/m^3

                    gas_puff.identifier.name = "gas_puff"
                    gas_puff.profiles_1d.resize(1)
                    gas_puff_p1d = gas_puff.profiles_1d[0]
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

        The setting itself is already in ``cases/my_actor/workflow.ymmsl`` from the start (see
        the ``workflow.ymmsl`` listing in Exercise 1's Solution tab above):

        .. code-block:: yaml

            settings:
              my_actor.density_rate: 0.02

        Making the rate a setting rather than a constant is what turns a script into an
        actor other people can reuse -- someone can tune it from their own case without
        touching your code.
