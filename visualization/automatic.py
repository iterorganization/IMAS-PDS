"""Generic recorder plot file: pick any recorded variable from a list and plot it.

Point a recorder at this file and it needs no code of its own::

    equilibrium.recorder_equilibrium.config: ${PDS_REPO}/visualization/automatic.py
    equilibrium.recorder_equilibrium.automatic_extract: true

The recorder then discovers every time-dependent 0D/1D/2D quantity in each IDS it
receives and records it, and the dashboard tab gives you a filter box, a variable
selector and an "Add Plot" button to open any of them. This is the same UI
``BasePlotter`` builds for the live visualization actor, which is why there is so little
here: ``State`` only has to switch it on and say what the recording contains.

Recording everything is slow, and it stays slow for as long as the tab is open: the
dashboard re-reads the whole store every time it polls, so the cost grows with the number
of variables, not with how many you plot. An equilibrium alone has some 4500 of them.
Say what you want and the run and the tab both stay quick::

    equilibrium.recorder_equilibrium.automatic_extract_fields: >
      equilibrium.time_slice[0].global_quantities.energy_mhd
      equilibrium.time_slice[0].global_quantities.ip

For a purpose-built tab instead -- flux contours, coil geometry, chosen profiles --
write a config with its own ``extract`` and ``Plotter``; ``nice_inv.py`` is the example.
"""

import logging
from dataclasses import dataclass

import numpy as np
import panel as pn
import param
import xarray as xr
from imas_muscle3.visualization.base_plotter import BasePlotter
from imas_muscle3.visualization.base_state import BaseState, Dim, Variable

logger = logging.getLogger()


@dataclass
class RecordedVariable(Variable):
    """A variable as it sits in a recorder store.

    Live, a variable is known as ``<ids>/<path>``. Zarr rejects ``/`` in a name,
    so the recorder stores it with ``.`` instead, and that stored name is what
    the datasets are keyed by. Reporting it unchanged as ``full_path`` lets the
    plotter address the data directly, with nothing to rename on the way.
    """

    @property
    def full_path(self) -> str:
        return self.path


def _describe(stored_name: str, ds: xr.Dataset) -> RecordedVariable:
    """Work out what ``ds`` holds, from its shape.

    Live, this comes from the IDS itself. Reading a finished recording there is
    no IDS left, so the dataset has to say it: a variable stored against time
    alone is 0D, and every further coordinate sits beside it as
    ``<stored_name>_<coord>``, in the data's own dimension order.
    """
    stored = set(map(str, ds.data_vars))
    coord_names = [
        str(dim) for dim in ds[stored_name].dims[1:] if f"{stored_name}_{dim}" in stored
    ]
    dimension = {1: Dim.ONE_D, 2: Dim.TWO_D}.get(len(coord_names), Dim.ZERO_D)
    return RecordedVariable(
        source_name=stored_name.split(".", 1)[0],
        path=stored_name,
        dimension=dimension,
        coord_names=coord_names,
    )


class State(BaseState):
    """Recorded data, described well enough for the picker to offer it.

    ``auto=True`` is what makes :class:`BasePlotter` build that picker.
    """

    def __init__(self, md_dict: dict) -> None:
        super().__init__(md_dict, auto=True)
        self._described: dict[str, RecordedVariable] = {}

    @param.depends("data", watch=True, on_init=True)
    def _index_recorded_data(self) -> None:
        """Describe variables the store has gained since the last look.

        The dashboard hands over the whole store on every poll, so this runs
        again and again while a run is live. It must therefore do as little as
        possible, and in particular must not touch ``data``: everything
        watching it -- including the plotter's own time-axis update, which
        reads every dataset -- would run a second time for each poll.
        """
        fresh = [name for name in map(str, self.data) if name not in self._described]
        if not fresh:
            return

        for name in fresh:
            self._described[name] = _describe(name, self.data[name])
        logger.info(
            "automatic: %d recorded variable(s) available (%d new)",
            len(self._described),
            len(fresh),
        )
        self.variables = dict(self._described)


class Plotter(BasePlotter):
    """Every plot here is opened by hand from the picker, so the fixed part of
    the tab is only a hint about how to use it."""

    @param.depends("_state.data", watch=True)
    def _update_on_new_data(self) -> None:
        """Refresh the time axis from the plots on screen, not the whole store.

        The inherited version reads ``time`` off every recorded dataset. Live
        that is a handful; here it is however many variables were recorded, on
        every poll, and each read is a lazily-opened Zarr store on shared
        storage -- so the tab gets slower the more was recorded, whether or not
        anything is being plotted.

        Every variable in a recorder store came from the same message stream
        and so shares its time base. Reading the ones actually plotted (or any
        one of them, before the first plot is opened) gives the same axis for a
        fixed, small cost.
        """
        data = self._state.data if self._state else {}
        if not data:
            return

        plotted = [
            data[var.full_path]
            for var in self._state.variables.values()
            if var.is_visualized and var.full_path in data
        ]
        for source in plotted or [next(iter(data.values()))]:
            times = [float(t) for t in np.asarray(source.time.values)]
            if times:
                break
        else:
            return

        self.time_slider_widget.options = sorted(set(times))
        if self._live_view:
            self.active_state = self._state
            self.time = times[-1]

    def get_dashboard(self) -> pn.viewable.Viewable:
        return pn.pane.Markdown(
            "Filter the list, choose a variable and press **Add Plot**. "
            "Plots open as panels you can move, resize and close; "
            "**Close All Plots** clears them.\n\n"
            "Uncheck **Live View** to scrub back through time with the player."
        )
