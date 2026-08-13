"""Scenario-generic TORAX config for the evolutive_controller evolutive coupling.

core_sources (the DINA-derived ECRH actuator trace) is imported the same way
inverse_convergence imports its core_sources: over a MUSCLE3 port (waveform_editor.core_sources_out ->
torax.core_sources_in_f), converted by the actor's receive_core_sources()/sources_from_IMAS()
and merged in via torax_config.update_fields({"sources.<key>": ...}) -- see
torax_muscle3/torax_actor.py.

That update_fields() call overrides sources.<key> for every key present in the imported IDS,
not just 'ecrh' -- so this only stays self-consistent (ohmic/impurity_radiation computed by
TORAX, not overridden by DINA) because sources_from_IMAS() only converts source entries whose
identifier.name matches one of its recognized keys ('ec', 'ohmic', 'fusion', ... -- see
torax/_src/imas_tools/input/core_sources.py) and silently skips everything else. Verified for
this shot: DINA's raw core_sources record (scenarios/<shot>/tmp/data/<shot>_in) has 15 source
entries all with an empty identifier.name; waveforms.yaml relabels only source(1) to 'ec', so
sources_from_IMAS() picks up exactly ecrh and nothing else. If a different shot's DINA data
carries real identifier names on other sources (e.g. an actual 'ohmic' label), those would
silently override the physics-based config below -- worth re-checking per shot.

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
        # Actuators: 'ecrh' added by scenarios/<shot>/config_torax.py.
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