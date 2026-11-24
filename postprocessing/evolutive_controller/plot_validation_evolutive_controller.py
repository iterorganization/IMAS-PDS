"""Validate evolutive_controller output against its reference.

Figures, written to ``--output_dir``:

* ``pds_rz_ip_<shot>.png``: R, Z (boundary geometric axis) and Ip, reference vs NICE.
* ``pds_kcurr_<shot>.png``: PF coil currents, DINA target vs NICE, one panel per coil.
* ``pds_nice_profiles_psi_<shot>``: NICE q and pressure vs psi_norm, and
* ``pds_torax_profiles_psi_<shot>``: TORAX Te, ne and q vs psi_norm, each on its own psi
  grid. These two have a time slider (see time_slider.py): a PNG per slider time plus a
  scrollable HTML page.

With ``--interactive`` all four are shown in matplotlib windows instead.

NICE output and TORAX output are read from ``--run_path`` (``out_nice``, ``out_torax``),
the DINA reference from the run's case (``cases/<case>/preprocess/in``).
"""

import argparse
import logging
import os
import re
from contextlib import ExitStack
from pathlib import Path
from typing import NamedTuple

import matplotlib.pyplot as plt
import numpy as np
from imas import DBEntry
from imas.ids_defs import CLOSEST_INTERP
from time_slider import (
    SliderFigure,
    add_slider_args,
    apply_slider_args,
    data_limits,
    per_frame,
    show_or_save,
    slider_times,
)

logger = logging.getLogger(__name__)

PLOT_KWARGS = {"marker": "."}
GET_KWARGS = {"interpolation_method": CLOSEST_INTERP, "lazy": True}

# ----------------------------------------------------------------------------------------
# Arguments
# ----------------------------------------------------------------------------------------


def handle_args():
    parser = argparse.ArgumentParser(
        description="Compare evolutive_controller's NICE output against its reference"
    )
    parser.add_argument("--shot_nr", type=str, help="Shot number")
    parser.add_argument(
        "--run_path",
        type=str,
        default=os.environ.get("RUN_DIR"),
        help=(
            "Run directory (default: $RUN_DIR); evolutive_controller's NICE and TORAX "
            "output are read from its --nice_subdir and --torax_subdir"
        ),
    )
    parser.add_argument(
        "--nice_subdir",
        type=str,
        default="out_nice",
        help="Subdirectory of the run with the NICE output (default: out_nice)",
    )
    parser.add_argument(
        "--torax_subdir",
        type=str,
        default="out_torax",
        help="Subdirectory of the run with the TORAX core_profiles output "
        "(default: out_torax)",
    )
    parser.add_argument(
        "--dina_path",
        type=str,
        help=(
            "Path to load raw DINA scenario data from (reference Ip and PF coil current). "
            "Default: cases/<case>/preprocess/in of the case --run_path belongs to"
        ),
    )
    parser.add_argument(
        "--reconstruction_path",
        type=str,
        required=True,
        help=(
            "Path to load the NICE-reconstructed equilibrium the workflow's `source` actor "
            "reads (reference R, Z -- waveform_editor never overlays geometric_axis, so "
            "this is the actual reference the controller solves against)"
        ),
    )
    parser.add_argument(
        "--max_points",
        type=int,
        default=500,
        help="Maximum number of time slices per series in the time-trace plots",
    )
    add_slider_args(parser)
    args = parser.parse_args()
    apply_slider_args(parser, args)

    if args.run_path is None:
        parser.error("--run_path (or $RUN_DIR) is required")
    if args.dina_path is None:
        case = case_dir(args.run_path)
        if case is None:
            parser.error(
                f"cannot find the case of run {args.run_path} (not under cases/runs/ and "
                "$PDS_REPO not set); give --dina_path"
            )
        args.dina_path = str(case / "preprocess" / "in")
    return args


def case_dir(run_path) -> Path | None:
    """Case directory of a run: cases/<case> for cases/runs/[<case>/]<case>_<date>_<time>.

    The cases directory is found from the run's location, else $PDS_REPO/cases.
    """
    run = Path(run_path).resolve()
    case = re.sub(r"_\d{8}_\d{6}$", "", run.name)
    for parent in run.parents:
        if parent.name == "runs" and parent.parent.name == "cases":
            return parent.parent / case
    if os.environ.get("PDS_REPO"):
        return Path(os.environ["PDS_REPO"]) / "cases" / case
    return None


