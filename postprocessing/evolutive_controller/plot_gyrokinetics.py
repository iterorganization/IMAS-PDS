"""Plot gyrokinetically relevant TORAX profiles, scrollable in time.

Each ``--run_path`` is a run directory. Its TORAX output is read from ``out_torax`` and,
if present, its NICE output from ``out_nice`` (see ``--torax_subdir``/``--nice_subdir``).
Several run paths can be given to overlay runs, one colour per run. Where a run has NICE
output, its equilibrium (boundary, axis, q and magnetic shear) is overlaid in
the same colour, dotted.

Writes to ``--output_dir`` (see time_slider.py):

* ``gyrokinetics_<shot>.html``: the figure at every slider time; drag the time slider in
  the figure or use the play controls below it. Open it in a browser.
* ``gyrokinetics_<shot>_t=<time>.png``: the figure at each slider time.

With ``--interactive`` the same figure is shown in a matplotlib window instead.
"""

import argparse
import os
from contextlib import ExitStack
from pathlib import Path
from typing import NamedTuple

import numpy as np
from imas import DBEntry
from imas.ids_toplevel import IDSToplevel
from matplotlib.lines import Line2D
from time_slider import (
    SliderFigure,
    add_slider_args,
    apply_slider_args,
    data_limits,
    nearest_index,
    per_frame,
    show_or_save,
    slider_times,
)

# ----------------------------------------------------------------------------------------
# Collisionality, as in QuaLiKiz
# ----------------------------------------------------------------------------------------

qe = 1.602176565e-19  # electron charge [C]
me = 9.10938291e-31  # electron mass [kg]
mp = 1.672621777e-27  # proton mass [kg]


def calc_c1(zeff, ne, q, Ro, Rmin, x):
    r"""Calculate part of the normalized collision frequency :math:`\nu^*`

    Args:
        zeff: Effective ion charge [-]
        ne: Electron density [1e19 m^-3]
        q: Safety factor [-]
        Ro: Midplane-averaged major radius of the flux surface [m]
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
        Ro: Midplane-averaged major radius of the flux surface [m]
        Rmin: Midplane-averaged minor radius of last-closed-flux-surface [m]
        x: Normalized radius [m]
    """
    # From QLK source:
    # Nustar(:) = Nue(:)*qx(:)*Ro(:)/epsilon(:)**1.5/(SQRT(Tex(:)*1.d3*qe/me))
    epsilon = Rmin * x / Ro
    return q * Ro / (epsilon**1.5 * np.sqrt(Te * 1e3 * qe / me))


# ----------------------------------------------------------------------------------------
# Arguments
# ----------------------------------------------------------------------------------------


def handle_args():
    parser = argparse.ArgumentParser(
        description="Plot gyrokinetically relevant profiles with a time slider"
    )
    parser.add_argument("--shot_nr", type=str, help="Shot number")
    parser.add_argument(
        "--run_path",
        type=str,
        nargs="+",
        action="extend",
        help=(
            "Run directory/directories (default: $RUN_DIR); give several to overlay runs. "
            "TORAX and NICE output are read from --torax_subdir and --nice_subdir in each"
        ),
    )
    parser.add_argument(
        "--torax_subdir",
        type=str,
        default="out_torax",
        help="Subdirectory of each run with the TORAX output (default: out_torax)",
    )
    parser.add_argument(
        "--nice_subdir",
        type=str,
        default="out_nice",
        help="Subdirectory of each run with the NICE output, if any (default: out_nice)",
    )
    parser.add_argument(
        "--labels",
        type=str,
        nargs="+",
        help="Legend label per --run_path (default: the run directory names)",
    )
    add_slider_args(parser)
    args = parser.parse_args()
    apply_slider_args(parser, args)

    if not args.run_path:
        if not os.environ.get("RUN_DIR"):
            parser.error("--run_path (or $RUN_DIR) is required")
        args.run_path = [os.environ["RUN_DIR"]]
    for run in args.run_path:
        if not (Path(run) / args.torax_subdir).is_dir():
            parser.error(f"no {args.torax_subdir} in run directory {run}")
    if args.labels is None:
        args.labels = short_labels([Path(run).resolve().name for run in args.run_path])
    if len(args.labels) != len(args.run_path):
        parser.error("give one --labels entry per --run_path")
    if len(set(args.labels)) != len(args.labels):
        parser.error(f"run labels must be unique, got {args.labels}")
    return args


