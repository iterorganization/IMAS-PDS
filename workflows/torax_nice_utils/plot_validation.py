"""
Validate output of simulations in FBE + Transport coupling
"""

import argparse
import os

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from imas import DBEntry, IDSFactory
from imas.ids_defs import CLOSEST_INTERP

PLOT_KWARGS = {"marker": "."}
GET_KWARGS = {"interpolation_method": CLOSEST_INTERP, "lazy": True}


def handle_args():
    parser = argparse.ArgumentParser(
        description="Get preprocessed input data for NICE from DINA"
    )
    parser.add_argument("--shot_nr", type=str, help="Shot number")
    parser.add_argument(
        "--dina_uri", type=str, help="URI to load DINA output data from"
    )
    parser.add_argument(
        "--nice_uri", type=str, help="URI to load NICE output data from"
    )
    parser.add_argument(
        "--torax_uri", type=str, help="URI to load TORAX output data from"
    )
    parser.add_argument(
        "--output_dir", type=str, help="path to directory in which to put plots"
    )
    parser.add_argument("--t_list", type=int, nargs="+", help="List of times to plot")
    args = parser.parse_args()
    return args


def nested_getattr(obj, name_list):
    """Get attribute of object by going down list of strings"""
    if len(name_list) == 0:
        return obj
    else:
        new_obj = getattr(obj, name_list[0])
        return nested_getattr(new_obj, name_list[1:])


# Fields recomputed from each code's own profiles instead of read from
# global_quantities: DINA's stored beta_pol is ~19% above and beta_tor ~5% below what
# the IMAS DD formulas give on its own stored pressure/Ip/B0 (different internal
# conventions), while NICE fills them exactly per the DD definitions — so the stored
# values of the two codes are not comparable. Recomputing both sides makes the panels
# apples-to-apples.
RECOMPUTED_0D = {"beta_pol", "beta_tor"}
_trapz = getattr(np, "trapezoid", None) or np.trapz


def recomputed_beta(eq, which):
    """beta_pol / beta_tor per the IMAS DD definitions from a single-slice
    equilibrium IDS; falls back to the stored value if profiles are absent."""
    ts = eq.time_slice[0]
    p = np.asarray(ts.profiles_1d.pressure)
    volume = np.asarray(ts.profiles_1d.volume)
    if len(p) == 0 or len(volume) != len(p):
        return nested_getattr(ts, ("global_quantities", which)).value
    mu0 = 4e-7 * np.pi
    p_dV = _trapz(p, volume)
    if which == "beta_pol":
        # beta_pol = 4 * int(p dV) / (mu0 * Ip^2 * R0)
        ip = float(ts.global_quantities.ip)
        r0 = float(eq.vacuum_toroidal_field.r0)
        return 4 * p_dV / (mu0 * ip**2 * r0)
    # beta_tor = <p>_V / (B0^2 / 2 mu0)
    b0 = float(np.asarray(eq.vacuum_toroidal_field.b0)[0])
    return (p_dV / volume[-1]) / (b0**2 / (2 * mu0))


def nice_output_flags(db):
    """Per-slice NICE solver status for a whole-trace equilibrium IDS: -1 means NICE failed
    to converge that slice (profiles_1d/global_quantities left as IMAS empty-value sentinels,
    e.g. 9e40), 0 means success. Indices line up 1:1 with the slice ordering used everywhere
    else in this workflow (the same `times` list the outer loop split/assembled from), so
    callers can index this array directly instead of matching by time value."""
    equilibrium = db.get("equilibrium", lazy=True)
    flags = equilibrium.code.output_flag
    if not flags:
        return np.zeros(len(equilibrium.time))
    return np.asarray(flags)


def main():
    """Plot simulation output data for PDS nice_torax coupling"""
    args = handle_args()
    dbs = {
        key: DBEntry(f"imas:hdf5?path={path}", "r")
        for key, path in {
            "dina": args.dina_uri,
            "nice": args.nice_uri,
            "torax": args.torax_uri,
        }.items()
    }

    pf_active_plots_dina_nice(args, dbs)
    equilibrium_plots_dina_nice(args, dbs)
    equilibrium_plots_nice_torax(args, dbs)
    core_profiles_plots_dina_torax(args, dbs)
    shape_comparison_plot(args, dbs)

    for db in dbs.values():
        db.close()


