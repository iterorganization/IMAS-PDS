"""Scenario-specific TORAX config for 105099 (inverse_convergence loop).

Same structure as the shared config_torax.py, but with Bohm-gyroBohm transport and
time-dependent chi multipliers. The time knots are adapted to this pulse (Ip peaks ~7.4 MA at t~35s,
ramp-down t~40-77s)."""

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
        # TORAX must not add its own ohmic or subtract its own radiation
        # through config - that double-counts terms already inside the imported source.
        "fusion": {},
        "ei_exchange": {},  # internal e<->i transfer; DINA gives no ion source at all
        "bremsstrahlung": {"mode": "ZERO"},
    },
    "transport": {
        "model_name": "bohm-gyrobohm",
        "chi_e_bohm_multiplier": {0: 1.8, 40: 1.8, 60: 4.0, 80: 4.0},
        "chi_i_bohm_multiplier": {0: 1.8, 40: 1.8, 60: 4.0, 80: 4.0},
        "chi_e_gyrobohm_multiplier": {0: 1.8, 40: 1.8, 60: 4.0, 80: 4.0},
        "chi_i_gyrobohm_multiplier": {0: 1.8, 40: 1.8, 60: 4.0, 80: 4.0},
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
