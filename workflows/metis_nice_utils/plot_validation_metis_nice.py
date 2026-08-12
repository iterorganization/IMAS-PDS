"""
Validate output of simulations in FBE + Transport coupling
"""

import argparse

import matplotlib.pyplot as plt
import numpy as np
from imas import DBEntry
from imas.ids_defs import CLOSEST_INTERP

PLOT_KWARGS = {"marker": "."}
GET_KWARGS = {"interpolation_method": CLOSEST_INTERP, "lazy": True}


def handle_args():
    parser = argparse.ArgumentParser(
        description="Get preprocessed input data for NICE from DINA"
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


def main():
    """Plot simulation output data for PDS metis+nice coupling"""
    args = handle_args()
    dbs = {
        key: DBEntry(f"imas:hdf5?path={path}", "r")
        for key, path in {
            "dina": args.dina_uri,
            "nice": args.nice_uri,
            "metis": args.metis_uri,
        }.items()
        if path is not None
    }

    pf_active_plots_dina_nice(args, dbs)
    equilibrium_plots_dina_nice(args, dbs)
    equilibrium_plots_nice_metis(args, dbs)

    for db in dbs.values():
        db.close()


def pf_active_plots_dina_nice(args, dbs):
    """Plot pf_active IDS output data for dina-nice"""
    # init data
    coil_figure_path = f"{args.output_dir}/pds_coils_{args.shot_nr}.png"
    coil_dict = {}
    pfas = {
        key: db.get("pf_active") for key, db in dbs.items() if key in ["dina", "nice"]
    }

    # init figure
    nrows, ncols = (5, 3)
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(12, 12))
    axes = axes.flatten()

    # plot data
    for key, pfa in pfas.items():
        for coil in pfa.coil:
            coil_name = str(coil.name)
            if coil_name not in coil_dict:
                coil_dict[coil_name] = max(coil_dict.values(), default=-1) + 1
                axes[coil_dict[coil_name]].set_title(coil_name)
                axes[coil_dict[coil_name]].set_ylabel("current")
                axes[coil_dict[coil_name]].set_xlabel("time")
            nbel = min(len(pfa.time), len(coil.current.data))
            axes[coil_dict[coil_name]].plot(
                pfa.time[:nbel], coil.current.data[:nbel], label=key, **PLOT_KWARGS
            )
            axes[coil_dict[coil_name]].legend()
    for ax in axes[len(pfa.coil) :]:
        fig.delaxes(ax)

    # save figure
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
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


def equilibrium_plots_nice_metis(args, dbs):
    """Plot equilibrium IDS output data for nice+metis"""
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
    ]
    equilibrium_plot_func(
        args,
        {key: val for (key, val) in dbs.items() if key in ["nice", "metis"]},
        equilibrium_fields_0d,
        equilibrium_fields_1d,
        equilibrium_1d_figure_path,
    )


def equilibrium_plot_func(args, dbs, fields_0d, fields_1d, output_path):
    """Plot equilibrium IDS output"""
    # init data
    eq_dict = {}
    equilibrium = next(iter(dbs.values())).get("equilibrium", lazy=True)

    # init figure
    nrows, ncols = (5, 2)
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(12, 12))
    axes = axes.flatten()
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    # gather values over time of 0D profiles
    for t in equilibrium.time:
        eqs = {
            key: db.get_slice("equilibrium", time_requested=t, **GET_KWARGS)
            for key, db in dbs.items()
        }
        for field in fields_0d:
            if field[-1] not in eq_dict:
                eq_dict[field[-1]] = {key: [] for key in dbs}
            vals = {
                key: nested_getattr(eqs[key].time_slice[0], field).value for key in dbs
            }

            for key in dbs:
                if key == "dina":
                    continue
                if "boundary" in field and hasattr(
                    eqs[key].time_slice[0].profiles_1d, field[-1]
                ):
                    nice_arr = getattr(
                        eqs[key].time_slice[0].profiles_1d, field[-1]
                    ).value
                    nice_psi = eqs[key].time_slice[0].profiles_1d.psi.value
                    if nice_psi.size == 0:
                        continue
                    nice_psi_norm = abs(nice_psi - nice_psi[0]) / abs(
                        nice_psi[-1] - nice_psi[0]
                    )
                    vals[key] = np.interp(0.99, nice_psi_norm, nice_arr)

            for key in dbs:
                if abs(vals[key]) > 1e30:
                    vals[key] = None
                eq_dict[field[-1]][key].append(vals[key])

    # plot 0d profiles over time
    for i, field_key in enumerate(eq_dict):
        axes[i].set_title(field_key)
        axes[i].set_ylabel(field_key)
        axes[i].set_xlabel("time")
        for key in dbs:
            axes[i].plot(
                equilibrium.time, eq_dict[field_key][key], label=key, **PLOT_KWARGS
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
                psi_norm = abs(psi - psi[0]) / abs(psi[-1] - psi[0])
                if num == 0:
                    axes[idx].plot(psi_norm, val, label=f"t={t}", color=colors[i_t])
                else:
                    axes[idx].scatter(psi_norm, val, color=colors[i_t], marker=".")
        axes[idx].legend()

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
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(output_path)


if __name__ == "__main__":
    main()