def pf_active_plots_dina_nice(args, dbs):
    """Plot pf_active IDS output data for dina-nice"""
    active_keys = ["dina", "nice"]
    # init data
    coil_figure_path = f"{args.output_dir}/pds_coils_{args.shot_nr}.png"
    coil_dict = {}
    pfas = {
        key: db.get("pf_active") for key, db in dbs.items() if key in active_keys
    }

    # init figure
    nrows, ncols = (7, 2)
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(15, 22))
    fig.suptitle(f"{args.shot_nr}: {'-'.join(active_keys).upper()}", fontsize=16)
    axes = axes.flatten()

    # pf_active carries no output_flag of its own; it shares the equilibrium's slice
    # ordering (both assembled from the same per-slice NICE calls in nice_lb.py), so a
    # failed equilibrium slice's coil currents are unreliable at the same index too.
    valid = {
        key: nice_output_flags(dbs[key]) != -1 for key in active_keys if key in dbs
    }

    # plot data
    for key, pfa in pfas.items():
        mask = valid.get(key)
        full_time = np.asarray(pfa.time)
        for coil in pfa.coil:
            coil_name = str(coil.name)
            if coil_name not in coil_dict:
                coil_dict[coil_name] = max(coil_dict.values(), default=-1) + 1
                axes[coil_dict[coil_name]].set_title(coil_name)
                axes[coil_dict[coil_name]].set_ylabel("current")
                axes[coil_dict[coil_name]].set_xlabel("time")
            time, current = full_time, np.asarray(coil.current.data)
            if mask is not None and len(mask) == len(time):
                time, current = time[mask], current[mask]
            axes[coil_dict[coil_name]].plot(
                time, current, label=key, **PLOT_KWARGS
            )
            axes[coil_dict[coil_name]].legend()
    for ax in axes[len(pfa.coil) :]:
        fig.delaxes(ax)

    # save figure
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(coil_figure_path)


def equilibrium_plots_dina_nice(args, dbs):
    """Plot equilibrium IDS output data for dina-nice"""
    equilibrium_0d_figure_path = (
        f"{args.output_dir}/pds_equilibrium_0D_{args.shot_nr}.png"
    )
    equilibrium_fields_0d = [
        ("global_quantities", "ip"),
        ("global_quantities", "magnetic_axis", "b_field_phi"),
        ("global_quantities", "magnetic_axis", "r"),
        ("global_quantities", "magnetic_axis", "z"),
        ("global_quantities", "beta_pol"),
        ("global_quantities", "beta_tor"),
        ("global_quantities", "li_3"),
        ("boundary", "elongation"),
    ]
    equilibrium_fields_1d = [
        ("profiles_1d", "pressure"),
        ("profiles_1d", "f"),
    ]
    equilibrium_plot_func(
        args,
        {key: val for (key, val) in dbs.items() if key in ["dina", "nice"]},
        equilibrium_fields_0d,
        equilibrium_fields_1d,
        equilibrium_0d_figure_path,
    )


def equilibrium_plots_nice_torax(args, dbs):
    """Plot equilibrium IDS output data for nice-torax"""
    equilibrium_1d_figure_path = (
        f"{args.output_dir}/pds_equilibrium_1D_{args.shot_nr}.png"
    )
    equilibrium_fields_0d = []
    equilibrium_fields_1d = [
        ("profiles_1d", "pressure"),
        ("profiles_1d", "dpressure_dpsi"),
        ("profiles_1d", "f"),
        ("profiles_1d", "f_df_dpsi"),
        ("profiles_1d", "psi"),
        ("profiles_1d", "q"),
        ("profiles_1d", "j_phi"),
        ("profiles_1d", "gm2"),
        ("profiles_1d", "volume"),
        ("profiles_1d", "elongation"),
        # Te/Ti are core_profiles quantities (equilibrium/profiles_1d has no
        # t_i_average or electrons node) -- see core_profiles_plots_dina_torax.
    ]
    equilibrium_plot_func(
        args,
        {key: val for (key, val) in dbs.items() if key in ["nice", "torax"]},
        equilibrium_fields_0d,
        equilibrium_fields_1d,
        equilibrium_1d_figure_path,
    )


