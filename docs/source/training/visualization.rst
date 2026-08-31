.. _`training/visualization`:

Visualizing workflows
=====================

.. TODO: reformat and clean up

You have already used the recorder plots: in :ref:`training/run_complex` the dashboard grew
a ``recorder_equilibrium`` tab while the run was going, and you watched the equilibrium fill
in slice by slice.

Those plots are not built into the dashboard. Each one comes from a small Python file that
ships with the workflow, and you can change it, or write your own. That is what this chapter
is about: getting the dashboard to show *you* what you want to see, rather than what someone
else decided to plot.

How a recorder plot gets made
-----------------------------

A **recorder** is an extra listener on data that is already moving between two actors. It
does not sit in the way of anything: the component that was receiving the data still
receives exactly the same thing, and the recorder quietly writes a copy for the dashboard to
draw.

What the recorder does with that copy is decided by a single **config file**, named in the
settings like any other configuration you met in :ref:`training/configuring`:

.. code-block:: yaml

    equilibrium.recorder_equilibrium.config: .../visualization/nice_inv.py

Note the full name. In ``prescribed_transport`` the recorder sits inside the ``equilibrium``
submodel, so its settings are written ``equilibrium.recorder_equilibrium.<setting>``. Shorten
it and the setting is simply never found, with no error to tell you so. Copy the form already
in your case's ``workflow_settings.ymmsl`` and you cannot get this wrong.

The available visualization scripts can be found in the ``visualization`` directory in the PDS repository. As a start, take a look at the ``nice_inv.py`` file, take a look at the different classes.

A visualization file has two halves, and it is worth keeping them apart in your head:

- a ``State`` class, which says **what to record** - which numbers to pull out of each
  IDS that goes past;
- a ``Plotter`` class, which says **how to draw it** - the curves, images and layout that
  become the tab you see.

The recorder itself only ever reads the ``State`` half. The dashboard reads the ``Plotter``
half.

Plots can be written with either `matplotlib <https://matplotlib.org/>`_, which you
might already know, or `HoloViews <https://holoviews.org/>`_, which gives you additional interactive abilities.

Setting up
----------

We will use ``prescribed_transport`` throughout. It is the shortest workflow in the repo and
has no outer loop, so a re-run after every change costs you a minute rather than a coffee
break:

.. code-block:: bash

    bin/pds-create-case prescribed_transport 105084
    bin/pds-run-case cases/prescribed_transport_105084

and in the terminal where you keep the dashboard:

.. code-block:: bash

    m3dash open cases/runs/

Click the run, and the ``recorder_equilibrium`` tab appears as soon as the recorder has
written something.

Exercise 1: plot a field without writing any extraction code
------------------------------------------------------------

The recorder can work out for itself which quantities an IDS carries,
so for a first plot you do not have to write any extraction code at all. You only have to
name the field you want and say how to draw it.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Plot the plasma's stored MHD energy over time.

        Write a config file with an empty ``State`` (no ``extract`` method) and a
        ``Plotter`` that draws that one field. Then point the recorder at your file and turn
        automatic extraction on, with these three settings:

        .. code-block:: yaml

            equilibrium.recorder_equilibrium.config: /path/to/your/config.py
            equilibrium.recorder_equilibrium.automatic_extract: true
            equilibrium.recorder_equilibrium.automatic_extract_fields: equilibrium.time_slice[0].global_quantities.energy_mhd

        Add them to ``workflow_settings.ymmsl`` in your case folder, the way you changed
        settings in :ref:`training/configuring`. Re-run and open the tab.

    .. md-tab-item:: Hint

        Write the field name with **dots**, not slashes:
        ``equilibrium.time_slice[0].global_quantities.energy_mhd``. You will see the slashed
        form elsewhere in IMAS, but the recorder stores it with dots, and the name your
        ``Plotter`` looks up has to match the name it was stored under.

        ``automatic_extract_fields`` is a filter. Leave it out and everything the recorder
        found gets written; your plot would still show only the field it names, but the run
        would write a lot more than you need.

    .. md-tab-item:: Solution

        .. code-block:: python

            # visualization/auto_explore.py
            import holoviews as hv
            import matplotlib.pyplot as plt
            import panel as pn

            from imas_muscle3.visualization.base_plotter import BasePlotter
            from imas_muscle3.visualization.base_state import BaseState

            FIELD = "equilibrium.time_slice[0].global_quantities.energy_mhd"


            class State(BaseState):
                pass  # automatic_extract fills this in


            class Plotter(BasePlotter):
                def get_dashboard(self):
                    return pn.bind(self._render, self._state.param.data)

                def _render(self, data):
                    ds = data.get(FIELD)
                    if ds is None:
                        return pn.pane.Markdown("*Waiting for data...*")

                    fig, ax = plt.subplots(figsize=(5, 3))
                    ax.plot(ds.time, ds[FIELD])
                    ax.set_title(f"{FIELD} (matplotlib)")
                    ax.set_xlabel("time")
                    fig.tight_layout()
                    static_pane = pn.pane.Matplotlib(fig, tight=True)
                    plt.close(fig)  # the pane rasterized it; drop the figure

                    interactive_pane = hv.Curve(ds, "time", FIELD).opts(
                        width=450,
                        height=250,
                        title=f"{FIELD} (holoviews)",
                        tools=["hover"],
                    )
                    return pn.Row(static_pane, interactive_pane)

        and in the case's ``workflow_settings.ymmsl``:

        .. code-block:: yaml

            settings:
              equilibrium.recorder_equilibrium.config: /path/to/pds/visualization/auto_explore.py
              equilibrium.recorder_equilibrium.automatic_extract: true
              equilibrium.recorder_equilibrium.automatic_extract_fields: equilibrium.time_slice[0].global_quantities.energy_mhd

        The tab now shows ``energy_mhd`` twice, once through matplotlib and once through
        HoloViews, and you did not write a line of code that knows anything about the
        equilibrium IDS.

