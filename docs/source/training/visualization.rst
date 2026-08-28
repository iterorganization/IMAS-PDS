.. _`training/visualization`:

Visualizing workflows
=====================

.. TODO: reformat and clean up

The **recorder actor** is a sink-only tap: wired onto conduits that already exist in
a workflow, it does not change the coupling, it just also writes a distilled copy
of the data flowing past to disk. Point the :ref:`muscle3-dashboard <training/muscle3_dashboard>` at a run that
includes one and it gets an extra tab, rendering that data live while the run is
still going, or afterwards.

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
named after the IDS it carries. This is ``recorder_equilibrium`` from
``workflows/prescribed_transport/workflow.ymmsl``:

.. code-block:: yaml

    components:
      recorder_equilibrium: {description: distill recorder (NICE inverse outputs), implementation: recorder, ports: {s: [equilibrium_in, pf_active_in]}}

    conduits:
      nice_inv.equilibrium_out: [sink.equilibrium_in, recorder_equilibrium.equilibrium_in]
      nice_inv.pf_active_out: [sink.pf_active_in, recorder_equilibrium.pf_active_in]

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
      recorder_equilibrium.config: ${PDS_REPO}/visualization/nice_inv.py

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
``BaseState.automatic_extract``.

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

.. code-block:: bash

    bin/pds-create-case prescribed_transport 105084
    bin/pds-run-case cases/prescribed_transport_105084

Then, in a separate terminal with the dashboard's own virtual environment
activated (see :ref:`muscle3-dashboard <training/muscle3_dashboard>`):

.. code-block:: bash

    m3dash open cases/runs/

Click the run, and a ``recorder_equilibrium`` tab appears once the recorder has written its
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
        ``recorder_equilibrium.config`` at it in
        ``workflows/prescribed_transport/settings.ymmsl``. Turn on
        ``recorder_equilibrium.automatic_extract`` and restrict it to just that field with
        ``recorder_equilibrium.automatic_extract_fields``, re-run the workflow, and open
        the ``recorder_equilibrium`` tab.

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
              recorder_equilibrium.config: ${PDS_REPO}/visualization/auto_explore.py
              recorder_equilibrium.automatic_extract: true
              recorder_equilibrium.automatic_extract_fields: equilibrium.time_slice[0].global_quantities.energy_mhd

        ``State`` has no ``extract`` override, so with ``automatic_extract:
        true`` set, the recorder fills it in via ``BaseState.automatic_extract``
        -- discovering and extracting every time-dependent quantity of each
        received IDS, no IDS-specific code required.
        ``automatic_extract_fields`` then drops everything but ``energy_mhd``
        before writing to disk; without it, every discovered quantity would
        be recorded, and ``Plotter`` would still only ever plot the one field
        it names.

        The ``recorder_equilibrium`` tab now shows a matplotlib/HoloViews pair for
        ``energy_mhd``, without a single line of extraction code.

Exercise 2: an explicit extract method
-----------------------------------------

.. md-tab-set::

    .. md-tab-item:: Exercise

        Point ``recorder_equilibrium.config`` back at the shipped default,
        ``visualization/nice_inv.py``, re-run, and compare its ``recorder_equilibrium`` tab
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
              recorder_equilibrium.config: ${PDS_REPO}/visualization/nice_inv.py

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

Exercise 3: record something nobody is recording yet
-----------------------------------------------------

The two exercises above both plotted data that a recorder was already receiving. Sooner or
later you will want to look at something no recorder is wired to, and then there are two
halves to the job: tap the data, and describe how to plot it.

The tap is a recorder component with an ``S`` port, listed as an extra receiver on a conduit
that already exists. Adding one means editing ``workflow.ymmsl`` -- but you do not have to
edit the shared one. Remember from :ref:`training/understanding` that a case folder is a
frozen copy: the ``workflow.ymmsl`` inside ``cases/<case>/`` is yours alone, so you can add a
component there and nobody else's runs change.

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
        shape of ``visualization/nice_inv.py`` for the config -- a ``State`` with an
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

        and in an override file stacked after the case:

        .. code-block:: yaml

            ymmsl_version: v0.2
            settings:
              recorder_target.config: my_target_config.py

        Now the dashboard grows a ``recorder_target`` tab next to ``recorder_equilibrium``, and you can watch
        the requested boundary and the solved one side by side while the run goes.

        Two things are worth taking away from this. A recorder never changes the coupling: the
        component that was already receiving still receives exactly what it did before, so
        adding one cannot change the physics. And because the recorder finds its data by its
        on-disk layout, the dashboard picks the new tab up on its own -- there is nothing to
        register anywhere.

Watching a run you are not sitting on
--------------------------------------

One practical note for SDCC, since the real cases from :ref:`training/run_complex` do not run
where you are looking at them.

The dashboard is a web application, so it has to open a browser somewhere with a screen --
which on SDCC means inside your NoMachine session, not over a plain SSH connection. The
simulation, meanwhile, is on a compute node with no screen at all.

That works out because they never talk to each other directly. The job writes its run
directory to the shared filesystem, and the dashboard reads it from there:

.. code-block:: bash

    # in a NoMachine terminal, on the login node
    m3dash open cases/runs/

    # in another terminal, submitting to a compute node
    bin/pds-run-case cases/prescribed_transport_105092

Start the dashboard first and leave it running -- it picks up new runs as they appear, and
the recorder plots fill in live while the job is on the compute node. If a tab stays empty,
the usual reason is simply that the recorder has not written its first store yet, which for
these workflows means the first solve is still going.
