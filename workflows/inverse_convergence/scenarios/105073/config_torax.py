"""Scenario-specific TORAX config for 105073 (inverse_convergence loop).

Same structure as the shared config_torax.py, but with Bohm-gyroBohm transport
calibrated onto this scenario's DINA trace: the chi-multiplier time knots (x1.8 through
flattop, ramped to x4 over the t=140-205s ramp-down where DINA's confinement collapses
with Ip) reproduce DINA's W_th within ~1% at flattop and through the ramp-down. The
knots are 105073 pulse times and do not transfer to other shots. Selected over the
shared config via torax.python_config_module in this scenario's settings.ymmsl.

The simulated time window is taken from the equilibrium sequence the actor receives
(t_initial/t_final = first/last /time), and the prescribed actuator sources (e.g. ECRH)
come from the core_sources IDS sent to the actor's core_sources_in_f port.
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
    # Sawtooth crashes clamp q0 near 1; without them the core current over-peaks
    # during flattop (q0 drops well below 1 in all DINA scenarios), driving the
    # axis f/b_field_phi away from DINA. The trigger only fires where a q=1
    # surface exists, so phases/scenarios without q<1 are unaffected.
    'mhd': {
        'sawtooth': {
            'trigger_model': {'model_name': 'simple'},
            'redistribution_model': {'model_name': 'simple'},
        },
    },
    'sources': {
        # The "ec" source injected from the received core_sources IDS is DINA's
        # source(1), identifier index=1 = TOTAL, relabeled to ec by the waveform
        # editor: it is the NET electron power balance (EC + ohmic - radiation,
        # verified against the DINA summary IDS power balance for 105073/105099).
        # TORAX must therefore not add its own ohmic or subtract its own radiation
        # on top - that double-counts terms already inside the imported source.
        'fusion': {},
        'ei_exchange': {},  # internal e<->i transfer; DINA gives no ion source at all
        'bremsstrahlung': {'mode': 'ZERO'},
    },
    "transport": {
        'model_name': 'bohm-gyrobohm',
        # Default BgB coefficients under-transport this scenario (flattop W_th
        # +40% vs DINA) and, with no critical-gradient feedback, nothing pulls
        # Te back during ramp-down where DINA's confinement collapses with Ip.
        # Time-dependent calibration against the 105073 DINA trace: x1.8 through
        # flattop, ramped to x4 in the t=140-205s ramp-down. Validated 2026-07-14
        # (W_th matches DINA within ~1%; x1.0 = *_bgb_test, x1.5 = *_bgb_x15_test
        # archive dirs).
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
