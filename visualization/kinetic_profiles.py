"""
TORAX visualization plotter.

Plots 1D radial profiles (T_e, T_i, n_e, n_i) from core_profiles IDS
against rho_tor_norm, evolving in time via a time slider.
Also plots scalar global quantities Ip and v_loop over time.
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

# Plots dimensions
_PROFILE_HEIGHT = 280
_PROFILE_WIDTH = 550
_SCALAR_HEIGHT = 220
_SCALAR_WIDTH = 550


class State(BaseState):
    """Extracts and stores time-evolving data from core_profiles and equilibrium IDS."""

    def extract(self, ids):
        if ids.metadata.name == "core_profiles":
            self._extract_core_profiles(ids)
        elif ids.metadata.name == "equilibrium":
            self._extract_equilibrium(ids)

    def _extract_core_profiles(self, ids):
        """Extract 1D radial profiles and global scalars from a core_profiles IDS slice."""
        if not ids.profiles_1d:
            logger.warning("core_profiles IDS has no profiles_1d data, skipping.")
            return
        p1d = ids.profiles_1d[0]
        t = ids.time[0]
        rho = np.asarray(p1d.grid.rho_tor_norm)
        if rho.size == 0:
            logger.warning("rho_tor_norm is empty at t=%.4f, skipping.", t)
            return

        n_rho = rho.size

        # --- 1D profiles ---
        t_e = np.asarray(p1d.electrons.temperature / 1e3)   # [keV]
        n_e = np.asarray(p1d.electrons.density)        # [m^-3]
        t_e0 = t_e[0]
        n_e0 = n_e[0]


        # Ion profiles: average over ion species present (usually D, T, He...)
        t_i = np.asarray(p1d.t_i_average / 1e3)  # [keV]
        t_i0 = t_i[0]
        n_i_list = [
            np.asarray(ion.density)
            for ion in p1d.ion
            if np.asarray(ion.density).size == n_rho
        ]
        # Mean ion temperature / density across species (simple average)
        n_i = np.sum(n_i_list, axis=0) # [m^-3]
        n_i0 = n_i[0]

        ip = -1 * ids.global_quantities.ip[0] / 1e6 # [MA]

        profiles = xr.Dataset(
            {
                "T_e": (("time", "x_coord"), [t_e]),
                "T_i": (("time", "x_coord"), [t_i]),
                "n_e": (("time", "x_coord"), [n_e]),
                "n_i": (("time", "x_coord"), [n_i]),
                "rho": (("time", "x_coord"), [rho]),
                "T_e0": ("time", [t_e0]),
                "T_i0": ("time", [t_i0]),
                "n_e0": ("time", [n_e0]),
                "n_i0": ("time", [n_i0]),
                "ip": ("time", [ip]),
            },
            coords={
                "time": [t],
                "x_coord": np.arange(len(t_e)),
            },
        )

        # Accumulate profiles over time
        existing_profiles = self.data.get("core_profiles")
        if existing_profiles is None:
            self.data["core_profiles"] = profiles
        else:
            self.data["core_profiles"] = xr.concat(
                [existing_profiles, profiles], dim="time", join="outer"
            )


    def _extract_equilibrium(self, ids):
        """Extract global Ip from equilibrium IDS (fallback scalar source)."""
        ts = ids.time_slice[0]
        t = ids.time[0]
        p1d = ts.profiles_1d
        new_point = xr.Dataset(
            {
                "ip_eq": ("time", [ts.global_quantities.ip]),
                "psi_profile": (("time", "x_coord"), [p1d.psi]),
                "f_df_dpsi": (("time", "x_coord"), [p1d.f_df_dpsi]),
                "dpressure_dpsi": (("time", "x_coord"), [p1d.dpressure_dpsi]),
            },
            coords={"time": [t]},
        )
        current_data = self.data.get("equilibrium")
        if current_data is None:
            self.data["equilibrium"] = new_point
        else:
            self.data["equilibrium"] = xr.concat(
                [current_data, new_point], dim="time", join="outer"
            )

class Plotter(BasePlotter):
    """Dashboard with time-evolving 1D profile plots and source waveforms."""
 
    def get_dashboard(self):
        # Overlay DynamicMaps directly (same pattern as nice_inv.py flux_map_elements).
        # Returning an Overlay from inside a DynamicMap callback breaks rendering.
        temperature = (
            hv.DynamicMap(self.plot_T_e) * hv.DynamicMap(self.plot_T_i)
        ).opts(
            hv.opts.Overlay(
                framewise=True, height=_PROFILE_HEIGHT, width=_PROFILE_WIDTH,
                title="Temperature profiles", show_legend=True, legend_position="top_right",
                xlabel="rho_tor_norm", ylabel="Temperature [keV]", show_grid=True,
            )
        )
        density = (
            hv.DynamicMap(self.plot_n_e) * hv.DynamicMap(self.plot_n_i)
        ).opts(
            hv.opts.Overlay(
                framewise=True, height=_PROFILE_HEIGHT, width=_PROFILE_WIDTH,
                title="Density profiles", show_legend=True, legend_position="top_right",
                xlabel="rho_tor_norm", ylabel="Density [m⁻³]", show_grid=True,
            )
        )
        ip      = hv.DynamicMap(self.plot_ip_vs_time)
        Te_0      = hv.DynamicMap(self.plot_Te0_vs_time)
        Ti_0      = hv.DynamicMap(self.plot_Ti0_vs_time)
        temperature_waveforms = ( Te_0 * Ti_0 ).opts(
            hv.opts.Overlay(
                framewise=True, height=_PROFILE_HEIGHT, width=_PROFILE_WIDTH,
                title="Temperature waveforms", show_legend=True, legend_position="top_right",
                xlabel="Time [s]", ylabel="Temperature [keV]", show_grid=True,
            )
        )
        ne_0      = hv.DynamicMap(self.plot_ne0_vs_time)
        ni_0      = hv.DynamicMap(self.plot_ni0_vs_time)
        density_waveforms = ( ne_0 * ni_0 ).opts(
            hv.opts.Overlay(
                framewise=True, height=_PROFILE_HEIGHT, width=_PROFILE_WIDTH,
                title="Density waveforms", show_legend=True, legend_position="top_right",
                xlabel="Time [s]", ylabel="Density [m⁻³]", show_grid=True,
            )
        )
        f_df_dpsi = hv.DynamicMap(self.plot_f_df_dpsi_profile)
        dpressure_dpsi = hv.DynamicMap(self.plot_dpressure_dpsi)

 
        return pn.Row(
            pn.Column(temperature, density),
            pn.Column(ip, temperature_waveforms, density_waveforms),
            pn.Column(
                f_df_dpsi, dpressure_dpsi, ip),
        )
 
    # ------------------------------------------------------------------
    # 1D profile plots — one method per curve
    # ------------------------------------------------------------------
 
    def _get_profile_snap(self):
        """Return (rho, selected_data) or (None, None) if no data yet."""
        state = self.active_state.data.get("core_profiles")
        if state is None:
            return None, None
        return state.sel(time=self.time, method="nearest"), state
 
    @param.depends("time")
    def plot_T_e(self):
        """Plot T_e vs rho_tor_norm at the selected time."""
        snap, _ = self._get_profile_snap()
        if snap is None:
            return hv.Curve([], kdims=["rho_tor_norm"], vdims=["T_e [keV]"], label = "T_e",).opts(
                framewise=True, height=_PROFILE_HEIGHT, width=_PROFILE_WIDTH,
                title="Waiting for core_profiles data...",
            )
        return hv.Curve(
            (snap.rho.values, snap.T_e.values), kdims=["rho_tor_norm"], vdims=["T_e [keV]"], label = "T_e",
        ).opts(color="red", framewise=True)
 
    @param.depends("time")
    def plot_T_i(self):
        """Plot T_i vs rho_tor_norm at the selected time."""
        snap, _ = self._get_profile_snap()
        if snap is None:
            return hv.Curve([], kdims=["rho_tor_norm"], vdims=["T_i [keV]"], label = "T_i",).opts(framewise=True)
        return hv.Curve(
            (snap.rho.values, snap.T_i.values), kdims=["rho_tor_norm"], vdims=["T_i [keV]"], label = "T_i",
        ).opts(color="blue", framewise=True)
 
    @param.depends("time")
    def plot_n_e(self):
        """Plot n_e vs rho_tor_norm at the selected time."""
        snap, _ = self._get_profile_snap()
        if snap is None:
            return hv.Curve([], kdims=["rho_tor_norm"], vdims=["n_e [m⁻³]"], label = "n_e",).opts(
                framewise=True, height=_PROFILE_HEIGHT, width=_PROFILE_WIDTH,
                title="Waiting for core_profiles data...",
            )
        return hv.Curve(
            (snap.rho.values, snap.n_e.values), kdims=["rho_tor_norm"], vdims=["n_e [m⁻³]"], label = "n_e",
        ).opts(color="red", framewise=True)
 
    @param.depends("time")
    def plot_n_i(self):
        """Plot n_i (sum over ions) vs rho_tor_norm at the selected time."""
        snap, _ = self._get_profile_snap()
        if snap is None:
            return hv.Curve([], kdims=["rho_tor_norm"], vdims=["n_i [m⁻³]"]).opts(framewise=True)
        return hv.Curve(
            (snap.rho.values, snap.n_i.values), kdims=["rho_tor_norm"], vdims=["n_i [m⁻³]"], label = "n_i",
        ).opts(color="blue", framewise=True)
 
    # ------------------------------------------------------------------
    # Scalar / waveform plots (history up to slider time)
    # ------------------------------------------------------------------
 
    @param.depends("time")
    def plot_ip_vs_time(self):
        """Plot plasma current Ip vs time."""
        state = self.active_state.data.get("core_profiles")
        var, ylabel = "ip", "Ip [MA]"
        if state is None:
            time, ip, title = [], [], "Waiting for data..."
        else:
            mask  = state.time <= self.time
            time  = state.time[mask]
            ip    = state[var][mask]
            title = "Plasma current over time"
 
        return hv.Curve((time, ip), "Time [s]", ylabel, label = "Ip").opts(
            framewise=True, height=_SCALAR_HEIGHT, width=_SCALAR_WIDTH,
            title=title, show_legend= True,
            color="green", show_grid=True,
        )
    
    @param.depends("time")
    def plot_Te0_vs_time(self):
        """Plot Te(0) vs time."""
        state = self.active_state.data.get("core_profiles")
        var = "T_e0"
        if state is None:
            time, Te0 = [], []
        else:
            mask  = state.time <= self.time
            time  = state.time[mask]
            Te0    = state[var][mask]
 
        return hv.Curve((time, Te0), kdims=["time"], vdims=["T_e0 [keV]"], label = "T_e(0)",).opts(
            framewise=True, color="red",
        )
    
    @param.depends("time")
    def plot_Ti0_vs_time(self):
        """Plot Ti(0) vs time."""
        state = self.active_state.data.get("core_profiles")
        var = "T_i0"
        if state is None:
            time, Ti0 = [], []
        else:
            mask  = state.time <= self.time
            time  = state.time[mask]
            Ti0    = state[var][mask]
 
        return hv.Curve((time, Ti0), kdims=["time"], vdims=["T_i0 [keV]"], label = "T_i(0)",).opts(
            framewise=True, color="blue",
        )
    
    @param.depends("time")
    def plot_ne0_vs_time(self):
        """Plot ne(0) vs time."""
        state = self.active_state.data.get("core_profiles")
        var = "n_e0"
        if state is None:
            time, ne0 = [], []
        else:
            mask  = state.time <= self.time
            time  = state.time[mask]
            ne0    = state[var][mask]
 
        return hv.Curve((time, ne0), kdims=["time"], vdims=["n_e0 [keV]"], label = "n_e(0)",).opts(
            framewise=True, color="red",
        )
    
    @param.depends("time")
    def plot_ni0_vs_time(self):
        """Plot ni(0) vs time."""
        state = self.active_state.data.get("core_profiles")
        var = "n_i0"
        if state is None:
            time, ni0 = [], []
        else:
            mask  = state.time <= self.time
            time  = state.time[mask]
            ni0    = state[var][mask]
 
        return hv.Curve((time, ni0), kdims=["time"], vdims=["n_i0 [keV]"], label = "n_i(0)",).opts(
            framewise=True, color="blue",
        )
    
    @param.depends("time")
    def plot_f_df_dpsi_profile(self):
        xlabel = "Psi"
        ylabel = "ff'"
        state = self.active_state.data.get("equilibrium")

        if state:
            selected_data = state.sel(time=self.time)
            psi = selected_data.psi_profile
            f_df_dpsi = selected_data.f_df_dpsi
            title = "ff' profile"
        else:
            psi, f_df_dpsi, title = [], [], "Waiting for data..."

        return hv.Curve((psi, f_df_dpsi), xlabel, ylabel).opts(
            framewise=True, height=200, width=600, title=title
        )

    @param.depends("time")
    def plot_dpressure_dpsi(self):
        xlabel = "Psi"
        ylabel = "p'"
        state = self.active_state.data.get("equilibrium")

        if state:
            selected_data = state.sel(time=self.time)
            psi = selected_data.psi_profile
            dpressure_dpsi = selected_data.dpressure_dpsi
            title = "p' profile"
        else:
            psi, dpressure_dpsi, title = [], [], "Waiting for data..."

        return hv.Curve((psi, dpressure_dpsi), xlabel, ylabel).opts(
            framewise=True, height=200, width=600, title=title
        )

    
