"""Equilibrium dashboard for evolutive NICE runs (recorder plot file).

It shows, for the time selected in the dashboard:

- the plasma: boundary now (red) and at the start of the run (grey, dashed),
  X-points, wall, vessel and coils, with equal R and Z scales; psi contours
  on request (checkbox, off by default);
- |Ip|, Z and R over the run. Z and R are the plasma position the controller
  uses (magnetic_controller.plasma_position of the run: geometric axis,
  magnetic axis or current centre);
- p' and ff' against normalised psi, now and at the start;
- the coil currents with the reference KCURR tracks, read from the run's
  simulink_log.csv (my_contr; see _read_reference).

Clicking on a time plot selects that time.

Use it for a recorder receiving NICE's equilibrium and pf_active, e.g.

    recorder_equilibrium.config: ${PDS_REPO}/visualization/nice_evo.py
    recorder_equilibrium.md: "wall=imas:hdf5?path=... pf_active=imas:hdf5?path=..."

(``md``: wall, vessel and coils of the plasma figure.)

Speed: while the run goes on, the recorder writes one Zarr chunk (one file)
per step and per variable, and the dashboard re-opens the stores every 2 s.
The time traces therefore read only the steps not plotted yet and append
them; the selected time reads one row of each variable.
"""

import logging
import re
from pathlib import Path

import matplotlib.tri as mtri
import numpy as np
import panel as pn
import param
import xarray as xr
import yaml
from bokeh.events import Tap
from bokeh.models import (
    BoxZoomTool,
    ColorBar,
    ColumnDataSource,
    DataRange1d,
    HoverTool,
    LinearColorMapper,
    PanTool,
    Range1d,
    ResetTool,
    SaveTool,
    Span,
    WheelZoomTool,
)
from bokeh.palettes import Viridis256
from bokeh.plotting import figure
from matplotlib.figure import Figure

from imas_muscle3.visualization.base_plotter import BasePlotter
from imas_muscle3.visualization.base_state import BaseState

# Picked up by name (not called here) by the dashboard's recorder viewer.
from imas_muscle3.visualization.md_loader import init_state  # noqa: F401

logger = logging.getLogger()

# ----------------------------------------------------------------------------
# What the recorder stores
# ----------------------------------------------------------------------------
N_OUTLINE = 101                      # boundary points per slice
N_X = 2                              # X-points per slice
PSI_N = np.linspace(0.0, 1.0, 51)    # grid of the stored profiles
SCALARS = ("ip", "r_geo", "z_geo", "r_axis", "z_axis", "r_cc", "z_cc")
PROFILES = ("dpressure_dpsi", "f_df_dpsi")

# Meshes already stored by this recorder process, and the last time seen
# (see State._extract_flux_map)
_GRIDS_SEEN = set()
_LAST_TIME = [None]


def _float(node):
    """A 0D IDS value as float, NaN when empty (IMAS stores -9e40)."""
    try:
        v = float(node)
    except (TypeError, ValueError):
        return np.nan
    return v if np.isfinite(v) and v > -1e39 else np.nan


def _array(node):
    """An IDS array as a flat float numpy array (empty -> size 0)."""
    try:
        a = np.asarray(node, dtype=float).ravel()
    except (TypeError, ValueError):
        return np.array([])
    return np.where(a < -1e39, np.nan, a)


def _fixed(values, n):
    """values truncated or NaN-padded to length n."""
    out = np.full(n, np.nan)
    values = np.asarray(values, dtype=float).ravel()[:n]
    out[: values.size] = values
    return out


def _resample_closed(r, z, n):
    """Closed curve resampled to n points evenly spaced along its length."""
    ok = np.isfinite(r) & np.isfinite(z)
    r, z = r[ok], z[ok]
    if r.size < 3:
        return np.full(n, np.nan), np.full(n, np.nan)
    if np.hypot(r[-1] - r[0], z[-1] - z[0]) > 1e-9:
        r, z = np.append(r, r[0]), np.append(z, z[0])
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(r), np.diff(z)))])
    s_new = np.linspace(0.0, s[-1], n)
    return np.interp(s_new, s, r), np.interp(s_new, s, z)


def _short_name(name):
    """'Central Solenoid 3U (CS3U)' -> 'CS3U'."""
    m = re.search(r"\(([^()]+)\)\s*$", str(name))
    return m.group(1).strip() if m else str(name).strip()


def _finite(*arrays):
    """Flatten the arrays and keep the points where all are finite."""
    arrays = [np.ravel(np.asarray(a, dtype=float)) for a in arrays]
    ok = np.logical_and.reduce([np.isfinite(a) for a in arrays])
    return [a[ok] for a in arrays]


def _one_per_time(obj):
    """Sorted by time, one entry per time (the last one written)."""
    index = obj.indexes["time"]
    if not index.is_unique:
        obj = obj.drop_duplicates("time", keep="last")
        index = obj.indexes["time"]
    return obj if index.is_monotonic_increasing else obj.sortby("time")


def _grid_key(r, z):
    """Cheap fingerprint of a mesh."""
    half = r.size // 2
    return (r.size, float(np.sum(r)), float(np.sum(z)), float(np.sum(r[:half])), float(np.sum(z[:half])))


