import logging
import traceback

import holoviews as hv
import numpy as np
import panel as pn
import param
import xarray as xr

from imas_muscle3.visualization.base_plotter import BasePlotter
from imas_muscle3.visualization.base_state import BaseState

logger = logging.getLogger(__name__)

_PLOT_HEIGHT = 300
_PLOT_WIDTH = 550

class State(BaseState):
    """Extracts scalar waveforms and 1D profiles for a SINGLE source."""

    def extract(self, ids):
        if ids.metadata.name == "core_sources":
            self._extract_core_sources(ids)

    def _extract_core_sources(self, ids):
        if not ids.source or not ids.time:
            return
            
        source = ids.source[0]
        if not source.global_quantities or not source.profiles_1d:
            return

        t_val = float(ids.time[0])

        # 1. EXTRACT SCALARS
        raw_power = source.global_quantities[0].electrons.power
        p_val = 0.0 if raw_power < -1e30 else (raw_power / 1e6) # [MW]
        
        raw_current = -1 * source.global_quantities[0].current_parallel
        c_val = 0.0 if raw_current < -1e30 else (raw_current / 1e3) # [kA]

        # 2. EXTRACT 1D PROFILES
        p1d = source.profiles_1d[0]
        rho = np.array(p1d.grid.rho_tor_norm)
        
        raw_energy = np.array(p1d.electrons.energy)
        clean_energy = np.where(raw_energy < -1e30, 0.0, raw_energy) / 1e6 # [MW]

        raw_jpar = -1 * np.array(p1d.j_parallel)
        clean_jpar = np.where(raw_jpar < -1e30, 0.0, raw_jpar) / 1e3 # [kA] 

        # 3. COMBINE INTO SINGLE XARRAY DATASET
        new_point = xr.Dataset(
            {
                "power": ("time", [p_val]),
                "current": ("time", [c_val]),
                "energy": (("time", "x_coord"), [clean_energy]),
                "j_parallel": (("time", "x_coord"), [clean_jpar]),
                "rho": (("time", "x_coord"), [rho]),
            },
            coords={
                "time": [t_val],
                "x_coord": np.arange(len(rho)),
            },
        )
        
        current_data = self.data.get("core_sources")
        if current_data is None:
            self.data["core_sources"] = new_point
        else:
            self.data["core_sources"] = xr.concat(
                [current_data, new_point], dim="time", join="outer"
            )


class Plotter(BasePlotter):
    """Dashboard with time-evolving single source waveforms and profiles."""

    def get_dashboard(self):
        power_map = hv.DynamicMap(self.plot_power)
        current_map = hv.DynamicMap(self.plot_current)
        energy_map = hv.DynamicMap(self.plot_energy_profile)
        jpar_map = hv.DynamicMap(self.plot_jpar_profile)
        
        return pn.Column(
            pn.Row(power_map, current_map),
            pn.Row(energy_map, jpar_map)
        )

    # ---------------------------------------------------------
    # TIME TRACES (Waveforms)
    # ---------------------------------------------------------
    @param.depends("time")
    def plot_power(self):
        try:
            state = self.active_state.data.get("core_sources")
            if state is not None:
                current_time = self.time if self.time is not None else float('inf')
                mask = state.time <= current_time
                time_vals = state.time[mask]
                power_vals = state.power[mask]
                title = "ECRH Power Waveform"
            else:
                time_vals, power_vals, title = np.array([0.0]), np.array([0.0]), "Waiting for data..."

            return hv.Curve((time_vals, power_vals), kdims=["time"], vdims=["Power"], label="ECRH Power").opts(
                framewise=True, height=_PLOT_HEIGHT, width=_PLOT_WIDTH,
                title=title, show_legend=True, show_grid=True,
                xlabel="Time [s]", ylabel="Power [MW]", color="red",
            )
        except Exception as e:
            return hv.Text(0, 0, f"Error: {e}").opts(color="red")

    @param.depends("time")
    def plot_current(self):
        try:
            state = self.active_state.data.get("core_sources")
            if state is not None:
                current_time = self.time if self.time is not None else float('inf')
                mask = state.time <= current_time
                time_vals = state.time[mask]
                current_vals = state.current[mask]
                title = "ECCD Current Waveform"
                y_min = float(state.current.min())
                y_max = float(state.current.max())
            else:
                time_vals, current_vals, title = np.array([0.0]), np.array([0.0]), "Waiting for data..."
                y_min = 0.0
                y_max = 0.0

            return hv.Curve((time_vals, current_vals), kdims=["time"], vdims=["Current"], label="ECCD").opts(
                framewise=False, ylim=(y_min * 1.05, y_max * 1.05), height=_PLOT_HEIGHT, width=_PLOT_WIDTH,
                title=title, show_legend=True, xlabel="Time [s]", 
                ylabel="Current [kA]", color="green", show_grid=True,
            )
        except Exception as e:
            return hv.Text(0, 0, f"Error: {e}").opts(color="red")

    # ---------------------------------------------------------
    # 1D SPATIAL PROFILES (Snapshots)
    # ---------------------------------------------------------
    @param.depends("time")
    def plot_energy_profile(self):
        try:
            state = self.active_state.data.get("core_sources")
            if state is not None:
                # Protect against None during early initialization
                current_time = self.time if self.time is not None else state.time.values[-1]
                ds_slice = state.sel(time=current_time, method="nearest")
                rho_vals = ds_slice.rho
                energy_vals = ds_slice.energy
                title = "Electron Energy Deposition Profile"
            else:
                rho_vals, energy_vals, title = np.array([0.0, 1.0]), np.array([0.0, 0.0]), "Waiting for data..."

            return hv.Curve((rho_vals, energy_vals), kdims=["rho"], vdims=["Energy"], label="ECRH Deposition profile").opts(
                framewise=True, height=_PLOT_HEIGHT, width=_PLOT_WIDTH,
                title=title, show_legend=True, show_grid=True,
                xlabel="rho_tor_norm", ylabel="Power Density [MW/m³]", color="red", 
            )
        except Exception as e:
            return hv.Text(0, 0, f"Error: {e}").opts(color="red")
    
    @param.depends("time")
    def plot_jpar_profile(self):
        try:
            state = self.active_state.data.get("core_sources")
            if state is not None:
                current_time = self.time if self.time is not None else state.time.values[-1]
                ds_slice = state.sel(time=current_time, method="nearest")
                rho_vals = ds_slice.rho
                jpar_vals = ds_slice.j_parallel
                title = "Parallel Current Drive Profile"
            else:
                rho_vals, jpar_vals, title = np.array([0.0, 1.0]), np.array([0.0, 0.0]), "Waiting for data..."

            return hv.Curve((rho_vals, jpar_vals), kdims=["rho"], vdims=["Current"], label="j_parallel").opts(
                framewise=True, height=_PLOT_HEIGHT, width=_PLOT_WIDTH,
                title=title, show_legend=True, show_grid=True,
                xlabel="rho_tor_norm", ylabel="Current Density [kA/m³]", color="green", 
            )
        except Exception as e:
            return hv.Text(0, 0, f"Error: {e}").opts(color="red")
