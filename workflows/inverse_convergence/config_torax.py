"""Scenario-generic TORAX config for the inverse_convergence loop.

This config carries no scenario-specific input path: the simulated time window is taken
from the equilibrium sequence the actor receives (t_initial/t_final = first/last /time),
and the EC power from the power-only 'ec' core_sources source sent to the actor's
core_sources_in_f port, which the actor deposits with the ecrh
extra_prescribed_power_density shape below; every other source is TORAX's own.
t_initial/t_final below are placeholders that the actor overwrites at run time.
"""

import json
from pathlib import Path

import numpy as np

rhon = np.linspace(0, 1, 25)
fixed_dt = 0.3

# EC deposition shape, impurity ratios and radiation multiplier from the shot's DINA run,
# written into the case by preprocess.sh (see preprocessing/dina/torax_params.py).
DINA = json.loads(Path("${CASE_DIR}/preprocess/torax_params.json").read_text())

CONFIG = {
    "profile_conditions": {
        "I_p_source": "geometry",
        "psi_source": "profile_conditions",
        # placeholder, overwritten by the actor with the psi of the received core_profiles
        "psi": {0.0: {0.0: 0.0, 1.0: 1.0}},
    },
    "plasma_composition": {
        "main_ion": {"H": 1},
        "impurity": {
            "species": DINA["impurities"],
            "impurity_mode": "n_e_ratios",
        },
    },
    "numerics": {
        "evolve_current": True,
        "evolve_ion_heat": True,
        "evolve_electron_heat": True,
        "evolve_density": False,
    },
    # placeholder replaced by the received equilibrium (I_p_source rejects circular)
    "geometry": {
        "model_name": "chease",
        "geometry_file": "iterhybrid.mat2cols",
        "n_rho": 50,
    },
    "pedestal": {},
    "mhd": {
        "sawtooth": {
            "trigger_model": {"model_name": "simple"},
            "redistribution_model": {"model_name": "simple"},
        },
    },
    "sources": {
        "ohmic": {},
        "fusion": {},
        "ei_exchange": {},
        "bremsstrahlung": {},
        "impurity_radiation": {
            "model_name": "mavrin_fit",
            "radiation_multiplier": DINA["radiation_multiplier"],
        },
        "cyclotron_radiation": {},
        # DINA's EC deposition shape, scaled by the actor to the EC power waveform on
        # core_sources_in_f. No ECCD: DINA's EC drives no current.
        "ecrh": {
            "extra_prescribed_power_density": {
                0.0: (
                    np.array(DINA["ec_deposition"]["rho"]),
                    np.array(DINA["ec_deposition"]["profile"]),
                )
            },
            "current_drive_efficiency": 0.0,
        },
    },
    "transport": {
        "core_transport_models": {
            "qlknn": {
                "model_name": "qlknn",
                "rho_min": 0.15,
                "rho_max": 0.93,
            },
            # inner core transport coefficients (ad-hoc MHD/EM transport)
            "inner_patch": {
                "model_name": "prescribed",
                "D_e": 0.1,
                "V_e": 0.0,
                "chi_i": 1.5,
                "chi_e": 1.5,
                "rho_max": 0.15,
            },
            # outer core transport coefficients (L-mode near edge region)
            "outer_patch": {
                "model_name": "prescribed",
                "D_e": 0.2,
                "V_e": -0.3,
                "chi_i": 2.0,
                "chi_e": 2.0,
                "rho_min": 0.93,
                "rho_max": 1.0,
            },
        },
    },
    "solver": {
        "solver_type": "newton_raphson",
        "use_fixed_point": True,
        "n_fixed_point_iterations": 10,
        "use_pereverzev": True,
    },
    "time_step_calculator": {
        "calculator_type": "fixed",
        "dt": fixed_dt,
        "t_initial": 0.0,  # overwritten by the actor from the received equilibrium /time
        "t_final": 1.0,  # overwritten by the actor from the received equilibrium /time
        "exact_t_final": True,
        "allow_backtracking": False,
    },
    "neoclassical": {
        "bootstrap_current": {"model_name": "sauter"},
    },
}
