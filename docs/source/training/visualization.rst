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

The available visualization scripts can be found in the ``visualization`` directory in the PDS repository.
As a start, take a look at the ``nice_inv.py`` file, take a look at the different classes.

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

Exercise 2: the same plot, extracted explicitly
------------------------------------------------

Automatic extraction is convenient, but it is generic: it can only give you plain curves of
whatever numbers it happened to find. A purpose-built config knows what the data *means*,
because it says so itself, in a ``State.extract`` method you write by hand instead of
turning ``automatic_extract`` on.

This exercise plots the same field as Exercise 1, the same way, so the only thing that
changes is where the data comes from.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Plot the plasma's stored MHD energy over time again, but this time give ``State`` an
        explicit ``extract`` method that reads ``energy_mhd`` off the incoming equilibrium
        IDS itself, instead of turning on ``automatic_extract``. Keep the same ``Plotter``
        from Exercise 1.

    .. md-tab-item:: Hint

        ``extract`` receives the IDS as its ``message`` argument. Pull the value out with
        plain attribute access -- ``message.time_slice[0].global_quantities.energy_mhd`` --
        and store it in ``self.data`` under the same key your ``Plotter`` already looks up.

    .. md-tab-item:: Solution

        .. code-block:: python

            # visualization/explicit_extract.py
            import holoviews as hv
            import matplotlib.pyplot as plt
            import panel as pn
            import xarray as xr

            from imas_muscle3.visualization.base_plotter import BasePlotter
            from imas_muscle3.visualization.base_state import BaseState

            FIELD = "equilibrium.time_slice[0].global_quantities.energy_mhd"


            class State(BaseState):
                def extract(self, message):
                    current_time = float(message.time[0])
                    value = float(message.time_slice[0].global_quantities.energy_mhd)
                    new_ds = xr.Dataset(
                        {FIELD: ("time", [value])}, coords={"time": [current_time]}
                    )
                    if FIELD in self.data:
                        self.data[FIELD] = xr.concat(
                            [self.data[FIELD], new_ds], dim="time"
                        )
                    else:
                        self.data[FIELD] = new_ds


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

        and in the case's ``workflow_settings.ymmsl``, point the recorder at this file
        instead -- there is no ``automatic_extract`` setting to turn on this time:

        .. code-block:: yaml

            settings:
              equilibrium.recorder_equilibrium.config: /path/to/pds/visualization/explicit_extract.py

        The tab looks exactly like the one from Exercise 1. What changed is not the plot but
        who decided what to record: in Exercise 1 the recorder discovered it for you, here
        ``State.extract`` says so directly.