def short_labels(labels: list[str]) -> list[str]:
    """Drop the "_"-separated prefix all labels share (e.g. workflow_shot_), if any"""
    if len(labels) < 2:
        return labels
    parts = [label.split("_") for label in labels]
    n = 0
    while all(len(p) > n + 1 and p[n] == parts[0][n] for p in parts):
        n += 1
    return ["_".join(p[n:]) for p in parts]


# ----------------------------------------------------------------------------------------
# Loading
#
# Everything plotted for one time slice of one run is a "slice" dict with keys
#   time_idx, time                 the TORAX core_profiles time slice
#   rho, Te, Ti0, ne, dTe, dTi0, dne, qx, smag, xx, tite0, logNustar, zeff
#                                  TORAX core_profiles (and derived) profiles vs rho
#   eq_rho, eq_qx, eq_smag         TORAX equilibrium profiles
#   rr, zz                         TORAX plasma boundary
#   rga, zma                       TORAX axis marker: geometric axis R, magnetic axis Z
#   nice_*                         the same NICE equilibrium quantities, if the run has NICE
# ----------------------------------------------------------------------------------------


def load_torax_slice(time_idx: int, to_cp: IDSToplevel, to_eq: IDSToplevel) -> dict:
    """TORAX quantities at core_profiles time slice ``time_idx``"""
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

    # QuaLiKiz geometry, per flux surface. r_inboard/r_outboard are major radii, on the
    # equilibrium grid, so interpolated onto core_profiles' rho.
    eq_rho = np.asarray(p1d.rho_tor_norm)
    r_inb = np.asarray(p1d.r_inboard)
    r_outb = np.asarray(p1d.r_outboard)
    # Midplane-averaged major radius of the flux surface (includes the Shafranov shift)
    Ro = np.interp(rho, eq_rho, (r_outb + r_inb) / 2)
    # Midplane-averaged minor radius of flux surface, normalized by
    # midplane-averaged minor radius of last-closed-flux-surface
    xx = (r_outb - r_inb) / (max(rr) - min(rr))
    xx_intp = np.interp(rho, eq_rho, xx)
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


def load_nice_slice(nice_eq: IDSToplevel, nice_time, time_val: float) -> dict:
    """NICE equilibrium quantities (nice_* keys) at the NICE slice nearest to time_val"""
    idx = nearest_index(nice_time, time_val)
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
        "nice_rho": rho,
        "nice_qx": q,
        "nice_smag": smag,
        "nice_rr": np.asarray(eq_slice.boundary.outline.r),
        "nice_zz": np.asarray(eq_slice.boundary.outline.z),
        "nice_rga": float(eq_slice.boundary.geometric_axis.r),
        "nice_zma": float(eq_slice.global_quantities.magnetic_axis.z),
    }


def load_run(torax: DBEntry, nice: DBEntry | None, frame_times) -> list[dict | None]:
    """A run's slice per slider time: its nearest time slice, None outside its range"""
    to_cp: IDSToplevel = torax.get("core_profiles", lazy=True)
    to_eq: IDSToplevel = torax.get("equilibrium", lazy=True)
    nice_eq = nice.get("equilibrium", lazy=True) if nice is not None else None
    nice_time = np.asarray(nice_eq.time) if nice_eq is not None else None
    cp_time = np.asarray(to_cp.time)

    def load(idx):
        print(f"  loading t[{idx}]={cp_time[idx]:.3f}s")
        s = load_torax_slice(idx, to_cp, to_eq)
        if nice_eq is not None:
            s |= load_nice_slice(nice_eq, nice_time, s["time"])
        return s

    return per_frame(frame_times, cp_time, load)


# ----------------------------------------------------------------------------------------
# Figure
# ----------------------------------------------------------------------------------------


class Series(NamedTuple):
    """One line in a profile panel: slice keys of its y and x values"""

    key: str
    x_key: str = "rho"
    label: str | None = None  # for the line-style legend of panels with several series


class Panel(NamedTuple):
    """One profile panel. Panels with the same ylim_group share their y-limits."""

    ylabel: str
    series: list[Series]
    ylim_group: str | None = None