Exercise 2: add a field to a real config
----------------------------------------

Automatic extraction is convenient, but it is generic: it can only give you plain curves of
whatever numbers it happened to find. A purpose-built config knows what the data *means*,
and ``visualization/nice_inv.py``, the one ``prescribed_transport`` ships with, is a good
example. Its tab gives you a poloidal flux contour with the separatrix and the X- and
O-points, the coil geometry with a current curve per coil, and the ff'/p' profiles.

The cost is that it has to be told exactly where to look. This exercise is about paying that
cost once: adding one field by hand, to both halves of the file.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Point the recorder back at the shipped config:

        .. code-block:: yaml

            equilibrium.recorder_equilibrium.config: /path/to/pds/visualization/nice_inv.py

        Re-run and compare this tab with the one from Exercise 1: pan, zoom and hover over
        the contour and the profiles.

        Then add ``energy_mhd`` here too, by hand: record it alongside ``ip`` and
        ``beta_tor``, draw it as a curve next to them, and add a small matplotlib panel
        showing all three together.

    .. md-tab-item:: Hint

        Two halves, so two edits. The recording happens in ``State``, where the other global
        quantities are already gathered into one dataset. Add yours to it. The drawing
        happens in ``Plotter``, where each plot is its own small method that gets listed in
        the layout at the end.

        The IDS path you need is
        ``equilibrium/time_slice[*]/global_quantities/energy_mhd``.

    .. md-tab-item:: Solution

        In ``State._extract_equilibrium_slice``, add ``energy_mhd`` to the dataset that
        already carries ``ip`` and ``beta_tor``:

        .. code-block:: python

            ip_beta_tor = xr.Dataset(
                {
                    "ip": ("time", [-1 * ts.global_quantities.ip]),
                    "beta_tor": ("time", [ts.global_quantities.beta_tor]),
                    "energy_mhd": ("time", [ts.global_quantities.energy_mhd]),
                },
                coords={
                    "time": [ids.time[itime]],
                },
            )

        In ``Plotter``, add an interactive curve next to ``plot_beta_tor``:

        .. code-block:: python

            @param.depends("time")
            def plot_energy_mhd(self):
                state = self.active_state.data.get("equilibrium")
                xlabel = "Time [s]"
                ylabel = "energy_mhd"

                if state:
                    mask = state.time <= self.time
                    time = state.time[mask].values
                    energy_mhd = state.energy_mhd.sel(time=mask).values
                    title = "MHD energy over time"
                else:
                    time = np.array([0])
                    energy_mhd = np.array([0])
                    title = "Waiting for data..."

                return hv.Curve((time, energy_mhd), xlabel, ylabel).opts(
                    framewise=True, height=200, width=600, title=title
                )

        Then a static matplotlib panel with all three together:

        .. code-block:: python

            @param.depends("time")
            def plot_summary_static(self):
                state = self.active_state.data.get("equilibrium")
                fig, ax = plt.subplots(figsize=(6, 3))
                if state:
                    mask = state.time <= self.time
                    time = state.time[mask].values
                    ax.plot(time, state.ip.sel(time=mask).values, label="ip")
                    ax.plot(
                        time, state.beta_tor.sel(time=mask).values, label="beta_tor"
                    )
                    ax.plot(
                        time,
                        state.energy_mhd.sel(time=mask).values,
                        label="energy_mhd",
                    )
                    ax.legend()
                ax.set_xlabel("Time [s]")
                ax.set_title("ip / beta_tor / energy_mhd (matplotlib summary)")
                fig.tight_layout()
                pane = pn.pane.Matplotlib(fig, tight=True)
                plt.close(fig)
                return pane

        and list both in the layout in ``get_dashboard``:

        .. code-block:: python

            energy_mhd = hv.DynamicMap(self.plot_energy_mhd)
            ...
            pn.Row(ip, beta_tor, energy_mhd),
            self.plot_summary_static,

        Only the HoloViews plot is wrapped in ``hv.DynamicMap``. The matplotlib one can go
        into the layout as it is.

