"""
Plasmaless coil + vessel model (plasmaless_controller workflow), same panels as
plot_plasmaless_imas.m of the plasmaless repository:
- (a) CS/PF superconducting coil currents [A] (pf_active.coil(:).current)
- (b) VS resistive coil currents [kA] (coils whose name starts with "VS")
- (c) passive loop currents [kA] (pf_passive.loop(:).current)
plus the coil voltages carried by the same pf_active messages:
- (d) CS/PF and (e) VS coil voltages [V]. The plasmaless actor echoes the voltages
  it applied over the step ending at the message time, i.e. the controller's
  command of the previous exchange (the scenario voltage at t0 for the first step).

Recorder ports: pf_active_in and pf_passive_in, wired as extra receivers on
plasmaless.pf_active_o_i and plasmaless.pf_passive_o_i (one slice per message).
"""

import logging

import holoviews as hv
import numpy as np
import panel as pn
import param
import xarray as xr
from imas_muscle3.visualization.base_plotter import BasePlotter
from imas_muscle3.visualization.base_state import BaseState

logger = logging.getLogger()

_HEIGHT = 260
_WIDTH = 900


def _series(values, ntime):
    """One value per time point, NaN when the quantity is not filled."""
    arr = np.asarray(values, dtype=float).ravel()
    if arr.size != ntime:
        return np.full(ntime, np.nan)
    return arr


def _append(current, new):
    """Concat along time; a repeated time keeps the latest values."""
    if current is None:
        return new
    combined = xr.concat([current, new], dim="time", join="outer")
    return combined.drop_duplicates("time", keep="last")


class State(BaseState):
    def extract(self, message):
        if message.metadata.name == "pf_active":
            self._extract_pf_active(message)
        elif message.metadata.name == "pf_passive":
            self._extract_pf_passive(message)

    def _extract_pf_active(self, ids):
        time = np.asarray(ids.time, dtype=float)
        if time.size == 0 or len(ids.coil) == 0:
            logger.warning("pf_active without time or coils, skipped.")
            return
        # (ncoil, ntime): one slice per message from the actor, any length works.
        current = np.array([_series(c.current.data, time.size) for c in ids.coil])
        voltage = np.array([_series(c.voltage.data, time.size) for c in ids.coil])
        names = np.array([str(c.name) for c in ids.coil])
        new = xr.Dataset(
            {
                "current": (("time", "coil"), current.T),
                "voltage": (("time", "coil"), voltage.T),
            },
            coords={"time": time, "coil": names},
        )
        self.data["pf_active"] = _append(self.data.get("pf_active"), new)

    def _extract_pf_passive(self, ids):
        time = np.asarray(ids.time, dtype=float)
        if time.size == 0 or len(ids.loop) == 0:
            logger.warning("pf_passive without time or loops, skipped.")
            return
        current = np.array([_series(lp.current, time.size) for lp in ids.loop])
        names = np.array([str(lp.name) for lp in ids.loop])
        new = xr.Dataset(
            {"current": (("time", "loop"), current.T)},
            coords={"time": time, "loop": names},
        )
        self.data["pf_passive"] = _append(self.data.get("pf_passive"), new)


class Plotter(BasePlotter):
    def get_dashboard(self):
        return pn.Column(
            hv.DynamicMap(self.plot_sc_currents),
            hv.DynamicMap(self.plot_vs_currents),
            hv.DynamicMap(self.plot_passive_currents),
            hv.DynamicMap(self.plot_sc_voltages),
            hv.DynamicMap(self.plot_vs_voltages),
        )

    def _pf_active_until_now(self, vs):
        """(time, values, names) of the selected coils, up to the slider time."""
        state = self.active_state.data.get("pf_active")
        if state is None:
            return None
        names = [str(n) for n in state.coil.values]
        idx = [i for i, n in enumerate(names) if n.upper().startswith("VS") == vs]
        mask = (state.time <= self.time).values
        return state.time.values[mask], state.isel(coil=idx, time=mask), names, idx

    def _coil_overlay(self, title, var, ylabel, scale, vs):
        selected = self._pf_active_until_now(vs)
        if selected is None or not selected[3]:
            return hv.NdOverlay(
                {"": hv.Curve(([0.0], [0.0]), "Time [s]", ylabel)}, kdims="coil"
            ).opts(title="Waiting for data...", height=_HEIGHT, width=_WIDTH)
        time, data, names, idx = selected
        values = data[var].values / scale
        curves = {
            names[i]: hv.Curve((time, values[:, k]), "Time [s]", ylabel)
            for k, i in enumerate(idx)
        }
        return hv.NdOverlay(curves, kdims="coil", sort=False).opts(
            title=title,
            framewise=True,
            height=_HEIGHT,
            width=_WIDTH,
            legend_position="right",
        )

    @param.depends("time")
    def plot_sc_currents(self):
        return self._coil_overlay(
            "(a) CS/PF superconducting coil currents",
            "current",
            "Current [A]",
            1.0,
            False,
        )

    @param.depends("time")
    def plot_vs_currents(self):
        return self._coil_overlay(
            "(b) VS resistive coil currents", "current", "Current [kA]", 1e3, True
        )

    @param.depends("time")
    def plot_sc_voltages(self):
        return self._coil_overlay(
            "(d) CS/PF coil voltages (applied over the preceding step)",
            "voltage",
            "Voltage [V]",
            1.0,
            False,
        )

    @param.depends("time")
    def plot_vs_voltages(self):
        return self._coil_overlay(
            "(e) VS coil voltages (applied over the preceding step)",
            "voltage",
            "Voltage [V]",
            1.0,
            True,
        )

    @param.depends("time")
    def plot_passive_currents(self):
        state = self.active_state.data.get("pf_passive")
        if state is None:
            paths, title = [], "Waiting for data..."
        else:
            mask = (state.time <= self.time).values
            time = state.time.values[mask]
            current = state.current.values[mask, :] / 1e3
            # One multi-line glyph: ~100 loops, no legend.
            paths = [
                np.column_stack([time, current[:, k]]) for k in range(current.shape[1])
            ]
            title = f"(c) Passive loop currents ({current.shape[1]} loops)"
        return hv.Path(paths, kdims=["Time [s]", "Current [kA]"]).opts(
            title=title,
            framewise=True,
            height=_HEIGHT,
            width=_WIDTH,
            color="steelblue",
            line_width=1,
        )
