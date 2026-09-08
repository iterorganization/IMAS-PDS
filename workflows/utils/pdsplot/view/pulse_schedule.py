"""Panels of the pulse schedule figure.

``PulseScheduleView`` only knows about the dictionary of numpy arrays produced by
:mod:`pdsplot.compute.pulse_schedule`, so the very same code draws the references
of a ``pulse_schedule`` IDS and the waveforms derived from the physics IDSs of an
input entry.  One view is built per entry; the entry drawn dashed is simply a view
constructed with ``linestyle="--"``.

A legend entry is written only once per panel: the entries share the colours and
are told apart by their line style, which the legend title spells out ("PDS
solid, in dashed"), instead of repeating the entry name after every quantity.
When there are more than two entries, which no line style can tell apart, the
name is appended to every entry again (``tag_labels=True``).
"""

import logging

import numpy as np

from ..compute.common import coil_group, has_data
from .common import BasePlot

logger = logging.getLogger("module")

#: One colour per scalar quantity, so that an overlay lines up with its reference.
COLOR = {
    "ip": "C0", "v_loop": "C3", "b0_r0": "C0", "li_3": "C2",
    "beta_tor_norm": "C1", "geometric_axis_r": "C0", "geometric_axis_z": "C1",
    "magnetic_axis_r": "C2", "magnetic_axis_z": "C3", "minor_radius": "C0",
    "elongation": "C1", "triangularity_upper": "C2", "triangularity_lower": "C3",
    "n_e_line": "C0", "n_e_volume_average": "C1", "zeff": "C3",
    "p_ec": "C0", "p_nbi": "C1", "p_ic": "C2", "p_lh": "C3",
}


