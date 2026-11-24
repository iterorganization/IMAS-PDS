"""Plot gyrokinetically relevant TORAX profiles, scrollable in time.

By default this writes, to ``--output_dir``:

* ``gyrokinetics_<shot>.html``: the figure for all plotted time slices; drag its time
  slider or use the play controls below it. Works headless (e.g. from
  ``postprocess.sh`` under sbatch); open it in a browser.
* ``gyrokinetics_<shot>_t=<time>.png``: the figure at each slider time.

Several ``--torax_uri`` can be given to overlay runs, one colour per run. With
``--nice_uri`` (one per run) the NICE equilibrium (boundary, magnetic axis, q and
magnetic shear) is overlaid in the same colour, dotted.

With ``--interactive`` the same figure is shown in a matplotlib window instead.
"""

import argparse
from contextlib import ExitStack
from pathlib import Path

import matplotlib

import matplotlib.pyplot as plt
import numpy as np
from imas import DBEntry
from imas.ids_toplevel import IDSToplevel
from matplotlib.animation import FuncAnimation
from matplotlib.lines import Line2D
from matplotlib.widgets import Slider

qe = 1.602176565e-19  # electron charge [C]
me = 9.10938291e-31  # electron mass [kg]
mp = 1.672621777e-27  # proton mass [kg]


def calc_c1(zeff, ne, q, Ro, Rmin, x):
    r"""Calculate part of the normalized collision frequency :math:`\nu^*`

    Args:
        zeff: Effective ion charge [-]
        ne: Electron density [1e19 m^-3]
        q: Safety factor [-]
        Ro: Midplane-averaged major radius of last-closed-flux-surface, QuaLiKiz internal [m]
        Rmin: Midplane-averaged minor radius of last-closed-flux-surface [m]
        x: Normalized radius [m] :math:`\frac{r_{\text{out}} + r_{\text{in}}}{r_{\text{out,LCFS}} + r_{\text{in,LCFS}}}`
    """
    c1 = 6.9224e-5 * zeff * ne * q * Ro * (Rmin * x / Ro) ** -1.5
    return c1


def calc_c2(ne):
    r"""Calculate part of the normalized collision frequency :math:`\nu^*`

    Args:
        ne: Electron density [1e19 m^-3]
    """
    c2 = 15.2 - 0.5 * np.log(0.1 * ne)
    return c2


def calc_lambda_e(ne, Te):
    r"""Calculate the Coulomb constant :math:`\Lambda_e`

    Args:
        ne: Electron density [1e19 m^-3]
        Te: Electron temperature [keV]
    """
    # From QLK source:
    # Lambe(:) = 15.2_DBL - 0.5_DBL*LOG(0.1_DBL*Nex(:)) + LOG(Tex(:))  !Coulomb constant and collisionality. Wesson 2nd edition p661-663
    c2 = calc_c2(ne)
    return c2 + np.log(Te)


def calc_nu_e(ne, Te, zeff, collmult=1):
    r"""Calculate the collision frequency :math:`\nu_e`

    Args:
        ne: Electron density [1e19 m^-3]
        Te: Electron temperature [keV]
        zeff: Effective ion charge [-]
    Kwargs:
        collmult: Collision strength multiplier [-] (QuaLiKiz debugging)
    """
    # From QLK source:
    # Nue(:) = 1._DBL/(1.09d-3) *Zeffx(:)*Nex(:)*Lambe(:)/(Tex(:))**1.5_DBL*collmult
    lambda_e = calc_lambda_e(ne, Te)
    return 1 / 1.09e-3 * zeff * ne * lambda_e / Te**1.5 * collmult