# ----------------------------------------------------------------------------------------
# Time traces
# ----------------------------------------------------------------------------------------


def nice_valid(db: DBEntry):
    """Per NICE equilibrium slice, whether NICE converged (output_flag is not -1)"""
    equilibrium = db.get("equilibrium", lazy=True)
    flags = equilibrium.code.output_flag
    if len(flags) == 0:  # not filled: treat every slice as converged
        return np.ones(len(equilibrium.time), dtype=bool)
    return np.asarray(flags) != -1


def subsample(n, max_points):
    """At most max_points evenly spaced indices into a series of length n"""
    return np.unique(np.linspace(0, n - 1, min(n, max_points)).astype(int))


def eq_traces(eq, idx, *getters):
    """Time and one array per getter at the given time_slice indices of a lazy IDS"""
    time = np.asarray(eq.time)[idx]
    slices = [eq.time_slice[int(i)] for i in idx]
    return (time, *(np.asarray([float(g(ts)) for ts in slices]) for g in getters))


def shorter_range(t_a, t_b):
    """(min, max) of whichever of two time series spans less time"""
    if (t_a.max() - t_a.min()) <= (t_b.max() - t_b.min()):
        return t_a.min(), t_a.max()
    return t_b.min(), t_b.max()


def interp_to_range(t_min, t_max, t, *values):
    """Restrict a time series to [t_min, t_max], interpolating value(s) exactly at the
    boundaries so a coarsely-sampled series draws a line spanning the same x-range as the
    series it's compared against, instead of overshooting to its own native samples
    outside that range."""
    inside = (t > t_min) & (t < t_max)
    t_new = np.concatenate(([t_min], t[inside], [t_max]))
    values_new = tuple(
        np.concatenate(([np.interp(t_min, t, v)], v[inside], [np.interp(t_max, t, v)]))
        for v in values
    )
    return (t_new, *values_new)


def align_ranges(t_a, values_a, t_b, values_b):
    """Restrict both series to whichever of the two spans less time, interpolating the
    other series exactly at that shorter span's boundaries so both lines drawn cover the
    same x-range."""
    t_min, t_max = shorter_range(t_a, t_b)
    return (
        interp_to_range(t_min, t_max, t_a, *values_a),
        interp_to_range(t_min, t_max, t_b, *values_b),
    )


def save_static(fig, path, args):
    """Save a figure without time slider, unless it is shown with --interactive"""
    if not args.interactive:
        print(f"Writing {path}")
        fig.savefig(path)
        plt.close(fig)


def rz_ip_plot(args, dbs, nice_ok):
    """Plot R, Z (plasma boundary geometric axis) and Ip: reference vs NICE output.

    R/Z reference comes from the reconstructed equilibrium fed into `source` (waveform_editor
    only overlays boundary/outline and global_quantities/ip from DINA, never geometric_axis --
    see workflows/evolutive_controller/waveforms.yaml), Ip reference from raw DINA.
    """
    recon_eq = dbs["reconstruction"].get("equilibrium", lazy=True)
    dina_eq = dbs["dina"].get("equilibrium", lazy=True)
    nice_eq = dbs["nice"].get("equilibrium", lazy=True)

    def r(ts):
        return ts.boundary.geometric_axis.r

    def z(ts):
        return ts.boundary.geometric_axis.z

    def ip(ts):
        return ts.global_quantities.ip

    recon_idx = subsample(len(recon_eq.time), args.max_points)
    recon_t, recon_r, recon_z = eq_traces(recon_eq, recon_idx, r, z)

    dina_idx = subsample(len(dina_eq.time), args.max_points)
    dina_t, dina_ip = eq_traces(dina_eq, dina_idx, ip)

    valid = np.flatnonzero(nice_ok)
    nice_idx = valid[subsample(len(valid), args.max_points)]
    nice_t, nice_r, nice_z, nice_ip = eq_traces(nice_eq, nice_idx, r, z, ip)

    (recon_t, recon_r, recon_z), (nice_rz_t, nice_r, nice_z) = align_ranges(
        recon_t, (recon_r, recon_z), nice_t, (nice_r, nice_z)
    )
    (dina_t, dina_ip), (nice_ip_t, nice_ip) = align_ranges(
        dina_t, (dina_ip,), nice_t, (nice_ip,)
    )

    fig, axes = plt.subplots(nrows=1, ncols=3, figsize=(18, 5))
    fig.suptitle(f"{args.shot_nr}: reference vs NICE output", fontsize=16)

    panels = [
        (axes[0], "R [m]", recon_t, recon_r, nice_rz_t, nice_r),
        (axes[1], "Z [m]", recon_t, recon_z, nice_rz_t, nice_z),
        (axes[2], "Ip [A]", dina_t, dina_ip, nice_ip_t, nice_ip),
    ]
    for ax, label, ref_t, ref_v, out_t, out_v in panels:
        ax.set_title(label)
        ax.set_ylabel(label)
        ax.set_xlabel("time")
        ax.plot(ref_t, ref_v, label="reference", **PLOT_KWARGS)
        ax.plot(out_t, out_v, label="nice", **PLOT_KWARGS)
        ax.legend()

    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    save_static(fig, f"{args.output_dir}/pds_rz_ip_{args.shot_nr}.png", args)


