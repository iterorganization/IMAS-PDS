"""Plot gyrokinetically relevant TORAX profiles, scrollable in time.

By default this writes, to ``--output_dir``:

* ``gyrokinetics_<shot>.html``: the figure for all plotted time slices; drag its time
  slider or use the play controls below it. Works headless (e.g. from
  ``postprocess.sh`` under sbatch); open it in a browser.
* ``gyrokinetics_<shot>_idx=<i>.png``: the figure at each plotted time slice.

With ``--interactive`` the same figure is shown in a matplotlib window instead.
"""

import argparse
from pathlib import Path

import matplotlib

import matplotlib.pyplot as plt
import numpy as np
from imas import DBEntry
from imas.ids_toplevel import IDSToplevel
from matplotlib.animation import FuncAnimation
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
        "--nice_uri", type=str, help="URI to load NICE output data from"
    )
    parser.add_argument(
        "--metis_uri", type=str, help="URI to load METIS output data from"
    )
    parser.add_argument(
        "--torax_uri", type=str, help="URI to load TORAX output data from"
    )
    parser.add_argument(
        "--output_dir", type=str, help="path to directory in which to put plots"
    )
    parser.add_argument("--t_list", type=int, nargs="+", help="List of times to plot")
    parser.add_argument(
        "--max_slices",
        type=int,
        default=3,
        help="Maximum number of (evenly spaced) time slices on the slider",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Open a matplotlib window with a time slider instead of writing files",
    )
    args = parser.parse_args()
    if not args.interactive and args.output_dir is None:
        parser.error("--output_dir is required unless --interactive is given")
    return args