def calc_tau_bounce(Te, q, Ro, Rmin, x):
    r"""Calculate the QuaLiKiz bounce frequency :math:`\Lambda_e`

    x is in QuaLiKiz units: :wiki:`Input-and-output-variables#geometry`

    .. math:: \frac{r_{out} + r_{out,LCFS}}{r_{out,LCFS} + r_{in,LCFS}}

    Args:
        Te: Electron temperature [keV]
        q: Safety factor [-]
        Ro: Midplane-averaged major radius of last-closed-flux-surface, QuaLiKiz internal [m]
        Rmin: Midplane-averaged minor radius of last-closed-flux-surface [m]
        x: Normalized radius [m]
    """
    # From QLK source:
    # Nustar(:) = Nue(:)*qx(:)*Ro(:)/epsilon(:)**1.5/(SQRT(Tex(:)*1.d3*qe/me))
    epsilon = Rmin * x / Ro
    return q * Ro / (epsilon**1.5 * np.sqrt(Te * 1e3 * qe / me))


def handle_args():
    parser = argparse.ArgumentParser(
        description="Plot gyrokinetically relevant profiles with a time slider"
    )
    parser.add_argument("--shot_nr", type=int, help="Shot number")
    parser.add_argument(
        "--dina_uri", type=str, help="URI to load DINA output data from"
    )
    parser.add_argument(
        "--nice_uri",
        type=str,
        nargs="+",
        action="extend",
        help=(
            "URI(s) to load NICE output data from, one per --torax_uri in the same order "
            "('none' for a run without NICE output); overlaid on that run's TORAX data"
        ),
    )
    parser.add_argument(
        "--metis_uri", type=str, help="URI to load METIS output data from"
    )
    parser.add_argument(
        "--torax_uri",
        type=str,
        nargs="+",
        action="extend",
        help="URI(s) to load TORAX output data from; give several to overlay runs",
    )
    parser.add_argument(
        "--labels",
        type=str,
        nargs="+",
        help="Legend label per --torax_uri (default: the run directory names)",
    )
    parser.add_argument(
        "--output_dir", type=str, help="path to directory in which to put plots"
    )
    parser.add_argument("--t_list", type=int, nargs="+", help="List of times to plot")
    parser.add_argument(
        "--max_slices",
        type=int,
        default=3,
        help=(
            "Number of evenly spaced times on the slider (default: 3). Each run's first, "
            "middle and last time slice are always included as well"
        ),
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Open a matplotlib window with a time slider instead of writing files",
    )
    args = parser.parse_args()
    if not args.interactive and args.output_dir is None:
        parser.error("--output_dir is required unless --interactive is given")
    if not args.torax_uri:
        parser.error("--torax_uri is required")
    if args.nice_uri is not None and len(args.nice_uri) != len(args.torax_uri):
        parser.error("give one --nice_uri entry per --torax_uri (use 'none' to skip one)")
    if args.labels is not None and len(args.labels) != len(args.torax_uri):
        parser.error("give one --labels entry per --torax_uri")
    return args


def run_label(uri: str) -> str:
    """Name of the run a URI belongs to: the run directory for .../<run>/out_torax"""
    path = Path(uri.split("path=")[-1].rstrip("/"))
    return path.parent.name if path.name.startswith("out_") else path.name


def short_labels(labels: list[str]) -> list[str]:
    """Drop the "_"-separated prefix all labels share (e.g. workflow_shot_), if any"""
    if len(labels) < 2:
        return labels
    parts = [label.split("_") for label in labels]
    n = 0
    while all(len(p) > n + 1 and p[n] == parts[0][n] for p in parts):
        n += 1
    return ["_".join(p[n:]) for p in parts]


def merge_times(times, tol=1e-6):
    """Sorted times with (near-)duplicates merged"""
    times = np.sort(np.asarray(times, dtype=float))
    keep = np.concatenate([[True], np.diff(times) > tol])
    return times[keep]


