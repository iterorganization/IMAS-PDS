"""Scenario-specific TORAX config for 105073 (evolutive_controller coupling).

Same structure as the shared config_torax.py, but with the Bohm-gyroBohm transport
model and chi-multiplier calibration from workflows/inverse_convergence/scenarios/105073/
config_torax.py (chi_*_bohm/gyrobohm_multiplier time knots: x1.8 through flattop, ramped
to x4 over the t=140-205s ramp-down where DINA's confinement collapses with Ip) -- tuned
there against this shot's DINA trace, reused here as-is since it's the same plasma.

t_initial/t_final below are placeholders that the actor overwrites at run time from the
received equilibrium.
"""
import numpy as np

rhon = np.linspace(0, 1, 25)
fixed_dt = 0.01

CONFIG = {
    'profile_conditions': {},
    'plasma_composition': {
        'main_ion': {'H': 1},
        "impurity": {
            "species": {
                "Ne": None,
            },
            "impurity_mode": "n_e_ratios_Z_eff",
        },
        "Z_eff": 1.1,
    },
    'numerics': {
        't_initial': 0.0,  # overwritten by the actor from the received equilibrium /time
        't_final': 1.0,    # overwritten by the actor from the received equilibrium /time
        'exact_t_final': True,
        'fixed_dt': fixed_dt,
        'adaptive_dt': False,
        'resistivity_multiplier': 1,
        'evolve_current': True,
        'evolve_ion_heat': True,
        'evolve_electron_heat': True,
        'evolve_density': False,
    },
    # circular geometry is only for testing and prototyping
    'geometry': {
        'geometry_type': 'circular',
        'n_rho': 25,
    },
    'pedestal': {},
    'mhd': {
        'sawtooth': {
            'trigger_model': {'model_name': 'simple'},
            'redistribution_model': {'model_name': 'simple'},
        },
    },
    'sources': {
        # Physics-based: self-consistent transport, not taken from DINA.
        'ohmic': {},
        'fusion': {},
        'ei_exchange': {},
        'bremsstrahlung': {'mode': 'ZERO'},
        'impurity_radiation': {
            'model_name': 'P_in_scaled_flat_profile',
            'fraction_P_heating': 0.3,
        },
        # Actuators: 'ecrh' added dynamically by receive_core_sources() above.
    },
    "transport": {
        'model_name': 'bohm-gyrobohm',
        # Default BgB coefficients under-transport this scenario (flattop W_th
        # +40% vs DINA) and, with no critical-gradient feedback, nothing pulls
        # Te back during ramp-down where DINA's confinement collapses with Ip.
        # Time-dependent calibration against the 105073 DINA trace: x1.8 through
        # flattop, ramped to x4 in the t=140-205s ramp-down.
        'chi_e_bohm_multiplier': {0: 1.8, 140: 1.8, 175: 4.0, 205: 4.0},
        'chi_i_bohm_multiplier': {0: 1.8, 140: 1.8, 175: 4.0, 205: 4.0},
        'chi_e_gyrobohm_multiplier': {0: 1.8, 140: 1.8, 175: 4.0, 205: 4.0},
        'chi_i_gyrobohm_multiplier': {0: 1.8, 140: 1.8, 175: 4.0, 205: 4.0},
        # set inner core transport coefficients (ad-hoc MHD/EM transport)
        'apply_inner_patch': True,
        'D_e_inner': 0.1,
        'V_e_inner': 0.0,
        'chi_i_inner': 1.5,
        'chi_e_inner': 1.5,
        'rho_inner': 0.15,  # radius below which patch transport is applied
        # set outer core transport coefficients (L-mode near edge region)
        'apply_outer_patch': True,
        'D_e_outer': 0.2,
        'V_e_outer': -0.3,
        'chi_i_outer': 2.0,
        'chi_e_outer': 2.0,
        'rho_outer': 0.93,  # radius above which patch transport is applied
    },
    'solver': {
        'solver_type': 'newton_raphson',
        'use_predictor_corrector': True,
        'n_corrector_steps': 10,
        'use_pereverzev': True,
    },
    'time_step_calculator': {
        'calculator_type': 'fixed',
    },
    'neoclassical': {
        'bootstrap_current': {'model_name': 'sauter'},
    },
}
