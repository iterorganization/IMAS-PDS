"""Scenario-generic TORAX config for the evolutive_controller evolutive coupling.

core_sources (the EC heating power) is imported the same way inverse_convergence imports
its core_sources: over a MUSCLE3 port (waveform_editor.core_sources_out ->
torax.core_sources_in_f). The Waveform-Editor "ec" source carries only
global_quantities/power (a tendency fitted to DINA's summary power_additional by
bin/pds-tendencies, per-pulse file cases/pulses/files/evolutive_controller_<case>_waveforms.yaml),
which the actor puts into sources.ecrh.P_total below. Requires TORAX-MUSCLE3 with
power-only source support (power_only_sources in torax_muscle3/torax_actor.py), which
maps an ec source carrying only global_quantities/power to sources.ecrh.P_total.
DINA's own core_sources is not imported: its source(1) is the "total" source
(additional + ohmic - radiation) and would double-count the ohmic heating and the
radiation computed below.

t_initial/t_final below are placeholders that the actor overwrites at run time from the
received equilibrium.
"""

import numpy as np

rhon = np.linspace(0, 1, 25)
fixed_dt = 0.01

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
        # Physics-based: self-consistent, not taken from DINA (same models as
        # inverse_convergence/config_torax.py).
        "ohmic": {},
        "fusion": {},
        "ei_exchange": {},
        "bremsstrahlung": {},  # Wesson model from Z_eff/impurity above
        "impurity_radiation": {},  # Mavrin fit from the Ne impurity above
        # EC deposition model (gaussian_lin_liu, same gaussian as inverse_convergence).
        # P_total is set at run time by the actor from the waveform's ec power (0 if
        # none is received).
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