def load_nice(nice_eq: IDSToplevel, nice_time, time_val: float) -> dict:
    """NICE equilibrium quantities at the NICE time slice nearest to time_val"""
    idx = int(np.argmin(np.abs(nice_time - time_val)))
    eq_slice = nice_eq.time_slice[idx]
    p1d = eq_slice.profiles_1d
    rho = np.asarray(p1d.rho_tor_norm)
    q = np.asarray(p1d.q)
    smag = np.asarray(p1d.magnetic_shear)
    if smag.size == 0 or not np.any(smag):
        # NICE leaves magnetic_shear zero: derive it from q, s = (rho / q) dq/drho
        with np.errstate(divide="ignore", invalid="ignore"):
            smag = rho / q * np.gradient(q, rho)
    return {
        "nice_time": float(nice_time[idx]),
        "nice_rho": rho,
        "nice_qx": q,
        "nice_smag": smag,
        "nice_rr": np.asarray(eq_slice.boundary.outline.r),
        "nice_zz": np.asarray(eq_slice.boundary.outline.z),
        "nice_rga": float(eq_slice.boundary.geometric_axis.r),
        "nice_zma": float(eq_slice.global_quantities.magnetic_axis.z),
    }


def load_run(to: DBEntry, nice: DBEntry | None, frame_times) -> list[dict | None]:
    """Per slider time, the run's nearest time slice (None outside the run's time range).

    With ``nice``, each slice also holds the NICE equilibrium nearest in time (nice_* keys).
    """
    nice_eq = nice.get("equilibrium", lazy=True) if nice is not None else None
    nice_time = np.asarray(nice_eq.time) if nice_eq is not None else None
    to_cp: IDSToplevel = to.get("core_profiles", lazy=True)
    to_eq: IDSToplevel = to.get("equilibrium", lazy=True)
    cp_time = np.asarray(to_cp.time)
    loaded = {}  # time index -> slice, so nearby slider times share one load
    slices = []
    for t in frame_times:
        if not cp_time[0] <= t <= cp_time[-1]:
            slices.append(None)
            continue
        idx = int(np.argmin(np.abs(cp_time - t)))
        if idx not in loaded:
            print(f"  loading t[{idx}]={cp_time[idx]:.3f}s")
            loaded[idx] = load_timeslice(idx, to_cp, to_eq)
            if nice_eq is not None:
                loaded[idx].update(load_nice(nice_eq, nice_time, loaded[idx]["time"]))
        slices.append(loaded[idx])
    return slices


def load_timeslice(time_idx: int, to_cp: IDSToplevel, to_eq: IDSToplevel) -> dict:
    """Load and derive everything plotted for one TORAX core_profiles time slice"""
    cp_slice = to_cp.profiles_1d[time_idx]
    elec = cp_slice.electrons
    ion = cp_slice.ion
    assert len(cp_slice.neutral) == 0

    rho = np.asarray(cp_slice.grid.rho_tor_norm)
    zeff = np.asarray(cp_slice.zeff)
    qx = np.asarray(cp_slice.q)
    smag = np.asarray(cp_slice.magnetic_shear)
    Te = np.asarray(elec.temperature) / 1e3  # keV
    Ti0 = np.asarray(ion[0].temperature) / 1e3  # keV
    ne = np.asarray(elec.density) / 1e19  # 1e19 m3

    # TODO: We can also fill this from the gyrokinetics IDS
    # This'd need Torax development
    dTi0 = np.gradient(Ti0)
    dne = np.gradient(ne)
    dTe = np.gradient(Te)

    # Equilibrium is on another timebase: take the first slice at or after this time
    time_val = float(to_cp.time[time_idx])
    eq_time = np.asarray(to_eq.time)
    eq_idx = min(int(eq_time.searchsorted(time_val)), len(eq_time) - 1)
    eq_slice = to_eq.time_slice[eq_idx]
    p1d = eq_slice.profiles_1d

    zma = float(eq_slice.global_quantities.magnetic_axis.z)
    Rmin = float(eq_slice.boundary.minor_radius)
    rga = float(eq_slice.boundary.geometric_axis.r)
    zz = np.asarray(eq_slice.boundary.outline.z)
    rr = np.asarray(eq_slice.boundary.outline.r)

    # Midplane-averaged major radius of flux surface
    # Includes Shafranov shift
    Ro = (max(rr) - min(rr)) / 2
    # Midplane-averaged minor radius of flux surface, normalized by
    # midplane-averaged minor radius of last-closed-flux-surface.
    r_inb = np.asarray(p1d.r_inboard)
    r_outb = np.asarray(p1d.r_outboard)
    xx = (r_outb - r_inb) / (max(rr) - min(rr))
    xx_intp = np.interp(np.linspace(0, 1, len(Te)), xx, xx)
    tau_bounce = calc_tau_bounce(Te, qx, Ro, Rmin, xx_intp)
    nu_e = calc_nu_e(ne, Te, zeff)
    nustar = nu_e * tau_bounce

    return {
        "time_idx": time_idx,
        "time": time_val,
        "rho": rho,
        "Te": Te,
        "Ti0": Ti0,
        "ne": ne,
        "dTe": dTe,
        "dTi0": dTi0,
        "dne": dne,
        "qx": qx,
        "smag": smag,
        "eq_rho": np.asarray(p1d.rho_tor_norm),
        "eq_qx": np.asarray(p1d.q),
        "eq_smag": np.asarray(p1d.magnetic_shear),
        "xx": xx_intp,
        "tite0": Ti0 / Te,
        "logNustar": np.log10(nustar),  # For GK
        "zeff": zeff,
        "rr": rr,
        "zz": zz,
        "rga": rga,
        "zma": zma,
    }


