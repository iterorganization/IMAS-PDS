"""
Validate evolutive_controller output: reference vs NICE for R, Z, Ip, PF coil current,
plus NICE (q, pressure) and TORAX (Te, ne, q) profiles, each on its own psi grid.

The profile figures have a time slider (see time_slider.py): saved as a PNG per slider
time plus a scrollable HTML page, or shown in a window with ``--interactive`` (together
with the R/Z/Ip and coil current figures).
"""

import argparse
import logging
import os
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from imas import DBEntry
from imas.ids_defs import CLOSEST_INTERP
from time_slider import (
    SliderFigure,
    add_slider_args,
    check_slider_args,
    data_limits,
    nearest_index,
    show_or_save,
    slider_times,
)

logger = logging.getLogger(__name__)

PLOT_KWARGS = {"marker": "."}
GET_KWARGS = {"interpolation_method": CLOSEST_INTERP, "lazy": True}


def handle_args():
    parser = argparse.ArgumentParser(
        description="Compare evolutive_controller's NICE output against its reference"
    )
    parser.add_argument("--shot_nr", type=str, help="Shot number")
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
        help=(
            "Path to load the NICE-reconstructed equilibrium the workflow's `source` actor "
            "reads (reference R, Z -- waveform_editor never overlays geometric_axis, so "
            "this is the actual reference the controller solves against)"
        ),
    )
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
        help="Subdirectory of the run with the TORAX core_profiles output (default: out_torax)",
    )
    parser.add_argument(
        "--max_points",
        type=int,
        default=500,
        help="Maximum number of time slices per series in the time-trace plots",
    )
    add_slider_args(parser)
    args = parser.parse_args()
    check_slider_args(parser, args)
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


def case_dir(run_path):
    """Case directory of a run: cases/<case> for a run cases/runs/[<case>/]<case>_<date>_<time>.

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
    if (t_a.max() - t_a.min()) <= (t_b.max() - t_b.min()):
        t_min, t_max = t_a.min(), t_a.max()
    else:
        t_min, t_max = t_b.min(), t_b.max()
    return (
        interp_to_range(t_min, t_max, t_a, *values_a),
        interp_to_range(t_min, t_max, t_b, *values_b),
    )


def nice_output_flags(db):
    """Per-slice NICE solver status: -1 means NICE failed to converge that slice."""
    equilibrium = db.get("equilibrium", lazy=True)
    flags = equilibrium.code.output_flag
    if not flags:
        return np.zeros(len(equilibrium.time))
    return np.asarray(flags)


def subsample(n, max_points):
    """At most max_points evenly spaced indices into a series of length n"""
    return np.unique(np.linspace(0, n - 1, min(n, max_points)).astype(int))


def eq_traces(eq, idx, *getters):
    """Time and one array per getter at the given time_slice indices of a lazy IDS"""
    time = np.asarray(eq.time)[idx]
    slices = [eq.time_slice[int(i)] for i in idx]
    return (time, *(np.asarray([float(g(ts)) for ts in slices]) for g in getters))


def main():
    """Plot evolutive_controller reference-vs-NICE validation figures"""
    args = handle_args()
    dbs = {
        key: DBEntry(f"imas:hdf5?path={path}", "r")
        for key, path in {
            "dina": args.dina_path,
            "reconstruction": args.reconstruction_path,
            "nice": os.path.join(args.run_path, args.nice_subdir),
            "torax": os.path.join(args.run_path, args.torax_subdir),
        }.items()
        if path is not None
    }

    rz_ip_plot(args, dbs)
    kcurr_plot(args, dbs)
    slider_figures = [nice_profiles_plot(args, dbs), torax_profiles_plot(args, dbs)]

    for db in dbs.values():
        db.close()

    show_or_save(slider_figures, args)


def save_static(fig, path, args):
    """Save a figure without time slider, unless it is shown with --interactive"""
    if not args.interactive:
        print(f"Writing {path}")
        fig.savefig(path)
        plt.close(fig)


def rz_ip_plot(args, dbs):
    """Plot R, Z (plasma boundary geometric axis) and Ip: reference vs NICE output.

    R/Z reference comes from the reconstructed equilibrium fed into `source` (waveform_editor
    only overlays boundary/outline and global_quantities/ip from DINA, never geometric_axis --
    see workflows/evolutive_controller/waveforms.yaml), Ip reference from raw DINA.
    """
    figure_path = f"{args.output_dir}/pds_rz_ip_{args.shot_nr}.png"

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

    valid = np.flatnonzero(nice_output_flags(dbs["nice"]) != -1)
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
    save_static(fig, figure_path, args)


def kcurr_plot(args, dbs):
    """Plot PF coil current (Kcurr, the KCURR_PFPO1 controller's tracked quantity):
    the raw-DINA target vs NICE's actual per-coil current, one panel per coil."""
    coil_figure_path = f"{args.output_dir}/pds_kcurr_{args.shot_nr}.png"
    coil_dict = {}
    pfas = {
        "reference": dbs["dina"].get("pf_active", lazy=True),
        "nice": dbs["nice"].get("pf_active", lazy=True),
    }
    nice_mask = nice_output_flags(dbs["nice"]) != -1
    ref_time = np.asarray(pfas["reference"].time)
    nice_time = np.asarray(pfas["nice"].time)[nice_mask]
    if ref_time.max() - ref_time.min() <= nice_time.max() - nice_time.min():
        t_min, t_max = ref_time.min(), ref_time.max()
    else:
        t_min, t_max = nice_time.min(), nice_time.max()

    nrows, ncols = (7, 2)
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(15, 22))
    fig.suptitle(f"{args.shot_nr}: reference vs NICE PF coil current", fontsize=16)
    axes = axes.flatten()

    for key, pfa in pfas.items():
        mask = nice_mask if key == "nice" else None
        full_time = np.asarray(pfa.time)
        for coil in pfa.coil:
            coil_name = str(coil.name)
            if coil_name not in coil_dict:
                next_slot = max(coil_dict.values(), default=-1) + 1
                if next_slot >= len(axes):
                    logger.warning(
                        "pf_active coil name %r (%s) has no free plot slot "
                        "(reference/nice disagree on coil naming for this "
                        "scenario) -- skipping its plot.",
                        coil_name,
                        key,
                    )
                    continue
                coil_dict[coil_name] = next_slot
                axes[coil_dict[coil_name]].set_title(coil_name)
                axes[coil_dict[coil_name]].set_ylabel("current")
                axes[coil_dict[coil_name]].set_xlabel("time")
            time, current = full_time, np.asarray(coil.current.data)
            if mask is not None and len(mask) == len(time):
                time, current = time[mask], current[mask]
            idx = subsample(len(time), args.max_points)
            time, current = interp_to_range(t_min, t_max, time[idx], current[idx])
            axes[coil_dict[coil_name]].plot(time, current, label=key, **PLOT_KWARGS)
            axes[coil_dict[coil_name]].legend()
    for ax in axes[len(pfa.coil) :]:
        fig.delaxes(ax)

    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    save_static(fig, coil_figure_path, args)