PANELS = [
    Panel(r"$T_e$ [keV]", [Series("Te")], ylim_group="T"),
    Panel(r"$T_{i,0}$ [keV]", [Series("Ti0")], ylim_group="T"),
    Panel(r"$n_e$ [$10^{19} m^{-3}$]", [Series("ne")]),
    Panel(r"$\partial T_e$ [keV]", [Series("dTe")], ylim_group="dT"),
    Panel(r"$\partial T_{i,0}$ [keV]", [Series("dTi0")], ylim_group="dT"),
    Panel(r"$\partial n_e$ [$10^{19} m^{-3}$]", [Series("dne")]),
    Panel(
        r"$q$ [-]",
        [
            Series("qx", label=r"$q_{1D,torax}$"),
            Series("eq_qx", "eq_rho", r"$q_{eq,torax}$"),
            Series("nice_qx", "nice_rho", r"$q_{eq,NICE}$"),
        ],
    ),
    Panel(
        r"$\hat{s}$ [-]",
        [
            Series("smag", label=r"$\hat{s}_{1D,torax}$"),
            Series("eq_smag", "eq_rho", r"$\hat{s}_{eq,torax}$"),
            Series("nice_smag", "nice_rho", r"$\hat{s}_{eq,NICE}$ (from q)"),
        ],
    ),
    Panel(
        r"$x\equiv\frac{r_{outb} - r_{inb}}{r_{outb,LCFS} - r_{inb,LCFS}}$",
        [Series("xx")],
    ),
    Panel(r"$\frac{T_{i,0}}{T_e}$ [-]", [Series("tite0")]),
    Panel(r"$\log_{10}(\nu^*$) [-]", [Series("logNustar")]),
    Panel(r"$Z_{eff}$ [-]", [Series("zeff")]),
]
LINESTYLES = ["-", "--", ":", "-."]  # per series within a panel


def check_panel_keys(slices):
    """Fail early on a PANELS key that no slice has (a typo would draw an empty panel)

    NICE keys are only in the slices of runs with NICE output, so they are exempt.
    """
    keys = set().union(*slices) if slices else set()
    for panel in PANELS:
        for series in panel.series:
            for key in (series.key, series.x_key):
                if not key.startswith("nice_") and key not in keys:
                    raise KeyError(f"PANELS uses {key!r}, which no slice has")


def clear(*lines):
    for line in lines:
        line.set_data([], [])