# One entry per profile panel: (axis label, [(data key, x key, legend label), ...]).
# Panels sharing a "ylim group" get the same y-limits, as T_e/T_i and their gradients did.
PANELS = [
    (r"$T_e$ [keV]", [("Te", "rho", None)], "T"),
    (r"$T_{i,0}$ [keV]", [("Ti0", "rho", None)], "T"),
    (r"$n_e$ [$10^{19} m^{-3}$]", [("ne", "rho", None)], None),
    (r"$\partial T_e$ [keV]", [("dTe", "rho", None)], "dT"),
    (r"$\partial T_{i,0}$ [keV]", [("dTi0", "rho", None)], "dT"),
    (r"$\partial n_e$ [$10^{19} m^{-3}$]", [("dne", "rho", None)], None),
    (
        r"$q$ [-]",
        [
            ("qx", "rho", r"$q_{1D,torax}$"),
            ("eq_qx", "eq_rho", r"$q_{eq,torax}$"),
            ("nice_qx", "nice_rho", r"$q_{eq,NICE}$"),
        ],
        None,
    ),
    (
        r"$\hat{s}$ [-]",
        [
            ("smag", "rho", r"$\hat{s}_{1D,torax}$"),
            ("eq_smag", "eq_rho", r"$\hat{s}_{eq,torax}$"),
            ("nice_smag", "nice_rho", r"$\hat{s}_{eq,NICE}$ (from q)"),
        ],
        None,
    ),
    (
        r"$x\equiv\frac{r_{outb} - r_{inb}}{r_{outb,LCFS} - r_{inb,LCFS}}$",
        [("xx", "rho", None)],
        None,
    ),
    (r"$\frac{T_{i,0}}{T_e}$ [-]", [("tite0", "rho", None)], None),
    (r"$\log_{10}(\nu^*$) [-]", [("logNustar", "rho", None)], None),
    (r"$Z_{eff}$ [-]", [("zeff", "rho", None)], None),
]


def data_limits(values, margin=0.05):
    """Padded (min, max) over all finite values in a list of arrays"""
    if len(values) == 0:
        return -1, 1
    flat = np.concatenate([np.ravel(v) for v in values])
    flat = flat[np.isfinite(flat)]
    if flat.size == 0:
        return -1, 1
    lo, hi = flat.min(), flat.max()
    pad = (hi - lo) * margin or abs(hi) * margin or 1
    return lo - pad, hi + pad