def normalise_psi(psi):
    return np.abs(psi - psi[0]) / np.abs(psi[-1] - psi[0])


class ProfilesPsiFigure(SliderFigure):
    """One panel per label, showing that profile vs psi_norm at the slider time.

    ``profiles`` holds, per slider time, (actual time, psi_norm, [values per label]) or
    None when the code has no valid profile there. Axis limits are fixed over all times.
    """

    def __init__(self, frame_times, profiles, title, labels):
        super().__init__(frame_times, figsize=(6 * len(labels), 6))
        self.profiles = profiles
        self.title_text = title
        valid = [p for p in profiles if p is not None]
        axes = self.fig.subplots(1, len(labels))
        self.lines = []
        for i, (ax, label) in enumerate(zip(axes, labels, strict=True)):
            ax.set_title(label)
            ax.set_ylabel(label)
            ax.set_xlabel("psi_norm")
            ax.set_xlim(*data_limits([psi for _, psi, _ in valid], margin=0.02))
            ax.set_ylim(*data_limits([values[i] for _, _, values in valid]))
            self.lines.append(ax.plot([], [], color="C0")[0])
        self.update(0)

    def title(self, frame: int) -> str:
        p = self.profiles[frame]
        when = "no valid profile at this time" if p is None else f"t={p[0]:.3f}s"
        return f"{self.title_text}\n{when}"

    def draw(self, frame: int):
        p = self.profiles[frame]
        for i, line in enumerate(self.lines):
            if p is None:
                line.set_data([], [])
            else:
                line.set_data(p[1], p[2][i])


def slider_profiles(times, max_slices, get_profiles, name):
    """Slider times over a code's timebase, and its profiles at the nearest time slice.

    get_profiles(t) returns (psi, [values per label]) or None. Returns the slider times
    and, per slider time, (actual time, psi_norm, values) or None.
    """
    frame_times = slider_times([times], max_slices)
    loaded = {}
    profiles = []
    for t in frame_times:
        t_slice = float(times[nearest_index(times, t)])
        if t_slice not in loaded:
            result = get_profiles(t_slice)
            if result is None:
                logger.warning("%s: empty profiles at t=%.4f, skipping.", name, t_slice)
                loaded[t_slice] = None
            else:
                psi, values = result
                loaded[t_slice] = (t_slice, normalise_psi(psi), values)
        profiles.append(loaded[t_slice])
    return frame_times, profiles


def nice_profiles_plot(args, dbs):
    """NICE equilibrium q and pressure on NICE's own psi grid, at NICE's valid slices
    (slider figure)."""
    nice_t = np.asarray(dbs["nice"].get("equilibrium", lazy=True).time)
    nice_t = nice_t[nice_output_flags(dbs["nice"]) != -1]

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
        return psi, [q, pressure / 1e3]

    title = f"{args.shot_nr}: NICE profiles vs psi_norm"
    frame_times, profiles = slider_profiles(nice_t, args.max_slices, get_profiles, title)
    figure = ProfilesPsiFigure(frame_times, profiles, title, ["q", "pressure [kPa]"])
    return figure, f"pds_nice_profiles_psi_{args.shot_nr}", title


def torax_profiles_plot(args, dbs):
    """TORAX core_profiles Te, ne and q on TORAX's own psi grid (slider figure)."""
    torax_t = np.asarray(dbs["torax"].get("core_profiles", lazy=True).time)

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
        return psi, values

    title = f"{args.shot_nr}: TORAX profiles vs psi_norm"
    frame_times, profiles = slider_profiles(torax_t, args.max_slices, get_profiles, title)
    figure = ProfilesPsiFigure(frame_times, profiles, title, ["Te [keV]", "ne [m^-3]", "q"])
    return figure, f"pds_torax_profiles_psi_{args.shot_nr}", title


if __name__ == "__main__":
    main()
