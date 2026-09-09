"""
Validate evolutive_controller output: reference vs NICE for R, Z, Ip, PF coil current.
"""

import argparse
import logging

import matplotlib.pyplot as plt
import numpy as np
from imas import DBEntry
from imas.ids_defs import CLOSEST_INTERP

logger = logging.getLogger(__name__)

PLOT_KWARGS = {"marker": "."}
GET_KWARGS = {"interpolation_method": CLOSEST_INTERP, "lazy": True}


def handle_args():
    parser = argparse.ArgumentParser(
        description="Compare evolutive_controller's NICE output against its reference"
    )
    parser.add_argument("--shot_nr", type=str, help="Shot number")
    parser.add_argument(
        "--dina_uri",
        type=str,
        help="URI to load raw DINA scenario data from (reference Ip and PF coil current)",
    )
    parser.add_argument(
        "--reconstruction_uri",
        type=str,
        help=(
            "URI to load the NICE-reconstructed equilibrium the workflow's `source` actor "
            "reads (reference R, Z -- waveform_editor never overlays geometric_axis, so "
            "this is the actual reference the controller solves against)"
        ),
    )
    parser.add_argument(
        "--nice_uri",
        type=str,
        help="URI to load evolutive_controller's NICE output from",
    )
    parser.add_argument(
        "--output_dir", type=str, help="path to directory in which to put plots"
    )
    args = parser.parse_args()
    return args


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


def main():
    """Plot evolutive_controller reference-vs-NICE validation figures"""
    args = handle_args()
    dbs = {
        "dina": DBEntry(f"imas:hdf5?path={args.dina_uri}", "r"),
        "reconstruction": DBEntry(f"imas:hdf5?path={args.reconstruction_uri}", "r"),
        "nice": DBEntry(f"imas:hdf5?path={args.nice_uri}", "r"),
    }

    rz_ip_plot(args, dbs)
    kcurr_plot(args, dbs)

    for db in dbs.values():
        db.close()


def rz_ip_plot(args, dbs):
    """Plot R, Z (plasma boundary geometric axis) and Ip: reference vs NICE output.

    R/Z reference comes from the reconstructed equilibrium fed into `source` (waveform_editor
    only overlays boundary/outline and global_quantities/ip from DINA, never geometric_axis --
    see workflows/evolutive_controller/waveforms.yaml), Ip reference from raw DINA.
    """
    figure_path = f"{args.output_dir}/pds_rz_ip_{args.shot_nr}.png"

    recon_eq = dbs["reconstruction"].get("equilibrium")
    dina_eq = dbs["dina"].get("equilibrium")
    nice_eq = dbs["nice"].get("equilibrium")

    recon_t = np.asarray(recon_eq.time)
    recon_r = np.asarray([ts.boundary.geometric_axis.r for ts in recon_eq.time_slice])
    recon_z = np.asarray([ts.boundary.geometric_axis.z for ts in recon_eq.time_slice])

    dina_t = np.asarray(dina_eq.time)
    dina_ip = np.asarray([ts.global_quantities.ip for ts in dina_eq.time_slice])

    nice_mask = nice_output_flags(dbs["nice"]) != -1
    nice_t = np.asarray(nice_eq.time)[nice_mask]
    nice_r = np.asarray([ts.boundary.geometric_axis.r for ts in nice_eq.time_slice])[
        nice_mask
    ]
    nice_z = np.asarray([ts.boundary.geometric_axis.z for ts in nice_eq.time_slice])[
        nice_mask
    ]
    nice_ip = np.asarray([ts.global_quantities.ip for ts in nice_eq.time_slice])[
        nice_mask
    ]

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
    fig.savefig(figure_path)


def kcurr_plot(args, dbs):
    """Plot PF coil current (Kcurr, the KCURR_PFPO1 controller's tracked quantity):
    the raw-DINA target vs NICE's actual per-coil current, one panel per coil."""
    coil_figure_path = f"{args.output_dir}/pds_kcurr_{args.shot_nr}.png"
    coil_dict = {}
    pfas = {
        "reference": dbs["dina"].get("pf_active"),
        "nice": dbs["nice"].get("pf_active"),
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
            time, current = interp_to_range(t_min, t_max, time, current)
            axes[coil_dict[coil_name]].plot(time, current, label=key, **PLOT_KWARGS)
            axes[coil_dict[coil_name]].legend()
    for ax in axes[len(pfa.coil) :]:
        fig.delaxes(ax)

    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(coil_figure_path)


if __name__ == "__main__":
    main()
