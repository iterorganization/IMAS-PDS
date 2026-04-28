"""
Simple example plot which plots the plasma current over time.
"""

import logging

import holoviews as hv
import matplotlib.pyplot as plt
import numpy as np
import panel as pn
import param
import xarray as xr

from imas_muscle3.visualization.base_plotter import BasePlotter
from imas_muscle3.visualization.base_state import BaseState


class State(BaseState):
    def extract(self, ids):
        if ids.metadata.name == "equilibrium":
            self._extract_equilibrium(ids)

    def _extract_equilibrium(self, ids):
        ts = ids.time_slice[0]
        # Extract profiles
        profiles_data = xr.Dataset(
            {
                "f_df_dpsi": (("time", "profile"), [ts.profiles_1d.f_df_dpsi]),
                "dpressure_dpsi": (
                    ("time", "profile"),
                    [ts.profiles_1d.dpressure_dpsi],
                ),
                "psi_profile": (("time", "profile"), [ts.profiles_1d.psi]),
            },
            coords={
                "time": [ids.time[0]],
                "profile": np.arange(len(ts.profiles_1d.f_df_dpsi)),
            },
        )

        ip_beta_tor = xr.Dataset(
            {
                "ip": ("time", [ts.global_quantities.ip]),
            },
            coords={
                "time": [ids.time[0]],
            },
        )

        # Combine all datasets
        new_data = xr.merge(
            [
                profiles_data,
                ip_beta_tor,
            ]
        )

        current_data = self.data.get("equilibrium")
        if current_data is None:
            self.data["equilibrium"] = new_data
        else:
            self.data["equilibrium"] = xr.concat(
                [current_data, new_data], dim="time", join="outer"
            )

class Plotter(BasePlotter):
    def get_dashboard(self):
        f_df_dpsi = hv.DynamicMap(self.plot_f_df_dpsi_profile)
        dpressure_dpsi = hv.DynamicMap(self.plot_dpressure_dpsi)
        ip = hv.DynamicMap(self.plot_ip_vs_time)

        return pn.Row(
            pn.Column(
                pn.Row(f_df_dpsi, dpressure_dpsi),
                pn.Row(ip),
            ),
        )

    @param.depends("time")
    def plot_ip_vs_time(self):
        xlabel = "Time [s]"
        ylabel = "Ip [A]"
        state = self.active_state.data.get("equilibrium")

        if state:
            mask = state.time <= self.time
            time = state.time[mask].values
            ip = state.ip.sel(time=mask).values
            title = "Ip over time"
        else:
            time, ip, title = [], [], "Waiting for data..."

        return hv.Curve((time, ip), kdims=["time_ip"], vdims=["ip"]).opts(
            framewise=True,
            height=200,
            width=600,
            title=title,
            xlabel=xlabel,
            ylabel=ylabel,
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