Exercise 3: record something nobody is recording yet
-----------------------------------------------------

The two exercises above both plotted data that a recorder was already receiving. Sooner or
later you will want to look at something no recorder is wired to, and then there are two
halves to the job: tap the data, and describe how to plot it.

The tap is a recorder component with an ``S`` port, listed as an extra receiver on a conduit
that already exists. Adding one means editing ``workflow.ymmsl``, but not the workflow's
own. As in :ref:`training/configuring`, the copy inside ``cases/<case>/`` is the one to
change: the component appears in this run and nowhere else, and the template you built the
case from is untouched.

.. md-tab-set::

    .. md-tab-item:: Exercise

        In ``prescribed_transport``, the waveform editor's output goes to NICE and nothing
        else looks at it. Put a recorder on it, so you can see what NICE is actually being
        asked for, next to what it produced.

        You will need three things:

        1. a component with an ``S`` port for the IDS you want, in the case's
           ``workflow.ymmsl``;
        2. that component added as a second receiver on the existing conduit;
        3. a config file for it, and a setting pointing at it.

    .. md-tab-item:: Hint

        Copy the shape of ``recorder_equilibrium`` from the top of this page for the wiring, and the
        shape of ``visualization/nice_inv.py`` for the config: a ``State`` with an
        ``extract`` that returns one ``xarray.Dataset``, and a ``Plotter`` with a single
        curve, is enough. Start from the smallest thing that renders, then add fields.

        A conduit takes a list of receivers, so adding yours means turning one target into
        two, not replacing it.

    .. md-tab-item:: Solution

        Sketch, in the case's own ``workflow.ymmsl``:

        .. code-block:: yaml

            components:
              recorder_target: {implementation: recorder, ports: {s: [equilibrium_in]}}

            conduits:
              waveform_editor.equilibrium_out: [equilibrium.equilibrium_in, recorder_target.equilibrium_in]

        and in the case's ``workflow_settings.ymmsl``:

        .. code-block:: yaml

            settings:
              recorder_target.config: /path/to/pds/my_target_config.py

        Now the dashboard grows a ``recorder_target`` tab next to ``recorder_equilibrium``, and you can watch
        the requested boundary and the solved one side by side while the run goes.

        Two things are worth taking away from this. A recorder never changes the coupling: the
        component that was already receiving still receives exactly what it did before, so
        adding one cannot change the physics. And because the recorder finds its data by its
        on-disk layout, the dashboard picks the new tab up on its own, so there is nothing
        to register anywhere.

Watching a run you are not sitting on
--------------------------------------

One practical note for SDCC, since the real cases from :ref:`training/run_complex` do not run
where you are looking at them.

The dashboard is a web application, so it has to open a browser somewhere with a screen,
which on SDCC means inside your NoMachine session, not over a plain SSH connection. The
simulation, meanwhile, is on a compute node with no screen at all.

That works out because they never talk to each other directly. The job writes its run
directory to the shared filesystem, and the dashboard reads it from there:

.. code-block:: bash

    # in a NoMachine terminal, on the login node
    m3dash open cases/runs/

    # in another terminal, submitting to a compute node
    bin/pds-run-case cases/prescribed_transport_105092

Start the dashboard first and leave it running: it picks up new runs as they appear, and
the recorder plots fill in live while the job is on the compute node. If a tab stays empty,
the usual reason is simply that the recorder has not written its first store yet, which for
these workflows means the first solve is still going.
