"""Scenario-generic TORAX config for the inverse_convergence loop.

This config carries no scenario-specific input path: the simulated time window is taken
from the equilibrium sequence the actor receives (t_initial/t_final = first/last /time),
and the EC heating power is taken from the core_sources IDS sent to the actor's
core_sources_in_f port: the Waveform-Editor "ec" source carries only
global_quantities/power (a tendency fitted to DINA's summary power_additional by
bin/pds-tendencies), which the actor puts into sources.ecrh.P_total below. Requires
TORAX-MUSCLE3 with power-only source support (power_only_sources in
torax_muscle3/torax_actor.py), which maps an ec source carrying only
global_quantities/power to sources.ecrh.P_total. TORAX computes the EC deposition,
the ohmic heating and the radiation itself.
t_initial/t_final below are placeholders that the actor overwrites at run time.
"""

import numpy as np

rhon = np.linspace(0, 1, 25)
fixed_dt = 0.3

CONFIG = {
    "profile_conditions": {},
    "plasma_composition": {
        "main_ion": {"H": 1},
        "impurity": {
            "species": {
                "Ne": None,
            },
            "impurity_mode": "n_e_ratios_Z_eff",
        },
        "Z_eff": 1.1,
    },
    "numerics": {
        "t_initial": 0.0,  # overwritten by the actor from the received equilibrium /time
        "t_final": 1.0,  # overwritten by the actor from the received equilibrium /time
        "exact_t_final": True,
        "fixed_dt": fixed_dt,
        "adaptive_dt": False,
        "resistivity_multiplier": 1,
        "evolve_current": True,
        "evolve_ion_heat": True,
        "evolve_electron_heat": True,
        "evolve_density": False,
    },
    # circular geometry is only for testing and prototyping
    "geometry": {
        "geometry_type": "circular",
        "n_rho": 25,
    },
    "pedestal": {},
    "mhd": {
        "sawtooth": {
            "trigger_model": {"model_name": "simple"},
            "redistribution_model": {"model_name": "simple"},
        },
    },
    "sources": {
        # The EC power is a Waveform-Editor waveform (core_sources/source(1)/
        # global_quantities/power, read by the TORAX actor into sources.ecrh.P_total);
        # TORAX computes the ohmic heating, the radiation and the EC deposition itself.
        # A waveform file importing DINA's "total" source (additional + ohmic -
        # radiation) as "ec" would double-count the ohmic and radiation terms with
        # this block.
        "fusion": {},
        "ei_exchange": {},  # internal e<->i transfer
        "ohmic": {},  # self-consistent ohmic heating
        "bremsstrahlung": {},  # Wesson model from Z_eff/impurity above
        "impurity_radiation": {},  # Mavrin fit from the Ne impurity above
        # EC deposition model (gaussian_lin_liu; gaussian fitted to DINA 105073's electron
        # heating profile, current drive efficiency at the TORAX default). P_total is set
        # at run time by the actor from the waveform's ec power (0 if none is received).
        "ecrh": {"gaussian_location": 0.3, "gaussian_width": 0.33, "P_total": 0.0},
    },
    "transport": {
        "model_name": "qlknn",
        # set inner core transport coefficients (ad-hoc MHD/EM transport)
        "apply_inner_patch": True,
        "D_e_inner": 0.1,
        "V_e_inner": 0.0,
        "chi_i_inner": 1.5,
        "chi_e_inner": 1.5,
        "rho_inner": 0.15,  # radius below which patch transport is applied
        # set outer core transport coefficients (L-mode near edge region)
        "apply_outer_patch": True,
        "D_e_outer": 0.2,
        "V_e_outer": -0.3,
        "chi_i_outer": 2.0,
        "chi_e_outer": 2.0,
        "rho_outer": 0.93,  # radius above which patch transport is applied
    },
    "solver": {
        "solver_type": "newton_raphson",
        "use_predictor_corrector": True,
        "n_corrector_steps": 10,
        "use_pereverzev": True,
    },
    "time_step_calculator": {
        "calculator_type": "fixed",
    },
    "neoclassical": {
        "bootstrap_current": {"model_name": "sauter"},
    },
}
