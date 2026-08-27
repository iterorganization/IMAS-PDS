.. _`basic/visualization`:

Visualization
=============

The **recorder actor** is a sink-only tap: wired onto conduits that already exist in
a workflow, it does not change the coupling, it just also writes a distilled copy
of the data flowing past to disk. Point the MUSCLE3 dashboard (``m3dash``, shipped with
IMAS-MUSCLE3) at a run that includes one and it gets an extra tab, rendering that data
live while the run is still going, or afterwards.

We will use ``prescribed_transport`` for the exercises below: of the workflows in
this repo it is the simplest chain (``source -> waveform_editor -> nice_inv ->
sink``, plus a recorder), with no outer Picard loop, so re-running it after
changing a setting is fast. Both exercises below plot the same field, the
plasma's stored MHD energy -- with no extraction code in exercise 1 (an empty
``State``, filled in automatically), by hand in exercise 2 (extending a real
``extract`` method) -- and each renders it two ways: as a static
``matplotlib`` figure and as an interactive HoloViews plot, since a
``Plotter`` is free to mix both (both are just Panel objects as far as the
dashboard is concerned).

The recorder actor
--------------------

A recorder is wired as an extra receiver on conduits that already feed another
component, for example ``sink``. Every connected ``S`` port is its own timeline,
named after the IDS it carries. This is ``rec_nice`` from
``workflows/prescribed_transport/workflow.ymmsl``:

.. code-block:: yaml

    components:
      rec_nice: {description: distill recorder (NICE inverse outputs), implementation: recorder, ports: {s: [equilibrium_in, pf_active_in]}}

    conduits:
      nice_inv.equilibrium_out: [sink.equilibrium_in, rec_nice.equilibrium_in]
      nice_inv.pf_active_out: [sink.pf_active_in, rec_nice.pf_active_in]

    implementations:
      recorder:
        executable: python
        args: -u -m imas_muscle3.actors.recorder_component

Each received IDS is reduced to plot-ready ``xarray`` datasets by a ``config``
file, and appended to a Zarr store -- one per outer-loop iteration, at
``<store_path>/<port>/<iteration_number>.zarr``. ``config`` is mandatory --
in particular, the dashboard's ``Plotter`` always has to be hand-written, so
a file always has to exist:

.. code-block:: yaml

    settings:
      rec_nice.config: /work/projects/pds/pds/visualization/nice_inv.py

The config file defines the extraction logic in one of two ways: a plain
``def extract(ids) -> dict[str, xarray.Dataset]`` function if you only need to
record data, or a ``State`` class (subclassing
``imas_muscle3.visualization.base_state.BaseState``) implementing
``extract(self, ids)``. Add a ``Plotter`` class alongside it (subclassing
``imas_muscle3.visualization.base_plotter.BasePlotter``, implementing
``get_dashboard()``) and the same file also tells the dashboard how to plot what
was recorded -- the recorder only ever reads the ``State`` half.

The ``State`` half of that can itself be automatic (exercise 1 below): if it
doesn't implement its own ``extract``, and the recorder's
``automatic_extract`` setting is on, extraction falls back to
``BaseState.automatic_extract`` -- the same discovery-and-extract logic the
live visualization actor's own automatic mode uses.

.. note::

    A fresh ``State`` instance is built for every message the recorder receives,
    so ``extract`` only accumulates *within* one call. Both message
    granularities still end up fully recorded: a live one-slice-per-message
    stream gets appended instant by instant by the recorder's own store; a
    whole-trace-per-message stream (e.g. one message per Picard iteration,
    looping over ``ids.time_slice`` inside ``extract``) gets appended
    trace by trace instead.

Running the workflow and opening the dashboard
-------------------------------------------------

.. code-block:: console

    bash bin/run_case.sbatch 105084_prescribed

``run_case.sbatch`` pins the run directory to ``cases/runs/<case>``, so the output lands
somewhere predictable. Then, in a separate terminal with the dashboard's own virtual
environment activated:

.. code-block:: console

    m3dash open cases/runs/

Click the run, and a ``rec_nice`` tab appears once the recorder has written its
first store -- no ymmsl parsing needed, the dashboard finds it by its on-disk
layout.