class GyrokineticsFigure:
    """The one figure: title, full-width time slider, equilibrium + 4x3 profiles.

    The same figure is shown with ``--interactive`` and saved to PNG/HTML otherwise.
    Moving the slider (by mouse, arrow keys or :meth:`update`) redraws all lines.
    Each run gets its own colour; within a panel, series are told apart by line style.
    Axis limits are fixed over all runs and slices, so moving the slider shows real
    changes rather than rescaled axes.
    """

    SLIDER_SPACE = 0.10  # top strip of the figure reserved for title and slider
    SLIDER_RECT = (0.06, 0.895, 0.86, 0.03)  # full width, between title and plots
    LINESTYLES = ["-", "--", ":", "-."]

    def __init__(self, runs: dict[str, list[dict | None]], frame_times, shot_nr):
        self.runs = runs  # label -> slice per slider time
        self.frame_times = list(frame_times)
        self.shot_nr = shot_nr
        all_slices = [s for slices in runs.values() for s in slices if s is not None]

        def limits(*keys, margin=0.05):
            return data_limits(
                [s[k] for s in all_slices for k in keys if k in s], margin
            )

        has_nice = any("nice_rr" in s for s in all_slices)

        self.fig = plt.figure(figsize=(18, 10), layout="constrained")
        self.fig.get_layout_engine().set(rect=(0, 0, 1, 1 - self.SLIDER_SPACE))
        left, right = self.fig.subfigures(1, 2, width_ratios=[1, 2])
        colors = {label: f"C{i}" for i, label in enumerate(runs)}

        # Equilibrium, per run: TORAX (boundary, magnetic axis, midplane) and
        # NICE (boundary, magnetic axis)
        self.ax_eq = left.subplots()
        self.eq_lines = {
            label: (
                self.ax_eq.plot([], [], color=c)[0],
                self.ax_eq.plot([], [], "o", color=c)[0],
                self.ax_eq.plot([], [], color=c, lw=0.8)[0],
            )
            for label, c in colors.items()
        }
        self.nice_eq_lines = {
            label: (
                self.ax_eq.plot([], [], color=c, ls=":")[0],
                self.ax_eq.plot([], [], "x", color=c)[0],
            )
            for label, c in colors.items()
        }
        self.ax_eq.set_xlim(*limits("rr", "nice_rr"))
        self.ax_eq.set_ylim(*limits("zz", "nice_zz"))
        if has_nice:  # legend for the line styles
            self.ax_eq.legend(
                handles=[
                    Line2D([], [], color="k", marker="o"),
                    Line2D([], [], color="k", ls=":", marker="x"),
                ],
                labels=["TORAX", "NICE"],
                loc="upper right",
            )
        self.ax_eq.set_aspect(1)
        self.ax_eq.set_xlabel("R [m]")
        self.ax_eq.set_ylabel("Z [m]")
        self.ax_eq.set_title("Equilibrium")
        # Run legend; its texts are updated with each run's actual time in _draw
        self.run_legend = left.legend(
            handles=[self.eq_lines[label][0] for label in runs],
            labels=list(runs),
            loc="outside lower center",
        )

        # Profiles
        axes = right.subplots(4, 3).flatten()
        group_keys = {}
        for _, series, group in PANELS:
            if group is not None:
                group_keys.setdefault(group, []).extend(key for key, _, _ in series)

        x_lim = limits("rho", margin=0.02)
        self.profile_lines = []  # (Line2D, run label, data key, x key)
        for ax, (ylabel, series, group) in zip(axes, PANELS):
            for (key, x_key, _), ls in zip(series, self.LINESTYLES):
                for label, c in colors.items():
                    (line,) = ax.plot([], [], color=c, ls=ls)
                    self.profile_lines.append((line, label, key, x_key))
            ax.set_ylabel(ylabel)
            ax.set_xlabel(r"$\rho_{N,tor}$")
            ax.set_xlim(*x_lim)
            keys = group_keys[group] if group is not None else [k for k, _, _ in series]
            ax.set_ylim(*limits(*keys))
            # Legend for the line styles, of the series that have data
            shown = [
                (series_label, ls)
                for (key, _, series_label), ls in zip(series, self.LINESTYLES)
                if any(key in s for s in all_slices)
            ]
            if len(shown) > 1:
                ax.legend(
                    handles=[Line2D([], [], color="k", ls=ls) for _, ls in shown],
                    labels=[series_label for series_label, _ in shown],
                    loc="best",
                )

        self.suptitle = self.fig.suptitle("")

        # Time slider. It steps over slider times (evenly spaced, so the HTML slider
        # can be laid exactly over it) and shows the selected time.
        self.ax_slider = self.fig.add_axes(self.SLIDER_RECT)
        self.slider = Slider(
            self.ax_slider,
            "time [s]",
            0,
            max(len(self.frame_times) - 1, 1),
            valinit=0,
            valstep=1,
        )
        self.slider.on_changed(lambda value: self._draw(int(value)))
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)
        self._draw(0)

    def update(self, frame: int):
        """Move the slider to ``frame`` (which redraws); returns the changed artists"""
        self.slider.set_val(frame)
        return self.fig.get_children()

    def _draw(self, frame: int):
        frame = min(frame, len(self.frame_times) - 1)
        t = self.frame_times[frame]
        for (label, slices), text in zip(self.runs.items(), self.run_legend.get_texts()):
            s = slices[frame]
            boundary, axis, midplane = self.eq_lines[label]
            nice_boundary, nice_axis = self.nice_eq_lines[label]
            if s is not None and "nice_rr" in s:
                nice_boundary.set_data(s["nice_rr"], s["nice_zz"])
                nice_axis.set_data([s["nice_rga"]], [s["nice_zma"]])
            else:
                nice_boundary.set_data([], [])
                nice_axis.set_data([], [])
            if s is None:  # slider time outside this run
                for line in (boundary, axis, midplane):
                    line.set_data([], [])
                text.set_text(f"{label} (no data at this time)")
                continue
            boundary.set_data(s["rr"], s["zz"])
            axis.set_data([s["rga"]], [s["zma"]])
            midplane.set_data((min(s["rr"]), max(s["rr"])), (s["zma"], s["zma"]))
            text.set_text(f"{label} (t[{s['time_idx']}]={s['time']:.3f}s)")
        for line, label, key, x_key in self.profile_lines:
            s = self.runs[label][frame]
            if s is None or key not in s:  # outside this run, or no NICE data
                line.set_data([], [])
            else:
                line.set_data(s[x_key], s[key])
        t0, t1 = self.frame_times[0], self.frame_times[-1]
        self.suptitle.set_text(
            f"{self.shot_nr} gyrokinetic profiles\nt={t:.3f}s, t=[{t0:.1f}, {t1:.1f}]"
        )
        self.slider.valtext.set_text(f"{t:.3f}")
        self.fig.canvas.draw_idle()

    def _on_key(self, event):
        """Left/right arrow keys step one slider time"""
        frame = int(self.slider.val)
        if event.key == "right":
            self.update(min(frame + 1, len(self.frame_times) - 1))
        elif event.key == "left":
            self.update(max(frame - 1, 0))


