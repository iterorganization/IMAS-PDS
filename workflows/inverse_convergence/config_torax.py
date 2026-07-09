"""Scenario-generic TORAX config for the inverse_convergence loop.

This config carries no scenario-specific input path: the simulated time window is taken
from the equilibrium sequence the actor receives (t_initial/t_final = first/last /time),
and the prescribed actuator sources (e.g. ECRH) are taken from the core_sources IDS sent
to the actor's core_sources_in_f port. t_initial/t_final below are placeholders that the
actor overwrites at run time.
"""
import numpy as np

rhon = np.linspace(0, 1, 25)
fixed_dt = 0.3

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
    'sources': {
        # Physics-based sources
        'ohmic': {},
        'fusion': {},
        'ei_exchange': {},
        # bremsstrahlung cannot be used simultaneously with impurity model mavrin_fit
        'bremsstrahlung': {'mode': 'ZERO'},
        'impurity_radiation': {
            'model_name': 'P_in_scaled_flat_profile',
            'fraction_P_heating': 0.3,
        },
        # Actuators (e.g. ecrh) are injected from the received core_sources IDS.
    },
    "transport": {
        'model_name': 'qlknn',
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
