.. _`training/configuring`:

Configuring existing workflows
==============================

What can be changed, and where it lives
---------------------------------------

Now that you have run some existing cases, we look at where the knobs live, 
and how to change them.
Almost everything you might want to change is a **setting**, and settings are grouped by
what they control:

- **The pulse design**: The waveforms and references from disk live in a
  `Waveform-Editor <https://waveform-editor.readthedocs.io/en/latest/yaml_format.html>`_
  configuration, ``waveforms.yaml`` or ``waveforms_no_transport.yaml`` in the workflow's own
  directory.
- **The solver configurations** are files of each code's own format:
  ``config_nice_inverse.xml`` for NICE, ``config_torax.py`` for TORAX. They live beside the
  workflow that uses them.
- **The workflow's own knobs** are plain yMMSL settings: how many timeslices to run, how many
  outer iterations, which part of the pulse to simulate, how much each actor logs.

Those settings reach a run from four places, and they are read in this order:

#. ``workflow.ymmsl`` -- the structure, and any defaults that belong to it
#. ``workflow_settings.ymmsl`` -- the workflow's generic settings, with this shot's paths filled in
#. ``scenario_settings.ymmsl`` -- the per-shot override from ``cases/overrides/``, if there is one
#. anything extra you pass on the command line

Keys are named after the component they belong to, so ``loop.max_slices`` is the
``max_slices`` setting of the ``loop`` component and ``equilibrium.nice.xml_path`` is the
NICE solver's config file inside the ``equilibrium`` submodel. If you are not sure what a key
is called, read ``workflow_settings.ymmsl`` in the case folder, or ``configuration.ymmsl``
in a run directory.

The exercises below all use the ``prescribed_transport`` workflow with the ``105092``
scenario, through the ``cases/prescribed_transport_105092/`` that you built in the previous section.

Exercise 1: change the plasma current value in the waveform file
----------------------------------------------------------------


.. md-tab-set::

    .. md-tab-item:: Exercise


        Take a look at the waveform YAML file for this specific case, under 
        ``cases/prescribed_transport_105092/config/waveforms_no_transport.yaml``.
        By YAML file shows that the ``ip`` target will just follow the reference input data:

        .. code-block:: yaml

            targets:
              equilibrium/time_slice/global_quantities/ip:
                - {ref: input}

        To set it yourself, we can replace it with an explicit
        `piecewise-linear tendency <https://waveform-editor.readthedocs.io/en/latest/tendencies.html#piecewise-linear-tendency>`_.

        Let's copy the waveform file and place it in the root of the PDS repository:

        .. code-block:: bash

            cp cases/prescribed_transport_105092/config/waveforms_no_transport.yaml my_waveforms.yaml

        In that copy, find the ``ip`` target and define it as a trapezoid instead: ramp up
        from ``t=0`` to ``t=9``, flattop to ``t=147``, ramp down to zero by ``t=170``. Set the
        flattop value to -3.2 MA.

        Now the case has to be told to use your copy instead of its own. It already sets that
        key -- have a look for yourself with

        .. code-block:: bash

            grep waveforms cases/prescribed_transport_105092/workflow_settings.ymmsl

        Instead of touching the original case file, we will write a second yMMSL file that sets the
        same key to a different value, and hand both to the manager. The manager reads the
        case's files first and yours last, and the last value for a key will take precedence.
        This means that only needs the one key you are changing, and everything you leave out keeps the case's
        value.

        So, three steps:

        #. Write ``my_ip.ymmsl`` with a ``settings:`` block setting
           ``waveform_editor.waveforms`` to your copy, using an absolute path.
        #. Submit the case with that file passed after the case folder.
        #. Check the new flattop current on the equilibrium plot. Does it correspond with your
           waveform?


    .. md-tab-item:: Solution

        In ``my_waveforms.yaml``, replace the ``ip`` target:

        .. code-block:: yaml

              equilibrium/time_slice/global_quantities/ip:
                - {time: [0, 9, 147, 170], value: [0, -3.2e6, -3.2e6, 0]}

        ``my_ip.ymmsl``:

        .. code-block:: yaml

            ymmsl_version: v0.2
            settings:
              waveform_editor.waveforms: /path/to/your/pds/my_waveforms.yaml

        Then pass it after the case folder:

        .. code-block:: bash

            bin/pds-run-case cases/prescribed_transport_105092 $PWD/my_ip.ymmsl

        You can look at the recorder actor to see if the plasma current corresponds to your
        set waveform.


Exercise 2: Change the ramp duration in the waveform file
---------------------------------------------------------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Continuing from the previous exercise, update your waveform YAML and stretch the 
        ramp-up from 9 to 20 seconds.

        Run the case again, and look at the plasma current. Does the plasma current correspond with your waveform?

    .. md-tab-item:: Solution

        .. code-block:: yaml

            targets:
              equilibrium/time_slice/global_quantities/ip:
                - {time: [0, 20, 147, 170], value: [0, -3.2e6, -3.2e6, 0]}

Exercise 3: Play around with the waveforms
------------------------------------------