def subsample(n, max_points):
    """At most max_points evenly spaced indices into a series of length n"""
    return np.unique(np.linspace(0, n - 1, min(n, max_points)).astype(int))


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
        [("qx", "rho", r"$q_{1D,torax}$"), ("eq_qx", "eq_rho", r"$q_{eq,torax}$")],
        None,
    ),
    (
        r"$\hat{s}$ [-]",
        [
            ("smag", "rho", r"$\hat{s}_{1D,torax}$"),
            ("eq_smag", "eq_rho", r"$\hat{s}_{eq,torax}$"),
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
    Axis limits are fixed over all slices, so moving the slider shows real changes
    rather than rescaled axes.
    """

    SLIDER_SPACE = 0.10  # top strip of the figure reserved for title and slider
    SLIDER_RECT = (0.06, 0.895, 0.86, 0.03)  # full width, between title and plots

    def __init__(self, slices: list[dict], shot_nr, t_range):
        self.slices = slices
        self.shot_nr = shot_nr
        self.t_range = t_range

        self.fig = plt.figure(figsize=(18, 10), layout="constrained")
        self.fig.get_layout_engine().set(rect=(0, 0, 1, 1 - self.SLIDER_SPACE))
        left, right = self.fig.subfigures(1, 2, width_ratios=[1, 2])

        # Equilibrium boundary
        self.ax_eq = left.subplots()
        (self.li_boundary,) = self.ax_eq.plot([], [])
        (self.li_axis,) = self.ax_eq.plot([], [], "o")
        (self.li_midplane,) = self.ax_eq.plot([], [])
        self.ax_eq.set_xlim(*data_limits([s["rr"] for s in slices]))
        self.ax_eq.set_ylim(*data_limits([s["zz"] for s in slices]))
        self.ax_eq.set_aspect(1)
        self.ax_eq.set_xlabel("R [m]")
        self.ax_eq.set_ylabel("Z [m]")
        self.ax_eq.set_title("Equilibrium")

        # Profiles
        axes = right.subplots(4, 3).flatten()
        group_limits = {}
        for _, series, group in PANELS:
            if group is not None:
                values = [s[key] for s in slices for key, _, _ in series]
                group_limits.setdefault(group, []).extend(values)
        group_limits = {g: data_limits(v) for g, v in group_limits.items()}

        x_lim = data_limits([s["rho"] for s in slices], margin=0.02)
        self.profile_lines = []  # (Line2D, data key, x key)
        for ax, (ylabel, series, group) in zip(axes, PANELS):
            for key, x_key, label in series:
                (line,) = ax.plot([], [], label=label)
                self.profile_lines.append((line, key, x_key))
            ax.set_ylabel(ylabel)
            ax.set_xlabel(r"$\rho_{N,tor}$")
            ax.set_xlim(*x_lim)
            if group is not None:
                ax.set_ylim(*group_limits[group])
            else:
                ax.set_ylim(*data_limits([s[key] for s in slices for key, _, _ in series]))
            if any(label for _, _, label in series):
                ax.legend(loc="best")

        self.suptitle = self.fig.suptitle("")

        # Time slider. It steps over slice numbers (evenly spaced, so the HTML slider
        # can be laid exactly over it) and shows the time of the selected slice.
        self.ax_slider = self.fig.add_axes(self.SLIDER_RECT)
        self.slider = Slider(
            self.ax_slider,
            "time [s]",
            0,
            max(len(slices) - 1, 1),
            valinit=0,
            valstep=1,
        )
        self.slider.on_changed(lambda value: self._draw(int(value)))
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)
        self._draw(0)

    def title(self, frame: int) -> str:
        s = self.slices[frame]
        t0, t1 = self.t_range
        return (
            f"{self.shot_nr} gyrokinetic profiles\n"
            f"t[{s['time_idx']}]={s['time']:.3f}s, t=[{t0:.1f}, {t1:.1f}]"
        )

    def update(self, frame: int):
        """Move the slider to ``frame`` (which redraws); returns the changed artists"""
        self.slider.set_val(frame)
        return self.fig.get_children()

    def _draw(self, frame: int):
        frame = min(frame, len(self.slices) - 1)
        s = self.slices[frame]
        self.li_boundary.set_data(s["rr"], s["zz"])
        self.li_axis.set_data([s["rga"]], [s["zma"]])
        self.li_midplane.set_data((min(s["rr"]), max(s["rr"])), (s["zma"], s["zma"]))
        for line, key, x_key in self.profile_lines:
            line.set_data(s[x_key], s[key])
        self.suptitle.set_text(self.title(frame))
        self.slider.valtext.set_text(f"{s['time']:.3f}")
        self.fig.canvas.draw_idle()

    def _on_key(self, event):
        """Left/right arrow keys step one slice"""
        frame = int(self.slider.val)
        if event.key == "right":
            self.update(min(frame + 1, len(self.slices) - 1))
        elif event.key == "left":
            self.update(max(frame - 1, 0))


def write_outputs(gk: GyrokineticsFigure, args):
    """Save the figure: a PNG per time slice, plus an HTML page to scroll through them"""
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for frame, s in enumerate(gk.slices):
        gk.update(frame)
        path = output_dir / f"gyrokinetics_{args.shot_nr}_idx={s['time_idx']}.png"
        print(f"Writing {path}")
        gk.fig.savefig(path)

    matplotlib.rcParams["animation.embed_limit"] = 500  # MB
    anim = FuncAnimation(gk.fig, gk.update, frames=len(gk.slices), blit=False)
    path = output_dir / f"gyrokinetics_{args.shot_nr}.html"
    print(f"Writing {path} ({len(gk.slices)} time slices)")
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

    if args.torax_uri is None:
        raise SystemExit("plot_gyrokinetics.py: --torax_uri is required")
    # The other sources are accepted for interface compatibility with the other
    # postprocessing scripts, but not (yet) plotted.
    for name in ("dina_uri", "nice_uri", "metis_uri"):
        if getattr(args, name) is not None:
            print(f"Note: --{name} given but not plotted yet")

    with DBEntry(f"imas:hdf5?path={args.torax_uri}", "r") as to:
        print("Getting TORAX core_profiles and equilibrium...")
        to_cp: IDSToplevel = to.get("core_profiles", lazy=True)
        to_eq: IDSToplevel = to.get("equilibrium", lazy=True)
        cp_time = np.asarray(to_cp.time)
        t_range = (float(cp_time[0]), float(cp_time[-1]))

        idxs = subsample(len(cp_time), args.max_slices)
        slices = []
        for n, time_idx in enumerate(idxs):
            print(f"Loading time slice {n + 1}/{len(idxs)} (t[{time_idx}])")
            slices.append(load_timeslice(int(time_idx), to_cp, to_eq))

    gk = GyrokineticsFigure(slices, args.shot_nr, t_range)
    if args.interactive:
        plt.show()
    else:
        write_outputs(gk, args)
    plt.close(gk.fig)


if __name__ == "__main__":
    main()
