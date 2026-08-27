.. _`basic/configuring_scenarios`:

Configuring scenarios
======================

Now that you have run some existing workflows (see :ref:`basic/run`), we look at where the
knobs of a scenario live, and how to change them for a single scenario without affecting
others that share the same workflow.

- ``scenario_config.env``: shot number, source/sink URIs, machine description collection,
  number of timeslices. Already scenario-specific, so edit it directly.
- ``md_collections/*.env``: machine description URIs (``pf_active``, ``pf_passive``,
  ``wall``, ``iron_core``). Shared across workflows.
- ``waveforms.yaml``: the `Waveform-Editor <https://waveform-editor.readthedocs.io/en/latest/yaml_format.html>`_
  config defining the targets sent to NICE (and TORAX, where used). Shared by the workflow.
- actor config files, e.g. ``config_nice.xml`` for NICE. Also shared by the workflow.

.. note::

    For the shared files, don't edit them in place: add a scenario-local copy next to
    ``scenario_config.env`` instead, and point at it. A ``waveforms.yaml`` in the scenario
    directory is used instead of the workflow's shared one automatically; a
    ``settings.ymmsl`` in the scenario directory can override any other setting, including
    an actor's config file path, using ``${SCEN}`` for the scenario directory.

The exercises below all use the ``prescribed_transport`` workflow with the ``105092``
scenario from :ref:`basic/run`.

Exercise 1: change the machine description
--------------------------------------------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Point the ``105092`` scenario at a different occurrence of one of the machine
        description URIs (e.g. ``MD_WALL``) and check whether the corresponding geometry
        changed in the plots.

    .. md-tab-item:: Solution

        .. code-block:: console

            cp md_collections/basic.env md_collections/my_md.env
            # edit MD_WALL in my_md.env to a different occurrence

        Point the scenario's waveform config at the new collection, then rerun
        ``cases/105092_prescribed.ymmsl`` and compare the coil/equilibrium plot
        to the previous run.

Exercise 2: change the I_p value in the waveform file
--------------------------------------------------------

By default the ``ip`` target just follows the input data:

.. code-block:: yaml

    targets:
      equilibrium/time_slice/global_quantities/ip:
        - {ref: input}

To set it yourself, replace it with an explicit
`piecewise-linear tendency <https://waveform-editor.readthedocs.io/en/latest/tendencies.html#piecewise-linear-tendency>`_.

.. md-tab-set::

    .. md-tab-item:: Exercise

        In a scenario-local ``waveforms.yaml``, define ``ip`` as a trapezoid: ramp up from
        ``t=0`` to ``t=9``, flattop to ``t=147``, ramp down to zero by ``t=170`` (matching
        the phases of this scenario, see :ref:`basic/run`). Then change the flattop value
        from 3 to 3.5 MA and rerun.

    .. md-tab-item:: Solution

        .. code-block:: yaml

            targets:
              equilibrium/time_slice/global_quantities/ip:
                - {time: [0, 9, 147, 170], value: [0, -3.5e6, -3.5e6, 0]}

        (sign follows this repo's COCOS convention). Check the new flattop current on the
        default equilibrium plot.

        .. note::

            The boundary shape and coil-current seed still come from the original input
            data, so pushing ``I_p`` far from it can keep NICE-inverse from converging
            cleanly on some timeslices.

Exercise 3: change the ramp duration in the waveform file
-------------------------------------------------------------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Stretch the ramp-up from 9 to 20 seconds.

    .. md-tab-item:: Solution

        .. code-block:: yaml

            targets:
              equilibrium/time_slice/global_quantities/ip:
                - {time: [0, 20, 147, 170], value: [0, -3.5e6, -3.5e6, 0]}

Exercise 4: change the flattop duration in the waveform file
------------------------------------------------------------------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Shorten the flattop so it ends at ``t=100`` instead of ``t=147``, keeping the
        23-second ramp-down.

    .. md-tab-item:: Solution

        .. code-block:: yaml

            targets:
              equilibrium/time_slice/global_quantities/ip:
                - {time: [0, 20, 100, 123], value: [0, -3.5e6, -3.5e6, 0]}

Exercise 5: increase the log level in the NICE config
---------------------------------------------------------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Raise NICE's own logging verbosity for this scenario only.

    .. md-tab-item:: Solution

        .. code-block:: console

            cp workflows/lib/config_nice_inverse.xml \
               my_config_nice.xml
            # in the copy: <verbose>1</verbose>

        In an override file stacked after the case:

        .. code-block:: yaml

            ymmsl_version: v0.2
            settings:
              solve.nice.xml_path: my_config_nice.xml

        Rerun with the override stacked after the case::

            muscle_manager --start-all cases/105092_prescribed.ymmsl my_override.ymmsl

        Then check the ``solve.nice`` log in the MUSCLE3 dashboard (``m3dash``).

Exercise 6: change the amount of timeslices in scenario_config.env
------------------------------------------------------------------------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Lower the number of timeslices to make the run faster.

    .. md-tab-item:: Solution

        .. code-block:: console

            export N_TIMESLICES=11

        Rerun -- it should finish noticeably faster, with the same overall behavior at a
        coarser time resolution.