_CENTROID_MESH = {}     # _grid_key -> (triangles, areas, R and Z of the triangle centres)


def _mesh_centroid(ts):
    """Exact current centre, as current_centre_estimate.m computes it: the
    j_phi-weighted centroid of NICE's mesh current density (ggd j_phi on the nodes
    ggd r, z), linear on the Delaunay triangles of the nodes. NaN without mesh data."""
    if not (len(ts.ggd) and len(ts.ggd[0].j_phi) and len(ts.ggd[0].r) and len(ts.ggd[0].z)):
        return np.nan, np.nan
    g = ts.ggd[0]
    r, z, j = _array(g.r[0].values), _array(g.z[0].values), _array(g.j_phi[0].values)
    if not (r.size >= 3 and r.size == z.size == j.size and np.all(np.isfinite(r) & np.isfinite(z))):
        return np.nan, np.nan
    key = _grid_key(r, z)
    if key not in _CENTROID_MESH:
        tri = mtri.Triangulation(r, z).triangles
        x, y = r[tri], z[tri]
        area = 0.5 * np.abs((x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0]))
        _CENTROID_MESH[key] = (tri, area, x.mean(axis=1), y.mean(axis=1))
    tri, area, rm, zm = _CENTROID_MESH[key]
    j = np.where(np.isfinite(j) & (np.abs(j) < 1e30), j, 0.0)
    di = j[tri].mean(axis=1) * area     # current in each triangle
    total = di.sum()
    if total == 0:
        return np.nan, np.nan
    return float(np.sum(rm * di) / total), float(np.sum(zm * di) / total)


def _current_centre(ts, r_geo, z_geo):
    """Current centre as the controller takes it (muscle_nice2control.m):
    global_quantities.current_centre when filled (NICE leaves it empty), else as
    current_centre_estimate.m computes it (exact from the mesh j_phi, else estimated
    from profiles_1d: flux-surface geometric axes weighted by j_phi*dA), else the
    boundary geometric axis."""
    cc = ts.global_quantities.current_centre
    r, z = _float(cc.r), _float(cc.z)
    if np.isfinite(r) and r > 0:
        return r, z
    r, z = _mesh_centroid(ts)
    if np.isfinite(z):
        return r, z
    p = ts.profiles_1d
    j = _array(p.j_phi) if hasattr(p, "j_phi") else np.array([])
    if not j.size and hasattr(p, "j_tor"):
        j = _array(p.j_tor)    # DD3 name
    a, rg, zg = _array(p.area), _array(p.geometric_axis.r), _array(p.geometric_axis.z)
    if a.size >= 2 and j.size == rg.size == zg.size == a.size:
        di = 0.5 * (j[:-1] + j[1:]) * np.diff(a)     # current between adjacent surfaces
        rm, zm = 0.5 * (rg[:-1] + rg[1:]), 0.5 * (zg[:-1] + zg[1:])
        ok = np.isfinite(di) & np.isfinite(rm) & np.isfinite(zm)
        if ok.any() and np.sum(di[ok]) != 0:
            return (float(np.sum(rm[ok] * di[ok]) / np.sum(di[ok])),
                    float(np.sum(zm[ok] * di[ok]) / np.sum(di[ok])))
    return r_geo, z_geo


