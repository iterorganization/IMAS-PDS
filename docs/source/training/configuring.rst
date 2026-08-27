.. _`training/configuring`:

Configuring existing workflows
==============================

Now that you have run some existing cases (see :ref:`training/run_complex`), we look at where
the knobs live, and how to change them for a single run without affecting anyone else using
the same workflow or the same scenario.

- The **case**, ``cases/<workflow>_<shot>/``: everything specific to this run. Built by
  ``bin/pds-create-case <workflow> <shot>``, it is a frozen snapshot of the pairing --
  ``workflow.ymmsl`` (the structure), ``workflow_settings.ymmsl`` (the workflow's generic
  settings, with the shot's paths filled in), an optional ``scenario_settings.ymmsl`` from
  ``cases/overrides/<workflow>_<shot>.ymmsl``, and ``config/``, local copies of every
  NICE/TORAX/recorder/waveform config file those settings point at.
- The **scenario**, ``$SCENARIOS_REPO/<shot>/``: the input data (``data/``) and the
  `Waveform-Editor <https://waveform-editor.readthedocs.io/en/latest/yaml_format.html>`_
  configuration files that define the machine description and the targets sent to NICE
  (and TORAX, where used).
- The **workflow**, ``workflows/<name>/workflow.ymmsl`` plus the building blocks it imports
  from ``workflows/lib/``: the structure only, which actors exist and how they are wired.
  It holds no paths and no scenario data.
- Actor configuration files owned by the workflow and shared by every case built from it,
  such as ``workflows/prescribed_transport/config_nice_inverse.xml`` for NICE and
  ``workflows/inverse_convergence/config_torax.py`` for TORAX. ``pds-create-case`` copies
  these into the case's ``config/``, so editing the original only affects cases you build
  afterwards.

.. note::

    Do not edit a case or a shared configuration file in place. Put your change in a small
    override file and stack it after the case: the last value given for a key wins.

    .. code-block:: bash

        sbatch bin/pds-run-case.sbatch cases/prescribed_transport_105092 ./my_override.ymmsl

    That keeps the case reusable, and the run directory records exactly what you ran: your
    files in ``input/``, and the merged result in ``configuration.ymmsl``.

.. note::

    Settings keys are matched by walking instance prefixes, so the short instance name is
    enough. In both ``prescribed_transport`` and ``inverse_convergence`` the NICE solver sits
    in the ``equilibrium`` submodel and is reached as ``equilibrium.nice.xml_path``. When in
    doubt, look at ``workflow_settings.ymmsl`` in the case folder, or at
    ``configuration.ymmsl`` of an earlier run.

The exercises below all use the ``prescribed_transport`` workflow with the ``105092``
scenario from :ref:`training/run_complex`, through ``cases/prescribed_transport_105092/``.

Exercise 1: change the machine description
--------------------------------------------

The machine description (``wall``, ``pf_active``, ``pf_passive``, ``iron_core``) is static
across the pulse. It is imported by the scenario's waveform configuration, under
``globals: imports:``, and handed to NICE by the waveform editor.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Point the ``105092`` case at a different occurrence of one of the machine description
        IDSs (e.g. the wall) and check whether the corresponding geometry changed in the plots.

    .. md-tab-item:: Solution

        .. code-block:: bash

            cp workflows/prescribed_transport/waveforms_no_transport.yaml my_waveforms.yaml
            # in the copy: change the machine description URI under globals: imports:

        Then point the case at your copy:

        .. code-block:: yaml

            ymmsl_version: v0.2
            settings:
              waveform_editor.waveforms: my_waveforms.yaml

        Rerun with the override stacked after the case and compare the coil/equilibrium plot
        to the previous run.

        .. note::

            The recorder draws the wall and coil outlines from its own ``rec_nice.md``
            setting, so change that one along with the waveform configuration -- otherwise the
            solve uses your new geometry while the plot still shows the old one.

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

        In your own copy of the waveform configuration, define ``ip`` as a trapezoid: ramp up
        from ``t=0`` to ``t=9``, flattop to ``t=147``, ramp down to zero by ``t=170`` (matching
        the phases of this scenario, see :ref:`training/run_complex`). Then change the flattop
        value from 3 to 3.5 MA and rerun.

    .. md-tab-item:: Solution

        .. code-block:: yaml

            targets:
              equilibrium/time_slice/global_quantities/ip:
                - {time: [0, 9, 147, 170], value: [0, -3.5e6, -3.5e6, 0]}

        (sign follows this repo's COCOS convention). Point ``waveform_editor.waveforms`` at
        the copy as in Exercise 1, rerun, and check the new flattop current on the
        equilibrium plot.

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

        Raise NICE's own logging verbosity for this run only.

    .. md-tab-item:: Solution

        .. code-block:: bash

            cp workflows/prescribed_transport/config_nice_inverse.xml my_config_nice.xml
            # in the copy: <verbose>1</verbose>

        In an override file:

        .. code-block:: yaml

            ymmsl_version: v0.2
            settings:
              equilibrium.nice.xml_path: my_config_nice.xml

        Rerun and check the ``equilibrium.nice`` log in the
        :ref:`muscle3-dashboard <training/muscle3_dashboard>`.

        ``inverse_convergence`` names its solver the same way, so the same key works there.

Exercise 6: run fewer time slices to make a run faster
------------------------------------------------------------------------

``inverse_convergence`` walks the pulse slice by slice and repeats that pass until the coil
currents stop changing. Both the number of slices and the number of passes are settings on
its outer loop: ``loop.max_slices`` (``0`` means every slice) and ``loop.max_iterations``.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Lower the number of timeslices of ``cases/inverse_convergence_105092/`` to make the
        run faster.

    .. md-tab-item:: Solution

        .. code-block:: yaml

            ymmsl_version: v0.2
            settings:
              loop.max_slices: 11
              loop.max_iterations: 1

        Rerun -- it should finish noticeably faster, with the same overall behavior at a
        coarser time resolution.

Exercise 7: change the start and end time of the simulation
-----------------------------------------------------------------------------

The ``source`` component reads the scenario's input data (spanning t=0 to t=170, see
:ref:`training/run_complex`) and accepts ``t_min``/``t_max`` settings to restrict which of
those timeslices get streamed into the workflow. Unlike Exercise 6, this changes *which* part
of the pulse is simulated rather than how finely it is sampled.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Restrict the run to the flattop phase only, from ``t=20`` to ``t=140``, skipping the
        ramp-up and ramp-down.

    .. md-tab-item:: Solution

        .. code-block:: yaml

            ymmsl_version: v0.2
            settings:
              source.t_min: 20
              source.t_max: 140

        Rerun and check that the resulting plots now start and end at flattop conditions
        instead of the ramp phases. In ``inverse_convergence`` the window is set on the outer
        loop, as ``loop.t_min`` and ``loop.t_max``.

.. todo::

    - Add a TORAX exercise: how to activate density transport and heat transport, through the
      case's ``config_torax.py`` override.
    - Add a METIS settings exercise, to sit alongside the NICE one (Exercise 5).
    - Add an exercise on implementation overriding: pointing an actor at a different build
      (EasyBuild module versus local installation) from a case or override file.
    - Add a section on taking a different DINA scenario and getting it into the PDS?