class GyrokineticsFigure(SliderFigure):
    """Equilibrium (left) and 4x3 gyrokinetic profile panels (right).

    Each run gets its own colour; within a panel, series are told apart by line style.
    Axis limits are fixed over all runs and slices, so moving the slider shows real
    changes rather than rescaled axes.
    """

    def __init__(self, runs: dict[str, list[dict | None]], frame_times, shot_nr):
        super().__init__(frame_times)
        self.runs = runs  # run label -> slice per slider time
        self.shot_nr = shot_nr
        self.colors = {label: f"C{i}" for i, label in enumerate(runs)}
        self.all_slices = [
            s for slices in runs.values() for s in slices if s is not None
        ]
        check_panel_keys(self.all_slices)

        left, right = self.fig.subfigures(1, 2, width_ratios=[1, 2])
        self._setup_equilibrium(left)
        self._setup_profiles(right)
        self.update(0)

    def limits(self, *keys, margin=0.05):
        """Axis limits over the given slice keys of all runs and slices"""
        values = [s[k] for s in self.all_slices for k in keys if k in s]
        return data_limits(values, margin)

    def has_data(self, key) -> bool:
        return any(key in s for s in self.all_slices)

    def _setup_equilibrium(self, subfig):
        ax = subfig.subplots()
        # Per run: TORAX (boundary, axis marker, midplane) and NICE (boundary, axis)
        self.torax_eq_lines = {
            label: (
                ax.plot([], [], color=c)[0],
                ax.plot([], [], "o", color=c)[0],
                ax.plot([], [], color=c, lw=0.8)[0],
            )
            for label, c in self.colors.items()
        }
        self.nice_eq_lines = {
            label: (
                ax.plot([], [], color=c, ls=":")[0],
                ax.plot([], [], "x", color=c)[0],
            )
            for label, c in self.colors.items()
        }
        ax.set_xlim(*self.limits("rr", "nice_rr"))
        ax.set_ylim(*self.limits("zz", "nice_zz"))
        if self.has_data("nice_rr"):  # legend for the line styles
            ax.legend(
                handles=[
                    Line2D([], [], color="k", marker="o"),
                    Line2D([], [], color="k", ls=":", marker="x"),
                ],
                labels=["TORAX", "NICE"],
                loc="upper right",
            )
        ax.set_aspect(1)
        ax.set_xlabel("R [m]")
        ax.set_ylabel("Z [m]")
        ax.set_title("Equilibrium")
        # Run legend, below the whole figure: the left subfigure is too narrow for the
        # long run labels. Its texts get each run's actual time in _draw_equilibrium.
        self.run_legend = self.fig.legend(
            handles=[lines[0] for lines in self.torax_eq_lines.values()],
            labels=list(self.runs),
            loc="outside lower center",
        )

    def _setup_profiles(self, subfig):
        group_keys = {}
        for panel in PANELS:
            if panel.ylim_group is not None:
                group_keys.setdefault(panel.ylim_group, []).extend(
                    s.key for s in panel.series
                )

        x_lim = self.limits("rho", margin=0.02)
        self.profile_lines = []  # (Line2D, run label, Series)
        for ax, panel in zip(subfig.subplots(4, 3).flatten(), PANELS, strict=True):
            for series, ls in zip(panel.series, LINESTYLES, strict=False):
                for label, c in self.colors.items():
                    (line,) = ax.plot([], [], color=c, ls=ls)
                    self.profile_lines.append((line, label, series))
            ax.set_ylabel(panel.ylabel)
            ax.set_xlabel(r"$\rho_{N,tor}$")
            ax.set_xlim(*x_lim)
            if panel.ylim_group is not None:
                ax.set_ylim(*self.limits(*group_keys[panel.ylim_group]))
            else:
                ax.set_ylim(*self.limits(*(s.key for s in panel.series)))
            # Legend for the line styles, of the series that have data
            shown = [
                (series.label, ls)
                for series, ls in zip(panel.series, LINESTYLES, strict=False)
                if self.has_data(series.key)
            ]
            if len(shown) > 1:
                ax.legend(
                    handles=[Line2D([], [], color="k", ls=ls) for _, ls in shown],
                    labels=[label for label, _ in shown],
                    loc="best",
                )

    def title(self, frame: int) -> str:
        t0, t1 = self.frame_times[0], self.frame_times[-1]
        return (
            f"{self.shot_nr} gyrokinetic profiles\n"
            f"t={self.frame_times[frame]:.3f}s, t=[{t0:.1f}, {t1:.1f}]"
        )

    def draw(self, frame: int):
        self._draw_equilibrium(frame)
        self._draw_profiles(frame)

    def _draw_equilibrium(self, frame: int):
        legend_texts = self.run_legend.get_texts()
        for (label, slices), text in zip(self.runs.items(), legend_texts, strict=True):
            s = slices[frame]
            boundary, axis, midplane = self.torax_eq_lines[label]
            nice_boundary, nice_axis = self.nice_eq_lines[label]
            if s is None:  # slider time outside this run
                clear(boundary, axis, midplane, nice_boundary, nice_axis)
                text.set_text(f"{label} (no data at this time)")
                continue

            boundary.set_data(s["rr"], s["zz"])
            axis.set_data([s["rga"]], [s["zma"]])
            midplane.set_data((min(s["rr"]), max(s["rr"])), (s["zma"], s["zma"]))
            text.set_text(f"{label} (t[{s['time_idx']}]={s['time']:.3f}s)")
            if "nice_rr" in s:
                nice_boundary.set_data(s["nice_rr"], s["nice_zz"])
                nice_axis.set_data([s["nice_rga"]], [s["nice_zma"]])
            else:
                clear(nice_boundary, nice_axis)

    def _draw_profiles(self, frame: int):
        for line, label, series in self.profile_lines:
            s = self.runs[label][frame]
            if s is None or series.key not in s:  # outside this run, or no NICE data
                clear(line)
            else:
                line.set_data(s[series.x_key], s[series.key])


# ----------------------------------------------------------------------------------------


def main():
    """Plot gyrokinetically relevant TORAX (and NICE) output for PDS, scrollable in time"""
    args = handle_args()
    run_paths = dict(zip(args.labels, map(Path, args.run_path), strict=True))

    with ExitStack() as stack:

        def open_db(path: Path) -> DBEntry:
            return stack.enter_context(DBEntry(f"imas:hdf5?path={path}", "r"))

        torax_dbs = {
            label: open_db(run / args.torax_subdir) for label, run in run_paths.items()
        }
        nice_dbs = {  # NICE output is optional per run
            label: open_db(run / args.nice_subdir)
            for label, run in run_paths.items()
            if (run / args.nice_subdir).is_dir()
        }

        frame_times = slider_times(
            [db.get("core_profiles", lazy=True).time for db in torax_dbs.values()],
            args.max_slices,
        )
        runs = {}
        for label, torax in torax_dbs.items():
            nice = nice_dbs.get(label)
            print(f"Loading run {label} (TORAX{' + NICE' if nice else ''})")
            runs[label] = load_run(torax, nice, frame_times)

    figure = GyrokineticsFigure(runs, frame_times, args.shot_nr)
    show_or_save(
        [(figure, f"gyrokinetics_{args.shot_nr}", f"Gyrokinetics {args.shot_nr}")], args
    )


if __name__ == "__main__":
    main()