def kcurr_plot(args, dbs, nice_ok):
    """Plot PF coil current (Kcurr, the KCURR_PFPO1 controller's tracked quantity):
    the raw-DINA target vs NICE's actual per-coil current, one panel per coil."""
    # legend label -> (pf_active, mask of slices to plot, or None for all). NICE's
    # convergence mask is per equilibrium slice; NICE writes pf_active on the same times.
    sources = {
        "reference": (dbs["dina"].get("pf_active", lazy=True), None),
        "nice": (dbs["nice"].get("pf_active", lazy=True), nice_ok),
    }
    t_min, t_max = shorter_range(
        np.asarray(sources["reference"][0].time),
        np.asarray(sources["nice"][0].time)[nice_ok],
    )

    fig, axes = plt.subplots(nrows=7, ncols=2, figsize=(15, 22))
    fig.suptitle(f"{args.shot_nr}: reference vs NICE PF coil current", fontsize=16)
    axes = axes.flatten()

    coil_axes = {}  # coil name -> its panel, in order of first appearance
    for key, (pfa, mask) in sources.items():
        full_time = np.asarray(pfa.time)
        for coil in pfa.coil:
            coil_name = str(coil.name)
            if coil_name not in coil_axes:
                if len(coil_axes) >= len(axes):
                    logger.warning(
                        "pf_active coil name %r (%s) has no free plot slot "
                        "(reference/nice disagree on coil naming for this "
                        "scenario) -- skipping its plot.",
                        coil_name,
                        key,
                    )
                    continue
                ax = coil_axes[coil_name] = axes[len(coil_axes)]
                ax.set_title(coil_name)
                ax.set_ylabel("current")
                ax.set_xlabel("time")
            time, current = full_time, np.asarray(coil.current.data)
            if mask is not None:
                time, current = time[mask], current[mask]
            idx = subsample(len(time), args.max_points)
            time, current = interp_to_range(t_min, t_max, time[idx], current[idx])
            coil_axes[coil_name].plot(time, current, label=key, **PLOT_KWARGS)
    for ax in coil_axes.values():
        ax.legend()
    for ax in axes[len(coil_axes) :]:
        fig.delaxes(ax)

    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    save_static(fig, f"{args.output_dir}/pds_kcurr_{args.shot_nr}.png", args)


# ----------------------------------------------------------------------------------------
# Profiles vs psi_norm, with time slider
# ----------------------------------------------------------------------------------------


class Profile(NamedTuple):
    """A code's profiles at one time slice"""

    time: float
    psi_norm: np.ndarray
    values: dict[str, np.ndarray]  # panel label -> profile


def normalise_psi(psi):
    return np.abs(psi - psi[0]) / np.abs(psi[-1] - psi[0])


def load_profiles(times, max_slices, get_profiles, name):
    """Slider times over a code's timebase, and its Profile at the nearest time slice
    (None where get_profiles finds no valid profile).

    get_profiles(t) returns (psi, {panel label: profile}) or None.
    """

    def load(i):
        t = float(times[i])
        result = get_profiles(t)
        if result is None:
            logger.warning("%s: empty profiles at t=%.4f, skipping.", name, t)
            return None
        psi, values = result
        return Profile(t, normalise_psi(psi), values)

    frame_times = slider_times([times], max_slices)
    return frame_times, per_frame(frame_times, times, load)