Exercise 1: automatic mode
----------------------------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Plot the equilibrium's MHD energy without writing any extraction
        code. A ``Plotter`` still has to be hand-written -- there's no way
        around that -- but its ``State`` doesn't: leave it empty and let
        ``automatic_extract`` fill it in.

        Write a new config file with a bare ``State`` (no ``extract``
        override) and a ``Plotter`` that plots one named field, and point
        ``rec_nice.config`` at it in
        ``cases/105084_prescribed.ymmsl``. Turn on
        ``rec_nice.automatic_extract`` and restrict it to just that field with
        ``rec_nice.automatic_extract_fields``, re-run the workflow, and open
        the ``rec_nice`` tab.

        .. note::

            Note the field's dotted form,
            ``equilibrium.time_slice[0].global_quantities.energy_mhd``, not
            the slashed form you'll see elsewhere,
            ``equilibrium/time_slice[0]/global_quantities/energy_mhd``:
            ``BaseState.automatic_extract`` discovers quantities using the
            slashed form, but Zarr rejects ``/`` in a variable name, so a
            bare ``State``'s automatic fallback flattens it to dots before
            recording -- ``automatic_extract_fields``, and the field your
            ``Plotter`` looks up, both have to match that same dotted form.

            This also is not the same as the live visualization actor's
            interactive variable-picker dropdown: that needs the raw IDS to
            discover quantities from, and the dashboard here only ever sees
            data that has already been distilled and written to a store.

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

        .. code-block:: yaml

            settings:
              rec_nice.config: /work/projects/pds/pds/visualization/auto_explore.py
              rec_nice.automatic_extract: true
              rec_nice.automatic_extract_fields: equilibrium.time_slice[0].global_quantities.energy_mhd

        ``State`` has no ``extract`` override, so with ``automatic_extract:
        true`` set, the recorder fills it in via ``BaseState.automatic_extract``
        -- discovering and extracting every time-dependent quantity of each
        received IDS, no IDS-specific code required.
        ``automatic_extract_fields`` then drops everything but ``energy_mhd``
        before writing to disk; without it, every discovered quantity would
        be recorded, and ``Plotter`` would still only ever plot the one field
        it names.

        The ``rec_nice`` tab now shows a matplotlib/HoloViews pair for
        ``energy_mhd``, without a single line of extraction code.

Exercise 2: an explicit extract method
-----------------------------------------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Point ``rec_nice.config`` back at the shipped default,
        ``visualization/nice_inv.py``, re-run, and compare its ``rec_nice`` tab
        to exercise 1's: a poloidal-flux contour with separatrix and X/O-points,
        the coil geometry and per-coil current curves, ff'/p' profiles, and
        Ip/beta_tor waveforms -- all purpose-built, at the cost of ``nice_inv.py``
        having to know exactly which IDS paths to reach for, and all of it
        interactive HoloViews plots (backed by bokeh): pan, zoom and hover over
        the contour and profile plots to see this for yourself.

        Now add exercise 1's field, ``energy_mhd``, here too, but by hand this
        time: extract ``equilibrium/time_slice[*]/global_quantities/energy_mhd``
        in ``State._extract_equilibrium_slice``, plot it as an interactive
        HoloViews curve next to ``ip``/``beta_tor``, and also fold it into a
        small static matplotlib summary panel alongside the other two.

    .. md-tab-item:: Solution

        .. code-block:: yaml

            settings:
              rec_nice.config: /work/projects/pds/pds/visualization/nice_inv.py

        In ``State._extract_equilibrium_slice``, add ``energy_mhd`` to the
        existing ``ip_beta_tor`` dataset:

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

        In ``Plotter``, add the interactive HoloViews curve, next to
        ``plot_beta_tor``:

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

        Add ``import matplotlib.pyplot as plt`` at the top of the file (it is
        already imported for the contour calculation), then add a static
        matplotlib summary of all three global quantities together:

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

        Add both to the dashboard layout in ``get_dashboard``:

        .. code-block:: python

            energy_mhd = hv.DynamicMap(self.plot_energy_mhd)
            ...
            pn.Row(ip, beta_tor, energy_mhd),
            self.plot_summary_static,

        ``plot_summary_static`` is not wrapped in ``hv.DynamicMap`` -- that
        wrapper is for HoloViews elements. A plain ``@param.depends``-decorated
        method returning a Panel object (here, a ``Matplotlib`` pane) can be
        placed directly in the layout and Panel re-renders it the same way.
