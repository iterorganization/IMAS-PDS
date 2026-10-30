import argparse
from typing import Dict

import matplotlib.pyplot as plt
import numpy as np
from imas import DBEntry, IDSToplevel, DBEntry
from imas.ids_primitive import IDSNumericArray
from imas.ids_defs import CLOSEST_INTERP

PLOT_KWARGS = {"marker": "."}


qe = 1.602176565e-19  # electron charge [C]
me = 9.10938291e-31  # electron mass [kg]
mp = 1.672621777e-27  # proton mass [kg]


def calc_c1(zeff, ne, q, Ro, Rmin, x):
    """Calculate part of the normalized collision frequency :math:`\nu^*`

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
    """Calculate part of the normalized collision frequency :math:`\nu^*`

    Args:
        ne: Electron density [1e19 m^-3]
    """
    c2 = 15.2 - 0.5 * np.log(0.1 * ne)
    return c2


def calc_lambda_e(ne, Te):
    """Calculate the Coulomb constant :math:`\Lambda_e`

    Args:
        ne: Electron density [1e19 m^-3]
        Te: Electron temperature [keV]
    """
    # From QLK source:
    # Lambe(:) = 15.2_DBL - 0.5_DBL*LOG(0.1_DBL*Nex(:)) + LOG(Tex(:))  !Coulomb constant and collisionality. Wesson 2nd edition p661-663
    c2 = calc_c2(ne)
    return c2 + np.log(Te)


def calc_nu_e(ne, Te, zeff, collmult=1):
    """Calculate the collision frequency :math:`\nu_e`

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
    """Calculate the QuaLiKiz bounce frequency :math:`\Lambda_e`

    x is in QuaLiKiz units: :wiki:`Input-and-output-variables#geometry`

    .. math:: \\frac{r_{out} + r_{out,LCFS}}{r_{out,LCFS} + r_{in,LCFS}}

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


def main():
    """Plot simulation output data for PDS metis+nice coupling"""
    args = handle_args()
    dbs = {
        key: DBEntry(f"imas:hdf5?path={path}", "r")
        for key, path in {
            "dina": args.dina_uri,
            "nice": args.nice_uri,
            "metis": args.metis_uri,
            "torax": args.torax_uri,
        }.items()
        if path is not None
    }

    gyrokinetic_transport_plots(args, dbs)

    for db in dbs.values():
        db.close()


def find_nearest(array, value, reverse=False):
    array = np.asarray(array)
    if reverse:
        idx = (np.abs(array.T - value)).argmin()
    else:
        idx = (np.abs(array - value)).argmin()
    return idx


def gyrokinetic_transport_plots(args: argparse.Namespace, dbs: Dict[str, DBEntry]):
    """Plot gyrokinetically important IDS output data from multiple sources"""
    # pf_active_plots_dina_nice(args, dbs)
    # equilibrium_plots_dina_nice(args, dbs)
    # equilibrium_plots_nice_metis(args, dbs)
    # Based on QuaLiKiz input and output

    # If this is workflow prescribed_transport, we have:
    #   * NICE: equilibrium and pf_active
    plot_timeslice(-1, args, dbs)


def plot_timeslice(time_idx: int, args: argparse.Namespace, dbs: Dict[str, DBEntry]):
    print(f"Plotting timeslice t_{{idx}}={time_idx}")

    if "nice" in dbs:
        print("NICE data found, plotting...")
        ni: DBEntry = dbs["nice"]
        ni_eq: IDSToplevel = ni.get("equilibrium")
        # ni_timebase: IDSNumericArray = ni_eq.time
        # ni_pf_act: IDSToplevel = ni.get("pf_active")
        # assert all(ni_timebase == ni_pf_act.time)

    if "torax" in dbs:
        print("Torax data found, plotting...")
        # For Later Database:
        # to_psi = grid.psi
        # to_area = grid.area
        # to_sur = grid.surface
        # to_vol = grid.volume
        # to_rho_tor = grid.rho_tor
        # t_i_avg = cp_slice.t_i_average
        # normni = cp_slice.n_i_total_over_n_e
        # pi_tot = cp_slice.pressure_ion_total
        # p_th = cp_slice.pressure_thermal
        # j_total = cp_slice.j_total
        # j_bootstrap = cp_slice.j_bootstrap
        # cond_parallel = cp_slice.conductivity_parallel
        # vac_tor = to_eq.vacuum_toroidal_field
        # ip = slice.global_quantities.ip
        # dr_inb = slice.profiles_1d.r_inboard
        # dr_outb = slice.profiles_1d.r_outboard
        to: DBEntry = dbs["torax"]
        to_cp: IDSToplevel = to.get("core_profiles")
        to_timebase: IDSNumericArray = to_cp.time
        # to_pf_act: IDSToplevel = to.get("pf_active")
        # assert all(to_timebase == to_pf_act.time)

        cp_slice = to_cp.profiles_1d[time_idx]
        grid = cp_slice.grid
        # to_rho_pol_norm = grid.rho_pol_norm
        to_rho_tor_norm = grid.rho_tor_norm

        elec = cp_slice.electrons
        ion = cp_slice.ion
        neutral = cp_slice.neutral
        assert len(neutral) == 0
        zeff = cp_slice.zeff
        qx = cp_slice.q
        smag = cp_slice.magnetic_shear
        Te = elec.temperature / 1e3  # keV
        Ti0 = ion[0].temperature / 1e3  # keV
        tite0 = Ti0 / Te
        ne = elec.density / 1e19  # 1e19 m3

        # TODO: We can also fill this from the gyrokinetics IDS
        # This'd need Torax development
        dTi0 = np.gradient(Ti0)
        dne = np.gradient(ne)
        dTe = np.gradient(Te)
        Ati = 1
        An = 1
        Ate = 1

        # Eq is on another timebase
        to_eq: IDSToplevel = to.get("equilibrium")
        to_eq_timebase: IDSNumericArray = to_eq.time
        ts = to_eq.time_slice
        time_val = to_timebase[time_idx]
        time_index = to_eq_timebase.value.searchsorted(time_val)
        slice = ts[time_index]
        eq_smag = slice.profiles_1d.magnetic_shear
        eq_qx = slice.profiles_1d.q
        eq_rho_tor_norm = slice.profiles_1d.rho_tor_norm

        zma = slice.global_quantities.magnetic_axis.z
        Rmin = slice.boundary.minor_radius
        rga = slice.boundary.geometric_axis.r
        zz = slice.boundary.outline.z
        rr = slice.boundary.outline.r

        # Midplane-averaged major radius of flux surface
        # Includes Shafranov shift
        Ro = (max(rr) - min(rr)) / 2
        x = np.linspace(0, 1, len(Te))
        tau_bounce = calc_tau_bounce(Te, qx, Ro, Rmin, x)
        nu_e = calc_nu_e(ne, Te, zeff)
        nustar = nu_e * tau_bounce
        logNustar = np.log10(nustar)  # For GK

    if "dina" in dbs:
        print("DINA data found, plotting...")
        di = dbs["dina"]

    if "metis" in dbs:
        print("Metis data found, plotting...")
        me = dbs["metis"]

    # If this is workflow inverse_convergence, we have:
    #   * NICE: equilibrium and pf_active
    #   * Torax: core_profiles, equilibrium, and pf_active

    # If this is workflow evolutive_controller, we have:
    # *
    fig1, ax1 = plt.subplots(figsize=(12, 12))
    (li1,) = ax1.plot(rr, zz)
    ax1.scatter(rga, zma)
    ax1.set_box_aspect(1)
    ax1.plot((min(rr), max(rr)), (zma, zma))

    fig2, axes = plt.subplots(4, 3, figsize=(12, 12))
    (
        ax_Te,
        ax_Ti0,
        ax_ne,
        ax_dTe,
        ax_dTi0,
        ax_dne,
        ax_qx,
        ax_smag,
        ax_x,
        ax_tite0,
        ax_nustar,
        ax_zeff,
    ) = axes.flatten()

    ax_Te.plot(to_rho_tor_norm, Te)
    ax_Te.set_ylabel(r"$T_e$ [keV]")

    ax_dTe.plot(to_rho_tor_norm, dTe)
    ax_dTe.set_ylabel(r"$\partial T_e$ [keV]")

    ax_Ti0.plot(to_rho_tor_norm, Ti0)
    ax_Ti0.set_ylabel(r"$T_{i,0}$ [keV]")
    ax_Ti0.set_ylim(ax_Te.get_ylim()[0], ax_Te.get_ylim()[1])

    ax_dTi0.plot(to_rho_tor_norm, dTi0)
    ax_dTi0.set_ylabel(r"$\partial T_{i,0}$ [keV]")
    ax_dTi0.set_ylim(ax_dTe.get_ylim()[0], ax_dTe.get_ylim()[1])

    ax_ne.plot(to_rho_tor_norm, ne)
    ax_ne.set_ylabel(r"$n_e$ [$10^{-19} m^3$]")

    ax_dne.plot(to_rho_tor_norm, dne)
    ax_dne.set_ylabel(r"$\partial n_e$ [$10^{-19} m^3$]")

    ax_qx.plot(to_rho_tor_norm, qx, label=r"$q_{1D,torax}$")
    ax_qx.plot(eq_rho_tor_norm, eq_qx, label=r"$q_{eq,torax}$")
    ax_qx.set_ylabel(r"$q$ [-]")
    ax_qx.legend()

    ax_smag.plot(to_rho_tor_norm, smag, label=r"$\hat{s}_{1D,torax}$")
    ax_smag.plot(eq_rho_tor_norm, eq_smag, label=r"$\hat{s}_{eq,torax}$")
    ax_smag.set_ylabel(r"$\hat{s}$ [-]")
    ax_smag.legend()
    # x is empty
    ax_x.set_ylabel(r"$x$")

    ax_tite0.plot(to_rho_tor_norm, tite0)
    ax_tite0.set_ylabel(r"$\frac{T_{i,0}}{T_e}$ [-]")

    ax_nustar.plot(to_rho_tor_norm, tite0)
    ax_nustar.set_ylabel(r"$\nu^*$ [-]")

    ax_zeff.plot(to_rho_tor_norm, tite0)
    ax_zeff.set_ylabel(r"$Z_{eff}$ [-]")

    for ax in axes.flatten():
        ax.set_xlabel(r"$\rho_{N,tor}$")

    fig2.suptitle(
        f"t[{time_idx}]={time_val}s, $t=[{round(to_timebase[0], 1)}, {round(to_timebase[-1], 1)}]$"
    )

    subname = "magnetic_equilibrium"
    path = f"{args.output_dir}/{subname}_{args.shot_nr}.png"
    # fig1.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig1.tight_layout()
    fig1.savefig(path)

    subname = "kinetic_sensitivities"
    path = f"{args.output_dir}/{subname}_{args.shot_nr}.png"
    # fig2.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig2.tight_layout()
    fig2.savefig(path)


if __name__ == "__main__":
    main()