class ProfilesPsiFigure(SliderFigure):
    """One panel per label, showing that profile vs psi_norm at the slider time.

    Axis limits are fixed over all times.
    """

    def __init__(self, frame_times, profiles: list[Profile | None], title, labels):
        super().__init__(frame_times, figsize=(6 * len(labels), 6))
        self.profiles = profiles
        self.title_text = title
        valid = [p for p in profiles if p is not None]
        self.lines = {}  # panel label -> line
        for ax, label in zip(self.fig.subplots(1, len(labels)), labels, strict=True):
            ax.set_title(label)
            ax.set_ylabel(label)
            ax.set_xlabel("psi_norm")
            ax.set_xlim(*data_limits([p.psi_norm for p in valid], margin=0.02))
            ax.set_ylim(*data_limits([p.values[label] for p in valid]))
            self.lines[label] = ax.plot([], [], color="C0")[0]
        self.update(0)

    def title(self, frame: int) -> str:
        p = self.profiles[frame]
        when = "no valid profile at this time" if p is None else f"t={p.time:.3f}s"
        return f"{self.title_text}\n{when}"

    def draw(self, frame: int):
        p = self.profiles[frame]
        for label, line in self.lines.items():
            if p is None:
                line.set_data([], [])
            else:
                line.set_data(p.psi_norm, p.values[label])


def nice_profiles_plot(args, dbs, nice_ok):
    """NICE equilibrium q and pressure on NICE's own psi grid, at NICE's valid slices"""
    nice_t = np.asarray(dbs["nice"].get("equilibrium", lazy=True).time)[nice_ok]
    labels = ["q", "pressure [kPa]"]

    def get_profiles(t):
        p1 = (
            dbs["nice"]
            .get_slice("equilibrium", time_requested=t, **GET_KWARGS)
            .time_slice[0]
            .profiles_1d
        )
        psi, q, pressure = (np.asarray(v) for v in (p1.psi, p1.q, p1.pressure))
        if len(psi) < 2 or not len(psi) == len(q) == len(pressure):
            return None
        return psi, dict(zip(labels, [q, pressure / 1e3], strict=True))

    title = f"{args.shot_nr}: NICE profiles vs psi_norm"
    frame_times, profiles = load_profiles(nice_t, args.max_slices, get_profiles, title)
    figure = ProfilesPsiFigure(frame_times, profiles, title, labels)
    return figure, f"pds_nice_profiles_psi_{args.shot_nr}", title


def torax_profiles_plot(args, dbs):
    """TORAX core_profiles Te, ne and q on TORAX's own psi grid"""
    torax_t = np.asarray(dbs["torax"].get("core_profiles", lazy=True).time)
    labels = ["Te [keV]", "ne [m^-3]", "q"]

    def get_profiles(t):
        p1 = (
            dbs["torax"]
            .get_slice("core_profiles", time_requested=t, **GET_KWARGS)
            .profiles_1d[0]
        )
        values = [
            np.asarray(p1.electrons.temperature) / 1e3,
            np.asarray(p1.electrons.density),
            np.asarray(p1.q),
        ]
        psi = np.asarray(p1.grid.psi)
        if len(psi) < 2 or any(len(v) != len(psi) for v in values):
            return None
        return psi, dict(zip(labels, values, strict=True))

    title = f"{args.shot_nr}: TORAX profiles vs psi_norm"
    frame_times, profiles = load_profiles(torax_t, args.max_slices, get_profiles, title)
    figure = ProfilesPsiFigure(frame_times, profiles, title, labels)
    return figure, f"pds_torax_profiles_psi_{args.shot_nr}", title


# ----------------------------------------------------------------------------------------


def main():
    """Plot evolutive_controller reference-vs-NICE validation figures"""
    args = handle_args()
    paths = {
        "dina": args.dina_path,
        "reconstruction": args.reconstruction_path,
        "nice": Path(args.run_path) / args.nice_subdir,
        "torax": Path(args.run_path) / args.torax_subdir,
    }
    with ExitStack() as stack:
        dbs = {
            key: stack.enter_context(DBEntry(f"imas:hdf5?path={path}", "r"))
            for key, path in paths.items()
        }
        nice_ok = nice_valid(dbs["nice"])
        rz_ip_plot(args, dbs, nice_ok)
        kcurr_plot(args, dbs, nice_ok)
        slider_figures = [
            nice_profiles_plot(args, dbs, nice_ok),
            torax_profiles_plot(args, dbs),
        ]

    show_or_save(slider_figures, args)


if __name__ == "__main__":
    main()