def write_outputs(gk: GyrokineticsFigure, args):
    """Save the figure: a PNG per time slice, plus an HTML page to scroll through them"""
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for frame, t in enumerate(gk.frame_times):
        gk.update(frame)
        path = output_dir / f"gyrokinetics_{args.shot_nr}_t={t:.3f}.png"
        print(f"Writing {path}")
        gk.fig.savefig(path)

    matplotlib.rcParams["animation.embed_limit"] = 500  # MB
    anim = FuncAnimation(gk.fig, gk.update, frames=len(gk.frame_times), blit=False)
    path = output_dir / f"gyrokinetics_{args.shot_nr}.html"
    print(f"Writing {path} ({len(gk.frame_times)} times)")
    html = anim.to_jshtml(fps=5, default_mode="once")

    # The frames already show the figure's own slider. Lay matplotlib's HTML range input
    # invisibly over it, so dragging the slider in the image scrolls through time.
    # Both map slice numbers linearly onto the same rectangle.
    x0, y0, w, h = GyrokineticsFigure.SLIDER_RECT
    style = f"""<style>
.animation {{ display: block; width: 100%; }}
.gk-figure {{ position: relative; }}
.gk-figure img {{ display: block; width: 100%; height: auto; }}
.gk-figure input[type=range].anim-slider {{
  position: absolute; margin: 0; opacity: 0; cursor: pointer;
  left: {x0 * 100}%; top: {(1 - y0 - h) * 100}%; width: {w * 100}%; height: {h * 100}%;
}}
</style>"""
    script = """<script>
document.querySelectorAll(".animation").forEach(function (anim) {
  var img = anim.querySelector("img");
  var wrap = document.createElement("div");
  wrap.className = "gk-figure";
  img.parentNode.insertBefore(wrap, img);
  wrap.appendChild(img);
  wrap.appendChild(anim.querySelector("input.anim-slider"));
});
</script>"""
    # style must come after html: matplotlib's own <style> would otherwise override it
    path.write_text(
        f"<!doctype html><title>Gyrokinetics {args.shot_nr}</title>{html}{style}{script}"
    )