class PulseScheduleView(BasePlot):
    """Draw one entry's waveforms.

    Args:
        waveforms (dict): output of ``PulseScheduleCompute``/``WaveformsFromIdsCompute``.
        label (str): legend label of this entry.
        linestyle (str): ``"-"`` for the main entry, ``"--"`` for a reference.
        alpha (float): line transparency.
        tag_labels (bool): append the entry name to every legend entry, needed
            only when more than two entries are overlaid.
    """

    def __init__(self, waveforms, label="PDS", linestyle="-", alpha=1.0,
                 tag_labels=False):
        self.waveforms = waveforms
        self.label = label
        self.linestyle = linestyle
        self.alpha = alpha
        self.tag_labels = tag_labels
        self.is_reference = linestyle != "-"

    # -- plumbing --------------------------------------------------------
    def _time(self, block):
        time = self.waveforms.get("time_" + block)
        if time is None or not len(time):
            time = self.waveforms.get("time")
        return np.asarray(time, dtype=float)

    def _tag(self, ax, text):
        """Legend entry of a curve of ``ax``, or None when it needs none.

        The quantity is named once per panel: the second entry draws the same
        quantities in the same colours, dashed, and the legend title says so. The
        name is only repeated -- suffixed by the entry name -- when the entries
        cannot be told apart by their style (``tag_labels``).
        """
        if text is None:
            return None
        if self.tag_labels:
            return "%s (%s)" % (text, self.label) if self.label else text
        return None if text in ax.get_legend_handles_labels()[1] else text

    def _line(self, ax, block, key, scale=1.0, label=None, color=None,
              legend=True):
        """Plot one waveform, silently skipping it when it holds no finite value."""
        values = np.asarray(self.waveforms.get(key), dtype=float)
        time = self._time(block)
        if not has_data(values) or not time.size:
            return False
        length = min(time.size, values.size)
        style = self.linestyle if length > 1 else "o"
        ax.plot(time[:length], values[:length] * scale, style,
                color=color or COLOR.get(key), alpha=self.alpha,
                label=self._tag(ax, label or key) if legend else None)
        return True

    # -- 1. flux control -------------------------------------------------
    def view_flux_control_waveforms(self, ax, ax_right):
        """Plasma current [MA] on ``ax`` and loop voltage [V] on ``ax_right``.

        The plasma current of an ITER scenario is negative in the COCOS of the
        data; it is drawn with its sign reversed, and named ``-Ip``, so that the
        panel reads as the magnitude of the current. The data itself is not
        touched: only what is plotted is.
        """
        self._line(ax, "flux_control", "ip", -1.0e-6, r"$-I_p$")
        self._line(ax_right, "flux_control", "v_loop", 1.0, r"$V_{loop}$")
        ax.set_ylabel(r"$-I_p$ [MA]")
        ax_right.set_ylabel(r"$V_{loop}$ [V]")
        ax.set_xlabel("time [s]")
        ax.set_title("Flux waveforms")

    # -- 2. toroidal field and stability ---------------------------------
    def view_field_stability_waveforms(self, ax, ax_right):
        """Vacuum ``B0.R0`` [T.m] on ``ax``, ``li_3`` and ``beta_N`` on the right."""
        self._line(ax, "tf", "b0_r0", 1.0, r"$B_0 R_0$")
        self._line(ax_right, "flux_control", "li_3", 1.0, r"$l_{i3}$")
        self._line(ax_right, "flux_control", "beta_tor_norm", 1.0, r"$\beta_N$")
        ax.set_ylabel(r"$B_0 R_0$ [T$\cdot$m]")
        ax_right.set_ylabel(r"$l_{i3}$, $\beta_N$")
        ax.set_xlabel("time [s]")
        ax.set_title("Toroidal field and stability")

    # -- 3. boundary snapshot --------------------------------------------
    def view_boundary(self, ax, time_value):
        """Boundary, X points and axes at the sample nearest ``time_value``."""
        time = self._time("position_control")
        if not time.size:
            return
        index = int(np.abs(time - time_value).argmin())
        outline_r = self.waveforms["boundary_outline_r"]
        outline_z = self.waveforms["boundary_outline_z"]
        if outline_r.size and index < outline_r.shape[1]:
            points_r = outline_r[:, index]
            points_z = outline_z[:, index]
            finite = np.isfinite(points_r) & np.isfinite(points_z)
            points_r, points_z = points_r[finite], points_z[finite]
            if points_r.size:
                points_r, points_z = self._closed(points_r, points_z)
                ax.plot(points_r, points_z, self.linestyle, color="C0",
                        alpha=self.alpha, linewidth=1.2,
                        label=self._tag(ax, "boundary"))
        x_point_r = self.waveforms["x_point_r"]
        x_point_z = self.waveforms["x_point_z"]
        if x_point_r.size and index < x_point_r.shape[1]:
            ax.plot(x_point_r[:, index], x_point_z[:, index], "x", color="C3",
                    alpha=self.alpha, markersize=8,
                    label=self._tag(ax, "X point"))
        marker = "s" if self.is_reference else "o"
        for key_r, key_z, color, name in (
                ("geometric_axis_r", "geometric_axis_z", "C2", "geom. axis"),
                ("magnetic_axis_r", "magnetic_axis_z", "C1", "mag. axis")):
            values_r = np.asarray(self.waveforms[key_r], dtype=float)
            values_z = np.asarray(self.waveforms[key_z], dtype=float)
            if index < values_r.size and np.isfinite(values_r[index]) \
                    and index < values_z.size and np.isfinite(values_z[index]):
                ax.plot(values_r[index], values_z[index], marker, color=color,
                        alpha=self.alpha, markersize=5,
                        label=self._tag(ax, name))
        ax.set_xlabel("R [m]")
        ax.set_ylabel("Z [m]")
        ax.set_aspect("equal", adjustable="box")
        ax.set_title("Boundary at t = %.2f s" % time_value)

    @staticmethod
    def _closed(points_r, points_z):
        """Close a contour, unless its ends are far apart.

        A ``pulse_schedule`` boundary outline is a closed list of points given
        once, so the first point has to be repeated; a separatrix taken from an
        equilibrium usually ends on the divertor targets and must be left open.
        """
        span = max(np.ptp(points_r), np.ptp(points_z), 1.0e-9)
        gap = np.hypot(points_r[0] - points_r[-1], points_z[0] - points_z[-1])
        if gap > 0.05 * span:
            return points_r, points_z
        return np.append(points_r, points_r[0]), np.append(points_z, points_z[0])

    @staticmethod
    def view_wall(ax, wall_outlines):
        """First wall contours, ``[(r, z), ...]``, drawn behind the boundaries."""
        for position, (points_r, points_z) in enumerate(wall_outlines or []):
            ax.plot(points_r, points_z, "-", color="0.35", linewidth=0.9,
                    label="first wall" if position == 0 else None)

    # -- 4, 5, 6. poloidal field coils ------------------------------------
    def _coil_indices(self, groups):
        names = self.waveforms.get("coil_names") or []
        return [index for index, name in enumerate(names)
                if coil_group(name) in groups]

    def view_coil_currents(self, ax, groups=("CS",), colors=None):
        """One line per coil of ``groups``, current in kA."""
        currents = self.waveforms.get("coil_currents")
        names = self.waveforms.get("coil_names") or []
        if currents is None or not currents.size:
            return
        time = self._time("pf_active")
        for position, index in enumerate(self._coil_indices(groups)):
            if index >= currents.shape[0]:
                continue
            values = currents[index]
            if not has_data(values):
                continue
            length = min(time.size, values.size)
            color = (colors or {}).get(names[index], "C%d" % (position % 10))
            ax.plot(time[:length], values[:length] * 1.0e-3, self.linestyle,
                    color=color, alpha=self.alpha,
                    label=self._tag(ax, names[index]))
        ax.set_xlabel("time [s]")
        ax.set_ylabel("I [kA]")

    def view_coil_voltages(self, ax, groups=("CS", "PF", "other"), colors=None):
        """One line per coil of ``groups``, voltage in V."""
        voltages = self.waveforms.get("coil_voltages")
        names = self.waveforms.get("coil_names") or []
        if voltages is None or not voltages.size:
            return
        time = self._time("pf_active")
        for position, index in enumerate(self._coil_indices(groups)):
            if index >= voltages.shape[0]:
                continue
            values = voltages[index]
            if not has_data(values):
                continue
            length = min(time.size, values.size)
            color = (colors or {}).get(names[index], "C%d" % (position % 10))
            ax.plot(time[:length], values[:length], self.linestyle, color=color,
                    alpha=self.alpha, label=self._tag(ax, names[index]))
        ax.set_xlabel("time [s]")
        ax.set_ylabel("V [V]")

    # -- 7. position control ----------------------------------------------
    def view_position_waveforms(self, ax):
        """Geometric and magnetic axis, R and Z, in metres."""
        self._line(ax, "position_control", "geometric_axis_r", 1.0, r"$R_{geo}$")
        self._line(ax, "position_control", "geometric_axis_z", 1.0, r"$Z_{geo}$")
        self._line(ax, "position_control", "magnetic_axis_r", 1.0, r"$R_{mag}$")
        self._line(ax, "position_control", "magnetic_axis_z", 1.0, r"$Z_{mag}$")
        ax.set_xlabel("time [s]")
        ax.set_ylabel("R, Z [m]")
        ax.set_title("Position waveforms")

    # -- 8. shape ----------------------------------------------------------
    def view_shape_waveforms(self, ax, ax_right):
        """Minor radius [m] on ``ax``; elongation and triangularity on the right."""
        self._line(ax, "position_control", "minor_radius", 1.0, r"$a$")
        self._line(ax_right, "position_control", "elongation", 1.0, r"$\kappa$")
        if not self._line(ax_right, "position_control", "triangularity_upper",
                          1.0, r"$\delta_{up}$"):
            self._line(ax_right, "position_control", "triangularity", 1.0,
                       r"$\delta$", color=COLOR["triangularity_upper"])
        self._line(ax_right, "position_control", "triangularity_lower", 1.0,
                   r"$\delta_{low}$")
        ax.set_xlabel("time [s]")
        ax.set_ylabel(r"$a$ [m]")
        ax_right.set_ylabel(r"$\kappa$, $\delta$")
        ax.set_title("Shape")

    # -- 9. X point --------------------------------------------------------
    def view_x_point_waveforms(self, ax):
        """R and Z of every X point reference against time."""
        x_point_r = self.waveforms["x_point_r"]
        x_point_z = self.waveforms["x_point_z"]
        if not x_point_r.size:
            return False
        time = self._time("position_control")
        drawn = False
        for index in range(x_point_r.shape[0]):
            for values, color, name in ((x_point_r[index], "C0", "R"),
                                        (x_point_z[index], "C1", "Z")):
                if not has_data(values):
                    continue
                length = min(time.size, values.size)
                suffix = "" if x_point_r.shape[0] == 1 else " %d" % (index + 1)
                ax.plot(time[:length], values[:length], self.linestyle,
                        color=color, alpha=self.alpha,
                        label=self._tag(ax, "%s%s" % (name, suffix)))
                drawn = True
        ax.set_xlabel("time [s]")
        ax.set_ylabel("R, Z [m]")
        ax.set_title("X point")
        return drawn

    # -- 10. density control ------------------------------------------------
    def view_density_waveforms(self, ax, ax_right):
        """Densities in 1e19 m^-3 on ``ax``, effective charge on the right."""
        self._line(ax, "density_control", "n_e_line", 1.0e-19,
                   r"$\langle n_e \rangle_{line}$")
        self._line(ax, "density_control", "n_e_volume_average", 1.0e-19,
                   r"$\langle n_e \rangle_{vol}$")
        self._line(ax_right, "density_control", "zeff", 1.0, r"$Z_{eff}$")
        ax.set_xlabel("time [s]")
        ax.set_ylabel(r"$n_e$ [$10^{19}$ m$^{-3}$]")
        ax_right.set_ylabel(r"$Z_{eff}$")
        ax.set_title("Density waveforms")

    # -- 11. heating and current drive ---------------------------------------
    def view_hcd_waveforms(self, ax):
        """EC, NBI, IC and LH launched power in MW."""
        drawn = False
        for key, name in (("p_ec", r"$P_{EC}$"), ("p_nbi", r"$P_{NBI}$"),
                          ("p_ic", r"$P_{IC}$"), ("p_lh", r"$P_{LH}$")):
            block = {"p_ec": "ec", "p_nbi": "nbi", "p_ic": "ic",
                     "p_lh": "lh"}[key]
            values = np.asarray(self.waveforms.get(key), dtype=float)
            if has_data(values) and np.nanmax(np.abs(values)) > 0:
                drawn |= self._line(ax, block, key, 1.0e-6, name)
        ax.set_xlabel("time [s]")
        ax.set_ylabel("P [MW]")
        ax.set_title("H&CD references")
        return drawn