def core_profiles_plots_dina_torax(args, dbs):
    """Plot Te/Ti from core_profiles: DINA input vs the final TORAX-evolved output.

    The evolved core_profiles only reach sink_torax since the loop grew a
    core_profiles_out_f lane (same change as this plot); for older data dirs the
    torax entry has no core_profiles, and the panels fall back to DINA-only.
    """
    figure_path = f"{args.output_dir}/pds_core_profiles_{args.shot_nr}.png"
    cps = {}
    for key in ["dina", "torax"]:
        try:
            cps[key] = dbs[key].get("core_profiles", lazy=True)
        except Exception:
            continue

    fields = [("electrons", "temperature"), ("t_i_average",)]
    labels = ["t_e", "t_i"]
    fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(15, 10))
    fig.suptitle(
        f"{args.shot_nr}: {'-'.join(cps).upper()} core_profiles", fontsize=16
    )
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    # profiles at t_list: first db as line, second as scatter (same convention
    # as the equilibrium 1D panels)
    for col, (field, label) in enumerate(zip(fields, labels)):
        ax = axes[0][col]
        ax.set_title(label)
        ax.set_ylabel(label)
        ax.set_xlabel("rho_tor_norm")
        for i_t, t in enumerate(args.t_list):
            for num, key in enumerate(cps):
                cp = dbs[key].get_slice(
                    "core_profiles", time_requested=t, **GET_KWARGS
                )
                p1 = cp.profiles_1d[0]
                rho = np.asarray(p1.grid.rho_tor_norm)
                val = np.asarray(nested_getattr(p1, field).value)
                if len(val) == 0 or len(rho) != len(val):
                    continue
                if num == 0:
                    ax.plot(rho, val, label=f"t={t}", color=colors[i_t])
                else:
                    ax.scatter(rho, val, color=colors[i_t], marker=".")
        handles, _ = ax.get_legend_handles_labels()
        keys = list(cps)
        if len(keys) > 1:
            handles += [
                Line2D([0], [0], color="k", label=f"{keys[0]} (line)"),
                Line2D([0], [0], color="k", marker=".", linestyle="None", label=f"{keys[1]} (scatter)"),
            ]
        ax.legend(handles=handles)

    # central values over time
    for col, (field, label) in enumerate(zip(fields, labels)):
        ax = axes[1][col]
        ax.set_title(f"central {label}")
        ax.set_ylabel(label)
        ax.set_xlabel("time")
        for key, cp_full in cps.items():
            times, vals = [], []
            for t in np.asarray(cp_full.time):
                p1 = dbs[key].get_slice(
                    "core_profiles", time_requested=t, **GET_KWARGS
                ).profiles_1d[0]
                val = np.asarray(nested_getattr(p1, field).value)
                if len(val) == 0:
                    continue
                times.append(t)
                vals.append(val[0])
            ax.plot(times, vals, label=key, **PLOT_KWARGS)
        ax.legend()

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(figure_path)