.. md-tab-set::

    .. md-tab-item:: Exercise

        The waveform format can be used to change any of the time dependent 0D quantities,
        like the plasma current.Besides the piecewise tendency, the waveform format supports many more different
        tendencies, such as linear, smooth, or periodic curves. Have a look at the 
        `available tendencies <https://waveform-editor.readthedocs.io/en/latest/tendencies.html#available-tendencies>`_,
        and try to create your own waveform for the plasma current.

        If you want to delve deeper into how to design your own waveforms using the Waveform
        Editor, you can have a look at the 
        `Training page of the Waveform Editor <https://waveform-editor.readthedocs.io/en/latest/training/training.html>`_.

        .. warning::

            The boundary shape and coil-current still come from the original input
            data, so pushing the plasma current far from it can keep NICE-inverse from converging
            cleanly on some timeslices.

Exercise 4: increase the log level in the NICE config
---------------------------------------------------------

The exercises so far changed the pulse design. This one changes a solver, and it works
slightly differently, because NICE is not configured through yMMSL settings: it reads its own
XML file, ``config_nice_inverse.xml``, which lives beside the workflow that uses it.

.. md-tab-set::

    .. md-tab-item:: Exercise

        We will change the configuration of NICE in this exercise, namely we will raise 
        NICE's own logging verbosity, by updating the verbosity of NICE from 0 to 1:
        ``<verbose>1</verbose>``.

        Unlike the waveform configuration in Exercise 1, this file has no placeholders in it,
        so you can copy it straight out of ``workflows/`` rather than out of the case. 
        Then, make an override file to point to the new NICE config.

        Run the case and have a look at the logs of the NICE actor from the MUSCLE3 dashboard.
        Compare these to the ones from previous runs, do you see a difference?

    .. md-tab-item:: Solution

        .. code-block:: bash

            cp workflows/prescribed_transport/config_nice_inverse.xml my_config_nice.xml
            # in the copy, replace the verbosity setting: <verbose>1</verbose>

        In an override file:

        .. code-block:: yaml

            ymmsl_version: v0.2
            settings:
              equilibrium.nice.xml_path: /path/to/pds/my_config_nice.xml

        Rerun and check the ``equilibrium.nice`` log in the
        :ref:`muscle3-dashboard <training/muscle3_dashboard>`. You should see that the
        verbosity is higher than in the previous runs.

Exercise 5: run fewer time slices to make a run faster
------------------------------------------------------

``inverse_convergence`` walks the pulse one timeslice at a time, then starts over with the
coil currents it just found, until they stop changing. A full run is a bit slow, so while you are
trying settings out it is worth to reduce the number of timeslices.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Take a look at the workflow settings of the ``cases/inverse_convergence_105092/`` case. 
        Which settings do you think you can change to make the workflow finish faster? 

    .. md-tab-item:: Solution

        Two settings on its outer loop control that:

        - ``loop.max_slices``: how many timeslices one pass covers (``0`` means all time slices)
        - ``loop.max_iterations``: how many passes it makes before stopping regardless

        Lower both, and note that a run stopped early has not converged, for example:

        .. code-block:: yaml

            ymmsl_version: v0.2
            settings:
              loop.max_slices: 11
              loop.max_iterations: 1

        Rerun the case, it should finish noticeably faster now, with the same overall behavior at a
        coarser time resolution.

Exercise 6: change the start and end time of the simulation
-----------------------------------------------------------

Exercise 5 made the run coarser over the whole pulse. This one keeps the detail and
simulates less of the pulse. The pulse spans t=0 to t=170, with the flattop between roughly
t=9 and t=147 (see :ref:`training/run_complex`).

.. md-tab-set::

    .. md-tab-item:: Exercise

        Restrict the run to the flattop phase only, from ``t=20`` to ``t=140``, skipping the
        ramp-up and ramp-down.

        The ``source`` component streams the scenario data in slice by slice, so
        ``source.t_min`` and ``source.t_max`` are what decide which slices enter the workflow.

    .. md-tab-item:: Solution

        .. code-block:: yaml

            ymmsl_version: v0.2
            settings:
              source.t_min: 20
              source.t_max: 140

        Rerun and check that the resulting plots now start and end at flattop conditions
        instead of the ramp phases. In ``inverse_convergence`` the window is set on the outer
        loop, as ``loop.t_min`` and ``loop.t_max``.

Exercise 7: switch METIS between predictive and interpretative
--------------------------------------------------------------

METIS can either work out the profiles itself, or be handed them from the scenario data and
work around them. Which one you choose is a set of settings on the same ``metis_from_dina`` case.

The switches all look like ``metis.metis_external_data_<quantity>``, and there is one per
quantity METIS could take from outside: ``0`` means "compute it", ``1`` means "read it from
the input data". ``workflows/metis_from_dina/settings.ymmsl`` sets all of them to ``0``,
which is the predictive mode you ran in :ref:`training/run_complex`.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Run ``metis_from_dina`` for shot ``105084`` in interpretative mode instead, feeding
        it the electron and ion temperatures, the electron density, the effective charge and
        the ECRH from the DINA data.

        .. tip::
            You do not need to rebuild the case for this.

    .. md-tab-item:: Solution

        .. code-block:: yaml

            ymmsl_version: v0.2
            settings:
              metis.metis_external_data_electron_temperature: 1
              metis.metis_external_data_electron_density: 1
              metis.metis_external_data_ion_temperature: 1
              metis.metis_external_data_charge_effective: 1
              metis.metis_external_data_ECRH: 1

        produced the input dataset, and that does not change. Stack the override after the
        existing case folder and run it again.

        Because the profiles are now prescribed rather than predicted, they should follow the
        DINA traces closely in the validation plots. 