class State(BaseState):
    def extract(self, message):
        name = message.metadata.name
        if name == "equilibrium":
            self._extract_equilibrium(message)
        elif name == "pf_active":
            self._extract_pf_active(message)

    def _store(self, key, new):
        current = self.data.get(key)
        if current is None:
            self.data[key] = new
        else:
            combined = xr.concat([current, new], dim="time", join="outer")
            self.data[key] = combined.drop_duplicates("time", keep="last")

    def _extract_pf_active(self, ids):
        times = _array(ids.time)
        if times.size == 0:
            return
        names = [str(c.name.value) for c in ids.coil]
        currents = np.full((times.size, len(names)), np.nan)
        for k, coil in enumerate(ids.coil):
            currents[:, k] = _fixed(_array(coil.current.data), times.size)
        self._store("pf_active", xr.Dataset({"currents": (("time", "coil"), currents)},
                                            coords={"time": times, "coil": names}))

    def _extract_equilibrium(self, ids):
        # A live stream sends one slice per message; an inverse loop can send
        # a whole trace. Handle both.
        times = _array(ids.time)
        for i, ts in enumerate(ids.time_slice):
            t = _float(ts.time)
            if np.isnan(t) and i < times.size:
                t = times[i]
            if np.isnan(t):
                continue
            self._extract_slice(ts, t)
            self._extract_flux_map(ts, t)

    def _extract_slice(self, ts, t):
        gq, b, prof = ts.global_quantities, ts.boundary, ts.profiles_1d
        r_geo, z_geo = _float(b.geometric_axis.r), _float(b.geometric_axis.z)
        r_cc, z_cc = _current_centre(ts, r_geo, z_geo)
        scalars = {
            "ip": _float(gq.ip),
            "r_geo": r_geo, "z_geo": z_geo,
            "r_axis": _float(gq.magnetic_axis.r), "z_axis": _float(gq.magnetic_axis.z),
            "r_cc": r_cc, "z_cc": z_cc,
        }
        boundary = np.array(_resample_closed(_array(b.outline.r), _array(b.outline.z), N_OUTLINE))

        x_r, x_z = [], []
        for node in ts.contour_tree.node:
            if _float(node.critical_type) == 1:
                x_r.append(_float(node.r))
                x_z.append(_float(node.z))
        x_points = np.array([_fixed(x_r, N_X), _fixed(x_z, N_X)])

        # Profiles on a fixed psi_N grid
        psi = _array(prof.psi)
        psi_0 = _float(gq.psi_axis)
        psi_1 = _float(b.psi)
        if np.isnan(psi_1):
            psi_1 = _float(gq.psi_boundary)
        profiles = np.full((len(PROFILES), PSI_N.size), np.nan)
        if psi.size >= 2:
            psi_0 = psi_0 if np.isfinite(psi_0) else psi[0]
            psi_1 = psi_1 if np.isfinite(psi_1) else psi[-1]
            if psi_1 != psi_0:
                psin = (psi - psi_0) / (psi_1 - psi_0)
                for j, key in enumerate(PROFILES):
                    values = _array(getattr(prof, key))
                    if values.size != psi.size:
                        continue
                    ok = np.isfinite(psin) & np.isfinite(values)
                    if ok.sum() >= 2:
                        order = np.argsort(psin[ok])
                        profiles[j] = np.interp(PSI_N, psin[ok][order], values[ok][order],
                                                left=np.nan, right=np.nan)

        self._store(
            "equilibrium",
            xr.Dataset(
                {
                    "scalars": (("time", "quantity"), [[scalars[k] for k in SCALARS]]),
                    "boundary": (("time", "rz", "point"), [boundary]),
                    "x_points": (("time", "rz", "x"), [x_points]),
                    "profiles": (("time", "profile", "psi_n"), [profiles]),
                },
                coords={"time": [t], "quantity": list(SCALARS), "rz": ["r", "z"],
                        "profile": list(PROFILES), "psi_n": PSI_N},
            ),
        )

    def _extract_flux_map(self, ts, t):
        """psi on NICE's GGD mesh; the mesh itself only when it changes."""
        if not (len(ts.ggd) and len(ts.ggd[0].psi) and len(ts.ggd[0].r) and len(ts.ggd[0].z)):
            return
        g = ts.ggd[0]
        r, z, psi = _array(g.r[0].values), _array(g.z[0].values), _array(g.psi[0].values)
        if not (r.size and r.size == z.size == psi.size):
            return
        self._store("flux_map", xr.Dataset({"psi": (("time", "grid_point"), [psi])}, coords={"time": [t]}))
        # Time going back = the recorder starts a new store (next outer-loop
        # iteration), which needs its own copy of the mesh.
        if _LAST_TIME[0] is not None and t < _LAST_TIME[0]:
            _GRIDS_SEEN.clear()
        _LAST_TIME[0] = t
        key = _grid_key(r, z)
        if key not in _GRIDS_SEEN:
            _GRIDS_SEEN.add(key)
            self._store(
                "flux_grid",
                xr.Dataset(
                    {"grid_r": (("time", "grid_point"), [r]), "grid_z": (("time", "grid_point"), [z])},
                    coords={"time": [t]},
                ),
            )


# ----------------------------------------------------------------------------
# What the dashboard shows (plain Bokeh figures, updated in place)
# ----------------------------------------------------------------------------
TOOLS = "pan,box_zoom,wheel_zoom,reset,save"
BLUE = "#1f77b4"
TIME_HEIGHT = 170
PROFILE_HEIGHT = 230
COIL_HEIGHT = 160
PLOT_MIN_WIDTH = 300     # narrowest plot before its box wraps to a new row [px]
COIL_MIN_WIDTH = 230
FLUX_MAP_HEIGHT = 640    # plasma figure frame [px]; the width follows the machine

# magnetic_controller.plasma_position -> (R column, Z column, label)
POSITIONS = {
    "geometric_axis": ("r_geo", "z_geo", "geometric axis"),
    "magnetic_axis": ("r_axis", "z_axis", "magnetic axis"),
    "current_centre": ("r_cc", "z_cc", "current centre"),
}
# Time plots: (column, title, unit, smallest axis span shown)
TIME_PLOTS = (("ip", "|Ip|", "MA", 0.02), ("z", "Z", "m", 0.005), ("r", "R", "m", 0.005))
COIL_MIN_SPAN = 0.5      # [kA]
# coil -> KCURR circuit, the k of KCURR_actual_ref_<k> in my_contr's simulink_log.csv
REFERENCE_CIRCUIT = {"CS3U": 1, "CS2U": 2, "CS1U": 3, "CS1L": 3, "CS2L": 4, "CS3L": 5,
                     "PF1": 6, "PF2": 7, "PF3": 8, "PF4": 9, "PF5": 10, "PF6": 11}
# Profiles: (name, title, unit)
PROFILE_PLOTS = (("dpressure_dpsi", "p'", "Pa/Wb"), ("f_df_dpsi", "ff'", "T² m²/Wb"))


def _fmt(value, unit=""):
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{value:.4g}" + (f" {unit}" if unit else "")