def equilibrium_plot_func(args, dbs, fields_0d, fields_1d, output_path):
    """Plot equilibrium IDS output"""
    # init data
    eq_dict = {}
    equilibrium = list(dbs.values())[0].get("equilibrium", lazy=True)

    # init figure
    nrows, ncols = (5, 2)
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(15, 22))
    fig.suptitle(f"{args.shot_nr}: {'-'.join(dbs.keys()).upper()}", fontsize=16)
    axes = axes.flatten()
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    # gather values over time of 0D profiles
    kept_times = []
    for t in equilibrium.time:
        eqs = {
            key: db.get_slice("equilibrium", time_requested=t, **GET_KWARGS)
            for key, db in dbs.items()
        }
        # Skip slices where NICE failed to converge: global_quantities is left as the IMAS
        # empty-value sentinel (+-9e40) rather than a real result, which would otherwise
        # show up as spurious spikes in these 0D traces. Also drop the time itself so the
        # x/y arrays plotted below stay the same length.
        nice_flag = "nice" in eqs and eqs["nice"].code.output_flag
        if nice_flag and nice_flag[0] == -1:
            continue
        kept_times.append(t)
        for field in fields_0d:
            if field[-1] not in eq_dict:
                eq_dict[field[-1]] = {key: [] for key in dbs.keys()}
            vals = {
                key: recomputed_beta(eqs[key], field[-1])
                if field[-1] in RECOMPUTED_0D
                else nested_getattr(eqs[key].time_slice[0], field).value
                for key in dbs.keys()
            }

            for key in dbs.keys():
                if key == "dina":
                    continue
                if "boundary" in field and hasattr(
                    eqs[key].time_slice[0].profiles_1d, field[-1]
                ):
                    nice_arr = getattr(
                        eqs[key].time_slice[0].profiles_1d, field[-1]
                    ).value
                    nice_psi = eqs[key].time_slice[0].profiles_1d.psi.value
                    if len(nice_psi) == 0:
                        continue
                    nice_psi_norm = abs(nice_psi - nice_psi[0]) / abs(
                        nice_psi[-1] - nice_psi[0]
                    )
                    vals[key] = np.interp(0.99, nice_psi_norm, nice_arr)

            for key in dbs.keys():
                eq_dict[field[-1]][key].append(vals[key])

    # plot 0d profiles over time
    for i, (field_key, val) in enumerate(eq_dict.items()):
        title = field_key
        if field_key in RECOMPUTED_0D:
            title += " (recomputed, DD def.)"
        axes[i].set_title(title)
        axes[i].set_ylabel(field_key)
        axes[i].set_xlabel("time")
        for key in dbs.keys():
            axes[i].plot(
                kept_times, eq_dict[field_key][key], label=key, **PLOT_KWARGS
            )
        axes[i].legend()

    # plot 1d profiles for given time values
    for i, field in enumerate(fields_1d):
        idx = len(eq_dict) + i
        axes[idx].set_title(field[-1])
        axes[idx].set_ylabel(field[-1])
        axes[idx].set_xlabel("psi_norm")
        for i_t, t in enumerate(args.t_list):
            for num, key in enumerate(dbs.keys()):
                eq = dbs[key].get_slice("equilibrium", time_requested=t, **GET_KWARGS)
                val = nested_getattr(eq.time_slice[0], field)
                psi = eq.time_slice[0].profiles_1d.psi
                if len(psi) == 0:
                    continue
                psi_norm = abs(psi - psi[0]) / abs(psi[-1] - psi[0])
                if num == 0:
                    axes[idx].plot(psi_norm, val, label=f"t={t}", color=colors[i_t])
                else:
                    axes[idx].scatter(psi_norm, val, color=colors[i_t], marker=".")
        handles, labels = axes[idx].get_legend_handles_labels()
        db_keys = list(dbs.keys())
        if len(db_keys) > 1:
            handles += [
                Line2D([0], [0], color="k", label=f"{db_keys[0]} (line)"),
                Line2D([0], [0], color="k", marker=".", linestyle="None", label=f"{db_keys[1]} (scatter)"),
            ]
        axes[idx].legend(handles=handles)

    # # plot ratio between core pressure values to check b_tor difference
    # if 'dina' in dbs.keys():
    #   vals = []
    #   for t in equilibrium.time:
    #     dina_eq = dbs['dina'].get_slice('equilibrium', time_requested=t, **GET_KWARGS).time_slice[0]
    #     nice_eq = dbs['nice'].get_slice('equilibrium', time_requested=t, **GET_KWARGS).time_slice[0]
    #     vals.append(nice_eq.profiles_1d.pressure[0] / dina_eq.profiles_1d.pressure[0])
    #   axes[idx + 1].plot(equilibrium.time, vals, color=colors[0])
    #   axes[idx + 1].plot(equilibrium.time, np.array(eq_dict['beta_tor']['nice']) / np.array(eq_dict['beta_tor']['dina']), color=colors[1])

    # save fig
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(output_path)


def shape_comparison_plot(args, dbs):
    """Plot the DINA input plasma boundary against the TORAX final-output
    equilibrium boundary, overlaid on a psi contour plot (as in
    visualization/nice_inv.py), for each time in args.t_list."""
    shape_figure_path = f"{args.output_dir}/pds_shape_comparison_{args.shot_nr}.png"
    dina, torax = dbs["dina"], dbs["torax"]

    ncols = min(len(args.t_list), 3)
    nrows = -(-len(args.t_list) // ncols)
    fig, axes = plt.subplots(
        nrows=nrows, ncols=ncols, figsize=(6 * ncols, 6 * nrows), squeeze=False
    )
    fig.suptitle(f"{args.shot_nr}: input vs final output plasma shape", fontsize=16)
    axes = axes.flatten()

    for ax, t in zip(axes, args.t_list):
        dina_ts = dina.get_slice("equilibrium", time_requested=t, **GET_KWARGS).time_slice[0]
        torax_ts = torax.get_slice("equilibrium", time_requested=t, **GET_KWARGS).time_slice[0]

        ax.plot(
            dina_ts.boundary.outline.r,
            dina_ts.boundary.outline.z,
            color="tab:blue",
            linewidth=2,
            label="input (dina)",
        )
        ax.plot(
            torax_ts.boundary.outline.r,
            torax_ts.boundary.outline.z,
            color="tab:red",
            linewidth=2,
            label="final output (torax)",
        )

        ax.set_title(f"t={t}")
        ax.set_xlabel("r [m]")
        ax.set_ylabel("z [m]")
        ax.set_aspect("equal")
        ax.legend()

    for ax in axes[len(args.t_list):]:
        fig.delaxes(ax)

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(shape_figure_path)


if __name__ == "__main__":
    main()
