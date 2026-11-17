"""Scenario-generic TORAX config for the evolutive_controller evolutive coupling.

The EC power waveform arrives as in inverse_convergence: a power-only 'ec' core_sources
source over a MUSCLE3 port (waveform_editor.core_sources_out -> torax.core_sources_in_f),
deposited by the actor's receive_core_sources() with the ecrh
extra_prescribed_power_density shape below -- see torax_muscle3/torax_actor.py. Every other
source is TORAX's own.

NICE evo_rd owns psi: TORAX does not evolve the current and takes psi and I_p from the
equilibrium NICE sends each step (initial psi from the F_INIT equilibrium).

t_initial/t_final and the chease geometry below are placeholders that the actor overwrites
at run time from the received equilibrium (the psi sources reject circular geometry).
"""

import json
from pathlib import Path

import numpy as np

rhon = np.linspace(0, 1, 25)
fixed_dt = 0.01

# EC deposition shape, impurity ratios and radiation multiplier from the shot's DINA run,
# written into the case by preprocess.sh (see preprocessing/dina/torax_params.py).
DINA = json.loads(Path("${CASE_DIR}/preprocess/torax_params.json").read_text())

CONFIG = {
    "profile_conditions": {
        "I_p_source": "geometry",
        "psi_source": "geometry",
    },
    "plasma_composition": {
        "main_ion": {"H": 1},
        "impurity": {
            "species": DINA["impurities"],
            "impurity_mode": "n_e_ratios",
        },
    },
    "numerics": {
        "evolve_current": False,
        "evolve_ion_heat": True,
        "evolve_electron_heat": True,
        "evolve_density": False,
    },
    "geometry": {
        "model_name": "chease",
        "geometry_file": "iterhybrid.mat2cols",
        "n_rho": 50,
    },
    "pedestal": {},
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
            "qlknn": {"model_name": "qlknn", "rho_min": 0.15, "rho_max": 0.93},
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