def main():
    """Plot gyrokinetically relevant TORAX output for PDS, scrollable in time"""
    args = handle_args()
    if not args.interactive:
        matplotlib.use("Agg")

    # The other sources are accepted for interface compatibility with the other
    # postprocessing scripts, but not (yet) plotted.
    for name in ("dina_uri", "metis_uri"):
        if getattr(args, name) is not None:
            print(f"Note: --{name} given but not plotted yet")

    labels = args.labels or short_labels([run_label(uri) for uri in args.torax_uri])
    if len(set(labels)) != len(labels):
        raise SystemExit(f"plot_gyrokinetics.py: run labels must be unique, got {labels}")

    with ExitStack() as stack:
        dbs = {
            label: stack.enter_context(DBEntry(f"imas:hdf5?path={uri}", "r"))
            for label, uri in zip(labels, args.torax_uri)
        }
        nice_dbs = {
            label: stack.enter_context(DBEntry(f"imas:hdf5?path={uri}", "r"))
            for label, uri in zip(labels, args.nice_uri or [])
            if uri.lower() != "none"
        }
        # Slider times: every run's first, middle and last time slice, plus
        # --max_slices evenly spaced times over the combined time range of all runs
        required = []
        for to in dbs.values():
            t = np.asarray(to.get("core_profiles", lazy=True).time)
            required += [t[0], t[len(t) // 2], t[-1]]
        evenly = np.linspace(min(required), max(required), args.max_slices)
        # Skip evenly spaced times that (nearly) coincide with a required slice
        close = 0.01 * (max(required) - min(required))
        evenly = [t for t in evenly if np.min(np.abs(np.asarray(required) - t)) > close]
        frame_times = merge_times(np.concatenate([required, evenly]))

        runs = {}
        for label, to in dbs.items():
            nice = nice_dbs.get(label)
            print(f"Loading run {label} (TORAX{' + NICE' if nice else ''})")
            runs[label] = load_run(to, nice, frame_times)

    gk = GyrokineticsFigure(runs, frame_times, args.shot_nr)
    if args.interactive:
        plt.show()
    else:
        write_outputs(gk, args)
    plt.close(gk.fig)


if __name__ == "__main__":
    main()