def _pane(fig, min_width=PLOT_MIN_WIDTH):
    """A Bokeh figure as an item of a wrapping box, at least min_width wide.
    (The Column is needed: a Bokeh pane alone is replaced by the figure,
    which ignores the flex style.)"""
    return pn.Column(pn.pane.Bokeh(fig, sizing_mode="stretch_width"), sizing_mode="stretch_width",
                     min_width=min_width, styles={"flex": f"1 1 {min_width}px"}, margin=0)


def _box(*objects):
    return pn.FlexBox(*objects, flex_wrap="wrap", sizing_mode="stretch_width")


def _plot_box(panes, min_width=PLOT_MIN_WIDTH):
    """Wrapping box of plots. A few empty items of the same size close the
    last row, so that its plots keep the width of the others."""
    fillers = [pn.Spacer(height=0, min_width=min_width, sizing_mode="stretch_width", margin=0,
                         styles={"flex": f"1 1 {min_width}px"}) for _ in range(6)]
    return _box(*panes, *fillers)


def _figure(height, x_range=None, title=""):
    fig = figure(height=height, sizing_mode="stretch_width", tools=TOOLS, title=title,
                 x_range=x_range if x_range is not None else DataRange1d(),
                 y_range=DataRange1d(only_visible=True, range_padding=0.1), toolbar_location="right")
    fig.toolbar.autohide = True
    fig.toolbar.logo = None
    fig.toolbar.active_scroll = None   # the mouse wheel scrolls the page
    fig.title.text_font_size = "10pt"
    fig.min_border_left = 55
    return fig


def _span_points(data, min_spans):
    """Two invisible points per column that keep its axis at least min_span
    tall, centred on the data: an almost constant quantity would otherwise be
    blown up to its numerical noise."""
    t = np.asarray(data["time"], dtype=float)
    out = {"time": np.full(2, t[-1] if t.size else 0.0)}
    for name, span in min_spans.items():
        v = np.asarray(data.get(name, []), dtype=float)
        v = v[np.isfinite(v)]
        mid = 0.5 * (float(v.min()) + float(v.max())) if v.size else 0.0
        half = 0.5 * span if not v.size or np.ptp(v) < span else 0.0
        out[name] = np.array([mid - half, mid + half])
    return out


def _run_dir(ds):
    """Run directory of a recorder store (<run>/instances/<recorder>/workdir/<port>/
    <occurrence>.zarr)."""
    return Path(ds.encoding["source"]).parents[4]


def _controller_position(ds):
    """magnetic_controller.plasma_position of the run, read from its
    configuration.ymmsl; geometric_axis when unset, as in the controller."""
    try:
        settings = yaml.safe_load((_run_dir(ds) / "configuration.ymmsl").read_text())["settings"]
        position = str(settings.get("magnetic_controller.plasma_position", "geometric_axis"))
    except Exception:
        logger.warning("plasma_position of the run not found, showing the geometric axis", exc_info=True)
        return "geometric_axis"
    return position if position in POSITIONS else "geometric_axis"


