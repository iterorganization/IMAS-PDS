"""Scenario-specific TORAX config for 105073 (inverse_convergence loop).

Same structure as the shared config_torax.py, but with Bohm-gyroBohm transport
calibrated onto this scenario's DINA trace: the chi-multiplier time knots (x1.8 through
flattop, ramped to x4 over the t=140-205s ramp-down where DINA's confinement collapses
with Ip)."""

import json
from pathlib import Path

import numpy as np

rhon = np.linspace(0, 1, 25)
fixed_dt = 0.3

# EC deposition shape, impurity ratios and radiation multiplier from the shot's DINA run,
# written into the case by preprocess.sh (see preprocessing/dina/torax_params.py).
DINA = json.loads(Path("${CASE_DIR}/preprocess/torax_params.json").read_text())

CONFIG = {
    "profile_conditions": {},
    "plasma_composition": {
        "main_ion": {"H": 1},
        "impurity": {
            "species": DINA["impurities"],
            "impurity_mode": "n_e_ratios",
        },
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
        "model_name": "bohm-gyrobohm",
        # Default BgB coefficients under-transport this scenario (flattop W_th
        # +40% vs DINA) and, with no critical-gradient feedback, nothing pulls
        # Te back during ramp-down where DINA's confinement collapses with Ip.
        # Time-dependent calibration against the 105073 DINA trace: x1.8 through
        # flattop, ramped to x4 in the t=140-205s ramp-down.
        "chi_e_bohm_multiplier": {0: 1.8, 140: 1.8, 175: 4.0, 205: 4.0},
        "chi_i_bohm_multiplier": {0: 1.8, 140: 1.8, 175: 4.0, 205: 4.0},
        "chi_e_gyrobohm_multiplier": {0: 1.8, 140: 1.8, 175: 4.0, 205: 4.0},
        "chi_i_gyrobohm_multiplier": {0: 1.8, 140: 1.8, 175: 4.0, 205: 4.0},
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
