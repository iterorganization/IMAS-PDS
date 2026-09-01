.. _`training/new_scenario`:

Adding a new scenario
======================

Running a workflow on your own data
-------------------------------------

Every exercise so far ran against a real shot in ``pds-scenarios`` or the small training
dataset baked into ``training_data/training_ids``. Sometimes you have neither yet -- your
own device's data, or just an equilibrium and ``pf_active`` you want to try that has not
been onboarded as a shot. Getting a shot into ``pds-scenarios`` properly is a separate,
heavier process (mostly outside this repository, in ``pds-scenarios`` itself); trying your
own data against a workflow does not require it. A case is a frozen, self-contained copy of
every file a run needs, so you can take one, point its copy at your own data instead, and
run it without touching anything shared.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Build a ``prescribed_transport`` case for any shot you already have (skip this if you
        already built one in an earlier exercise), then copy it:

        .. code-block:: bash

            bin/pds-create-case prescribed_transport 105084
            cp -r cases/prescribed_transport_105084 cases/prescribed_transport_custom

        In the copy, repoint every ``DBEntry`` the case reads its scenario data from at your
        own IMAS data -- or, if you do not have any handy, at the bundled
        ``training_data/training_ids`` used in the earlier exercises. That means:

        - ``source.source_uri`` and ``equilibrium.recorder_equilibrium.md`` in
          ``workflow_settings.ymmsl``.
        - ``input`` and ``input_md`` in ``config/waveforms_no_transport.yaml``.
        - ``--dina_uri`` in ``postprocess.sh``, plus a new entry in its per-shot ``T_LIST``
          lookup, since ``$SHOT`` is no longer a real shot number.

        Then run the case and check its validation plots.

    .. md-tab-item:: Hint

        A case is a frozen snapshot: ``workflow_settings.ymmsl`` and
        ``config/waveforms_no_transport.yaml`` hold literal, already-resolved paths, not
        ``${SHOT}`` placeholders. Grep for the old shot number across the copy to find every
        place that needs editing:

        .. code-block:: bash

            grep -rn 105084 cases/prescribed_transport_custom

        That also turns up the case's own paths back into its ``config/`` directory, which
        still say ``prescribed_transport_105084`` after the copy and should point at
        ``prescribed_transport_custom`` instead.

        ``postprocess.sh`` picks its comparison times from a ``case "$SHOT" in ...`` lookup,
        and ``$SHOT`` comes from ``case.env`` -- give your run its own label there, and pick
        times inside the range your data actually covers, the same way each shot's own
        ``T_LIST`` matches its ramp-up/flattop/ramp-down.

    .. md-tab-item:: Solution

        ``case.env`` only needs its label changed -- ``$SHOT`` is not required to be a real
        shot number, it is whatever ``postprocess.sh`` keys its lookup on:

        .. code-block:: text

            WF_NAME=prescribed_transport
            SHOT=custom

        ``workflow_settings.ymmsl`` still says ``prescribed_transport_105084`` in the three
        paths pointing back into its own ``config/`` directory; fix those first:

        .. code-block:: bash

            sed -i 's/prescribed_transport_105084/prescribed_transport_custom/g' \
              cases/prescribed_transport_custom/workflow_settings.ymmsl

        Then repoint the two settings that actually name the source DBEntry:

        .. code-block:: yaml

            # before
            source.source_uri: "imas:hdf5?path=/work/projects/pds/pds-scenarios/105084/data/in"
            equilibrium.recorder_equilibrium.md: "wall=imas:hdf5?path=/work/projects/pds/pds-scenarios/105084/data/in_md pf_active=imas:hdf5?path=/work/projects/pds/pds-scenarios/105084/data/in_md"

            # after
            source.source_uri: "imas:hdf5?path=<pds root>/training_data/training_ids"
            equilibrium.recorder_equilibrium.md: "wall=imas:hdf5?path=<pds root>/training_data/training_ids pf_active=imas:hdf5?path=<pds root>/training_data/training_ids"

        Both ``data/in`` and ``data/in_md`` collapse onto the same directory here, because
        ``training_data/training_ids`` bundles the pulse IDSs and the machine description
        IDSs in one place; a real shot keeps them apart. Point these at your own two URIs if
        you have separate ones.

        The waveform editor config, ``cases/prescribed_transport_custom/config/waveforms_no_transport.yaml``,
        names the same DBEntry again under its own setting names:

        .. code-block:: yaml

            # before
            globals:
              imports:
                input: "imas:hdf5?path=/work/projects/pds/pds-scenarios/105084/data/in"
                input_md: "imas:hdf5?path=/work/projects/pds/pds-scenarios/105084/data/in_md"

            # after
            globals:
              imports:
                input: "imas:hdf5?path=<pds root>/training_data/training_ids"
                input_md: "imas:hdf5?path=<pds root>/training_data/training_ids"

        The rest of that file -- which fields ``machine_description``, ``state`` and
        ``targets`` pull from ``input``, ``input_md`` or the live ``equilibrium_in`` port --
        does not change: it says which fields to read, not where from, and stays valid for
        any equilibrium/``pf_active`` DBEntry.

        Last, ``cases/prescribed_transport_custom/postprocess.sh``:

        .. code-block:: bash

            # before
            case "$SHOT" in
              105073) T_LIST="25 130 175" ;;
              105078) T_LIST="20 150 270" ;;
              105084) T_LIST="10 150 270" ;;
              105092) T_LIST="30 110 130" ;;
              105099) T_LIST="20 35 60" ;;
              *) echo "postprocess.sh: no known t_list for shot $SHOT" >&2; exit 1 ;;
            esac
            ...
              --dina_uri "$SCENARIOS_REPO/$SHOT/data/in" \

            # after
            case "$SHOT" in
              105073) T_LIST="25 130 175" ;;
              105078) T_LIST="20 150 270" ;;
              105084) T_LIST="10 150 270" ;;
              105092) T_LIST="30 110 130" ;;
              105099) T_LIST="20 35 60" ;;
              custom) T_LIST="2 80 140" ;;
              *) echo "postprocess.sh: no known t_list for shot $SHOT" >&2; exit 1 ;;
            esac
            ...
              --dina_uri "<pds root>/training_data/training_ids" \

        ``training_data/training_ids`` only has equilibrium slices around t = 2, 80, 140,
        160 and 167 seconds, hence that ``T_LIST``; using its own data's actual time range is
        the reason this is a per-shot ``case`` statement rather than one fixed list.

        Run it the same way as any other case:

        .. code-block:: bash

            sbatch bin/pds-run-case.sbatch cases/prescribed_transport_custom

        ``postprocess.sh`` runs automatically once ``muscle_manager`` finishes. Check
        ``cases/runs/prescribed_transport_custom/plots/`` for the validation plots it
        produced, and if anything looks wrong, read
        ``cases/runs/prescribed_transport_custom/configuration.ymmsl`` first -- it shows the
        fully resolved settings the run actually used, which is the fastest way to confirm
        your edits took effect.