class Plotter(BasePlotter):
    contours = param.Boolean(default=False, label="ψ contours")
    levels = param.Integer(default=20, bounds=(2, 100), doc="Number of contour levels")

    # -- layout ---------------------------------------------------------------
    def get_dashboard(self):
        self._seen_data = None
        self._shown = {}        # (group, variable) -> (samples, first time, last time) plotted
        self._first = {}        # rows at the first time, by (variable, first time)
        self._spans = []        # time cursors of all the time plots
        self._position = None   # controller position shown in Z/R
        self._coil_figs = {}
        self._src_refs = {}     # coil -> reference line source
        self._reference = {}    # coil -> (log times, KCURR reference [kA])
        self._ref_log_size = None   # size of the controller log when last read
        self._refs_drawn = set()    # coils whose reference line holds the last read
        self._x_range = DataRange1d(only_visible=True, range_padding=0.02)

        flux_map = self._build_flux_map()
        time_figs = self._build_time_plots()
        profile_figs = self._build_profile_plots()
        self._src_coils = ColumnDataSource({"time": []})
        self._src_coils_span = ColumnDataSource({"time": []})
        self._coil_box = _box(pn.pane.Markdown("**Waiting for coil currents...**"))

        contour_controls = pn.Row(
            pn.widgets.Checkbox.from_param(self.param.contours, margin=(12, 10)),
            pn.widgets.IntSlider.from_param(self.param.levels, name="Levels", width=220,
                                            visible=self.param.contours),
        )
        right = pn.Column(
            *[pn.pane.Bokeh(f, sizing_mode="stretch_width") for f in time_figs],
            _plot_box([_pane(f) for f in profile_figs]),
            sizing_mode="stretch_width", min_width=2 * PLOT_MIN_WIDTH,
            styles={"flex": f"1 1 {2 * PLOT_MIN_WIDTH}px"},
        )
        return pn.Column(
            _box(pn.Column(contour_controls, pn.pane.Bokeh(flux_map)), right),
            self._coil_box,
            sizing_mode="stretch_width",
        )

    def _add_time_tools(self, fig, line, label, tooltip):
        """Time cursor, hover readout and click-to-select-time of a time plot."""
        span = Span(location=self.time, dimension="height", line_color="black", line_dash="dotted",
                    line_width=1.5)
        fig.add_layout(span)
        self._spans.append(span)
        fig.add_tools(HoverTool(renderers=[line], mode="vline",
                                tooltips=[("t", "@time{0.0000} s"), (label, tooltip)]))
        fig.on_event(Tap, self._on_tap)

    def _build_time_plots(self):
        columns = ["time"] + [c for c, *_ in TIME_PLOTS]
        self._src_scalars = ColumnDataSource({c: [] for c in columns})
        self._src_scalars_span = ColumnDataSource({c: [] for c in columns})
        self._time_figs = {}
        for column, title, unit, _ in TIME_PLOTS:
            fig = _figure(TIME_HEIGHT, self._x_range)
            line = fig.line("time", column, source=self._src_scalars, line_width=2, color=BLUE)
            fig.scatter("time", column, source=self._src_scalars_span, alpha=0)
            self._add_time_tools(fig, line, title, f"@{{{column}}}{{0.0000}} {unit}")
            self._time_figs[column] = [fig, title, unit]
        return [f for f, *_ in self._time_figs.values()]

    def _build_profile_plots(self):
        columns = ["psi_n"] + [f"{p}_{w}" for p, *_ in PROFILE_PLOTS for w in ("now", "first")]
        self._src_profiles = ColumnDataSource({c: [] for c in columns})
        self._profile_figs = []
        for name, title, unit in PROFILE_PLOTS:
            fig = _figure(PROFILE_HEIGHT, title=f"{title} [{unit}]")
            fig.line("psi_n", f"{name}_first", source=self._src_profiles, line_width=2, color="grey",
                     line_dash="dashed", legend_label="start")
            fig.line("psi_n", f"{name}_now", source=self._src_profiles, line_width=2, color=BLUE,
                     legend_label="selected time")
            fig.xaxis.axis_label = "ψ_N"
            fig.legend.location = "top_left"
            fig.legend.label_text_font_size = "8pt"
            fig.legend.background_fill_alpha = 0.5
            self._profile_figs.append(fig)
        return self._profile_figs

    def _build_flux_map(self):
        md = getattr(self._state, "md", None) or {}
        limiter, vessel, quads, coil_paths = self._machine(md)

        # Window: the machine with a margin, or a default ITER-sized box; the
        # frame has the shape of the window, so R and Z have the same scale.
        r_pts = [r for r, _ in limiter + vessel + coil_paths] + [np.array([q[0], q[1]]) for q in quads]
        z_pts = [z for _, z in limiter + vessel + coil_paths] + [np.array([q[2], q[3]]) for q in quads]
        r_all, z_all = _finite(np.concatenate(r_pts), np.concatenate(z_pts)) if r_pts else ([], [])
        if len(r_all):
            x0, x1 = max(0.0, float(np.min(r_all)) - 0.5), float(np.max(r_all)) + 0.5
            y0, y1 = float(np.min(z_all)) - 0.5, float(np.max(z_all)) + 0.5
        else:
            x0, x1, y0, y1 = 1.0, 13.0, -9.0, 9.0
        frame_width = round(FLUX_MAP_HEIGHT * (x1 - x0) / (y1 - y0))

        fig = figure(frame_height=FLUX_MAP_HEIGHT, frame_width=frame_width, x_range=Range1d(x0, x1),
                     y_range=Range1d(y0, y1), title="Plasma", toolbar_location="above",
                     tools=[PanTool(), WheelZoomTool(), BoxZoomTool(match_aspect=True), ResetTool(), SaveTool()])
        fig.toolbar.logo = None
        fig.xaxis.axis_label = "R [m]"
        fig.yaxis.axis_label = "Z [m]"

        self._src_contours = ColumnDataSource({"xs": [], "ys": [], "color": [], "psi": []})
        contours = fig.multi_line("xs", "ys", line_color="color", line_width=1, source=self._src_contours)
        fig.add_tools(HoverTool(renderers=[contours], tooltips=[("ψ", "@psi{0.000} Wb")]))
        self._color_mapper = LinearColorMapper(palette=Viridis256, low=0, high=1)
        self._color_bar = ColorBar(color_mapper=self._color_mapper, title="ψ [Wb]", width=10, visible=False)
        fig.add_layout(self._color_bar, "right")

        if limiter:
            fig.multi_line([r for r, _ in limiter], [z for _, z in limiter], line_color="black", line_width=2)
        if vessel:
            fig.multi_line([r for r, _ in vessel], [z for _, z in vessel], line_color="grey", line_width=1)
        if quads:
            src = ColumnDataSource({k: [q[i] for q in quads] for i, k in
                                    enumerate(("left", "right", "bottom", "top", "name"))})
            coils = fig.quad(left="left", right="right", bottom="bottom", top="top", source=src,
                             fill_color="lightgrey", fill_alpha=0.5, line_color="black")
            fig.add_tools(HoverTool(renderers=[coils], tooltips=[("coil", "@name")]))
        if coil_paths:
            fig.multi_line([r for r, _ in coil_paths], [z for _, z in coil_paths], line_color="black")

        self._src_b0, self._src_b, self._src_x = (ColumnDataSource({"x": [], "y": []}) for _ in range(3))
        fig.line("x", "y", source=self._src_b, color="red", line_width=3, legend_label="boundary")
        fig.line("x", "y", source=self._src_b0, color="grey", line_dash="dashed", line_width=2,
                 legend_label="boundary at start")
        fig.scatter("x", "y", source=self._src_x, marker="x", size=12, color="black", line_width=2,
                    legend_label="X-point")
        legend = fig.legend[0]
        legend.orientation = "horizontal"
        legend.label_text_font_size = "8pt"
        legend.border_line_alpha = 0
        fig.add_layout(legend, "below")
        return fig

    @staticmethod
    def _machine(md):
        """Limiter, vessel, coil rectangles and coil outlines from the
        machine description (empty lists without one)."""
        limiter, vessel, quads, coil_paths = [], [], [], []
        wall = md.get("wall")
        if wall is not None and len(wall.description_2d):
            d2 = wall.description_2d[0]
            for unit in d2.limiter.unit:
                limiter.append((_array(unit.outline.r), _array(unit.outline.z)))
            for unit in d2.vessel.unit:
                vessel.append((_array(unit.annular.centreline.r), _array(unit.annular.centreline.z)))
        pf = md.get("pf_active")
        if pf is not None:
            for coil in pf.coil:
                name = _short_name(coil.name.value)
                for element in coil.element:
                    geo = element.geometry
                    rect, outline, ann = geo.rectangle, geo.outline, geo.annulus
                    if _float(rect.width) > 0 and _float(rect.height) > 0:
                        r0, z0, w, h = _float(rect.r), _float(rect.z), _float(rect.width), _float(rect.height)
                        quads.append((r0 - w / 2, r0 + w / 2, z0 - h / 2, z0 + h / 2, name))
                    elif _array(outline.r).size:
                        coil_paths.append((_array(outline.r), _array(outline.z)))
                    elif _float(ann.radius_outer) > 0:
                        phi = np.linspace(0, 2 * np.pi, 17)
                        coil_paths.append((_float(ann.r) + _float(ann.radius_outer) * np.cos(phi),
                                           _float(ann.z) + _float(ann.radius_outer) * np.sin(phi)))
        return limiter, vessel, quads, coil_paths

    def _set_coil_figures(self, names):
        """One small plot per coil: current (blue) and reference (black, dashed)."""
        self._coil_figs = {}
        self._src_refs = {}
        for name in names:
            fig = _figure(COIL_HEIGHT, self._x_range, f"{name} [kA]")
            line = fig.line("time", name, source=self._src_coils, line_width=2, color=BLUE)
            self._src_refs[name] = ColumnDataSource({"time": [], "i": []})
            fig.line("time", "i", source=self._src_refs[name], line_width=1.5, color="black", line_dash="dashed")
            fig.scatter("time", name, source=self._src_coils_span, alpha=0)
            self._add_time_tools(fig, line, name, f"@{{{name}}}{{0.000}} kA")
            self._coil_figs[name] = fig
        self._coil_box.objects = _plot_box([_pane(f, COIL_MIN_WIDTH) for f in self._coil_figs.values()],
                                           COIL_MIN_WIDTH).objects

    # -- data access ----------------------------------------------------------
    # The viewer reads the Zarr stores while the recorder writes them, so a
    # read can fail for one refresh: the helpers return None instead of
    # raising, and the plots keep their previous content.
    def _new_rows(self, group, name):
        """(rows, True): the samples of group/name not plotted yet, to append;
        (rows, False): all of them, to replace the plot (first call, or a store
        that changed other than by growing); (None, False): nothing new."""
        ds = self._state.data.get(group)
        if ds is None or name not in ds:
            return None, False
        key = (group, name)
        try:
            times = np.asarray(ds.time.values, dtype=float)
            if not times.size:
                return None, False
            n, t_first, t_last = self._shown.get(key, (0, None, None))
            same_start = n > 0 and times.size >= n and times[0] == t_first and times[n - 1] == t_last
            if same_start and times.size == n:
                return None, False
            grown = same_start and bool(np.all(np.diff(times[n - 1:]) > 0))
            rows = ds[name].isel(time=slice(n, None)) if grown else _one_per_time(ds[name])
            rows = rows.load()
        except Exception:
            logger.debug("%s/%s not readable", group, name, exc_info=True)
            return None, False
        self._shown[key] = (times.size, times[0], times[-1])
        return rows, grown

    def _row(self, group, name, where="now"):
        """One row of group/name: at the selected time ("now") or the first one
        (cached)."""
        ds = self._state.data.get(group)
        if ds is None or name not in ds:
            return None
        try:
            da = _one_per_time(ds[name])
            if where == "now":
                return da.sel(time=self.time, method="nearest").load()
            key = (group, name, float(da.time[0]))
            if key not in self._first:
                self._first[key] = da.isel(time=0).load()
            return self._first[key]
        except Exception:
            logger.debug("%s/%s not readable at t=%s", group, name, self.time, exc_info=True)
            return None

    # -- interaction ----------------------------------------------------------
    def _on_tap(self, event):
        """Click on a time plot: select the nearest recorded time (and leave
        live view, otherwise the next data update moves the time again)."""
        times = np.asarray(self.time_slider_widget.options, dtype=float)
        if event.x is None or not times.size:
            return
        self._live_view = False
        self.time = float(times[int(np.argmin(np.abs(times - event.x)))])

    # -- new data -------------------------------------------------------------
    @param.depends("_state.data", watch=True)
    def _update_on_new_data(self):
        """New data from the recorder: extend the time traces, then let the
        base class move the time (live view) and redraw the selected time."""
        # The recorder viewer sets the data and then triggers it again: skip
        # the second, identical, update (same datasets).
        data = self._state.data
        seen = self._seen_data
        if seen is not None and seen.keys() == data.keys() and all(seen[k] is data[k] for k in data):
            return
        self._seen_data = dict(data)   # keeps them alive, so the check above can trust "is"

        self._check_contour_cache()
        self._refresh_scalars()
        self._refresh_coils()
        before = self.time
        super()._update_on_new_data()
        if self.time == before:     # otherwise _on_time already ran
            self._on_time()

    def _refresh_scalars(self):
        if self._position is None and "equilibrium" in self._state.data:
            self._position = _controller_position(self._state.data["equilibrium"])
            label = POSITIONS[self._position][2]
            self._time_figs["z"][1] = f"Z {label}"
            self._time_figs["r"][1] = f"R {label}"
        rows, grown = self._new_rows("equilibrium", "scalars")
        if rows is None:
            return
        r_col, z_col, _ = POSITIONS[self._position]
        cols = {
            "time": np.asarray(rows.time.values, dtype=float),
            "ip": np.abs(rows.sel(quantity="ip").values) / 1e6,
            "z": rows.sel(quantity=z_col).values,
            "r": rows.sel(quantity=r_col).values,
        }
        if grown:
            self._src_scalars.stream(cols)
        else:
            self._src_scalars.data = cols
        self._src_scalars_span.data = _span_points(self._src_scalars.data, {c: s for c, _, _, s in TIME_PLOTS})

    def _refresh_coils(self):
        rows, grown = self._new_rows("pf_active", "currents")
        if rows is None:
            return
        names = [_short_name(n) for n in rows.coil.values]
        values = np.asarray(rows.values, dtype=float) / 1e3
        cols = {"time": np.asarray(rows.time.values, dtype=float)}
        cols.update({n: values[:, k] for k, n in enumerate(names)})
        if grown:
            self._src_coils.stream(cols)
        else:
            self._src_coils.data = cols
        self._src_coils_span.data = _span_points(self._src_coils.data, dict.fromkeys(names, COIL_MIN_SPAN))
        if list(self._coil_figs) != names:
            self._set_coil_figures(names)
        self._update_reference_lines()

    def _read_reference(self):
        """The references KCURR tracks, from the run's simulink_log.csv (my_contr's
        log, one row per controller step, written live): {coil: (times, current
        [kA])}, CS1U and CS1L on the CS1 circuit, none for VS3. Re-read only when the
        log has grown; returns whether it was."""
        ds = self._state.data.get("pf_active")
        try:
            log = _run_dir(ds) / "simulink_log.csv"
            size = log.stat().st_size
        except Exception:
            return False
        if size == self._ref_log_size:
            return False
        try:
            with open(log) as f:
                head = f.readline().strip().split(",")
            # a row still being written has too few columns and is skipped
            data = np.genfromtxt(log, delimiter=",", skip_header=1, ndmin=2, invalid_raise=False)
        except Exception:
            logger.warning("controller log %s not readable, keeping the previous reference", log)
            return False
        self._ref_log_size = size
        if not data.size or "t" not in head:
            return False
        t = data[:, head.index("t")]
        self._reference = {}
        for coil, k in REFERENCE_CIRCUIT.items():
            column = f"KCURR_actual_ref_{k}"
            if column in head:
                self._reference[coil] = (t, data[:, head.index(column)] / 1e3)
        return True

    def _update_reference_lines(self):
        """Reference lines: redrawn when the controller log has grown or the coil
        figures are new."""
        if not self._read_reference() and self._refs_drawn == set(self._src_refs):
            return
        for name, src in self._src_refs.items():
            if name in self._reference:
                t, i = self._reference[name]
                src.data = {"time": t, "i": i}
        self._refs_drawn = set(self._src_refs)

    # -- selected time --------------------------------------------------------
    @param.depends("time", watch=True)
    def _on_time(self):
        for span in self._spans:
            span.location = self.time
        self._update_titles()
        self._update_plasma()
        self._update_profiles()

    @param.depends("contours", "levels", watch=True)
    def _on_contours(self):
        self._color_bar.visible = self.contours
        self._update_contours()

    def _index(self, times):
        times = np.asarray(times, dtype=float)
        return int(np.argmin(np.abs(times - self.time))) if times.size else None

    def _update_titles(self):
        data = self._src_scalars.data
        k = self._index(data["time"])
        for column, (fig, title, unit) in self._time_figs.items():
            value = float(data[column][k]) if k is not None else None
            fig.title.text = f"{title} = {_fmt(value, unit)}"
        data = self._src_coils.data
        k = self._index(data["time"])
        if k is None:
            return
        for name, fig in self._coil_figs.items():
            text = f"{name} = {_fmt(float(data[name][k]), 'kA')}"
            if name in self._reference:
                td, idata = self._reference[name]
                text += f"  (ref {_fmt(float(np.interp(self.time, td, idata)), 'kA')})"
            fig.title.text = text

    def _update_plasma(self):
        for src, b in ((self._src_b0, self._row("equilibrium", "boundary", "first")),
                       (self._src_b, self._row("equilibrium", "boundary"))):
            x, y = _finite(b.sel(rz="r").values, b.sel(rz="z").values) if b is not None else ([], [])
            src.data = {"x": x, "y": y}
        xp = self._row("equilibrium", "x_points")
        x, y = _finite(xp.sel(rz="r").values, xp.sel(rz="z").values) if xp is not None else ([], [])
        self._src_x.data = {"x": x, "y": y}
        self._update_contours()

    def _update_profiles(self):
        now = self._row("equilibrium", "profiles")
        first = self._row("equilibrium", "profiles", "first")
        if now is None:
            return
        cols = {"psi_n": PSI_N}
        for name, *_ in PROFILE_PLOTS:
            cols[f"{name}_now"] = now.sel(profile=name).values
            cols[f"{name}_first"] = first.sel(profile=name).values if first is not None else np.full(PSI_N.size, np.nan)
        self._src_profiles.data = cols
        for fig, (_, title, unit) in zip(self._profile_figs, PROFILE_PLOTS, strict=True):
            fig.title.text = f"{title} [{unit}] at t = {float(now.time):.4f} s"
            if first is not None:
                fig.legend.items[0].label = {"value": f"start ({float(first.time):.4f} s)"}

    # -- psi contours (only when switched on) -----------------------------------
    def _check_contour_cache(self):
        """Keep cached contours while the run only grows (live view); drop
        them when data of times already seen may have changed (another
        occurrence selected, or a store rebuilt by the recorder)."""
        ds = self._state.data.get("flux_map") if self._state is not None else None
        n = ds.sizes.get("time", 0) if ds is not None else 0
        t_first = float(ds.time[0]) if n else None
        seen_n, seen_first = self.__dict__.get("_cache_key", (0, None))
        if n < seen_n or t_first != seen_first:
            self.__dict__.setdefault("_contour_cache", {}).clear()
            self.__dict__.setdefault("_grid_cache", {}).clear()
        self.__dict__["_cache_key"] = (n, t_first)

    def _mesh(self, t):
        """(valid-point mask, triangulation) of the mesh in use at time t."""
        ds = self._state.data.get("flux_grid")
        if ds is None:
            return None
        times = ds.time.values
        k = min(max(int(np.searchsorted(times, t, side="right")) - 1, 0), times.size - 1)
        cache = self.__dict__.setdefault("_grid_cache", {})
        if times[k] not in cache:
            try:
                r = np.asarray(ds["grid_r"].isel(time=k).load().values, dtype=float)
                z = np.asarray(ds["grid_z"].isel(time=k).load().values, dtype=float)
                ok = np.isfinite(r) & np.isfinite(z)
                cache[times[k]] = (ok, mtri.Triangulation(r[ok], z[ok]))
            except Exception:
                logger.warning("Mesh at t=%s not usable", times[k], exc_info=True)
                return None
        return cache[times[k]]

    def _update_contours(self):
        if not self.contours:
            self._src_contours.data = {"xs": [], "ys": [], "color": [], "psi": []}
            return
        psi = self._row("flux_map", "psi")
        if psi is None:
            return
        t = float(psi.time)
        cache = self.__dict__.setdefault("_contour_cache", {})
        key = (t, self.levels)
        if key not in cache:
            if len(cache) > 300:
                cache.clear()
            cache[key] = self._calc_contours(t, np.asarray(psi.values, dtype=float), self.levels)
        xs, ys, levels = cache[key]
        colors = []
        if levels:
            low, high = min(levels), max(levels)
            self._color_mapper.update(low=low, high=high if high > low else low + 1.0)
            colors = [Viridis256[round(255 * (lev - low) / ((high - low) or 1.0))] for lev in levels]
        self._src_contours.data = {"xs": xs, "ys": ys, "color": colors, "psi": levels}

    def _calc_contours(self, t, psi, levels):
        """Contour lines of psi: (list of R arrays, list of Z arrays, levels)."""
        mesh = self._mesh(t)
        if mesh is None:
            return [], [], []
        ok, tri = mesh
        if psi.size != ok.size:
            return [], [], []
        psi = psi[ok]
        if not np.isfinite(psi).all():
            # NaN breaks tricontour: drop the triangles that touch one
            bad = ~np.isfinite(psi)
            tri = mtri.Triangulation(tri.x, tri.y, tri.triangles, mask=bad[tri.triangles].any(axis=1))
            psi = np.where(bad, np.nanmean(psi), psi)
        try:
            # A private Figure, not pyplot: pyplot keeps every call in one
            # global figure that grows in a long-running dashboard.
            cs = Figure().add_subplot().tricontour(tri, psi, levels=levels)
        except (RuntimeError, ValueError):
            logger.warning("Contours skipped at t=%s", t, exc_info=True)
            return [], [], []
        xs, ys, lv = [], [], []
        for level, segs in zip(cs.levels, cs.allsegs, strict=False):
            for seg in segs:
                if len(seg) > 1:
                    xs.append(seg[:, 0])
                    ys.append(seg[:, 1])
                    lv.append(float(level))
        return xs, ys, lv
