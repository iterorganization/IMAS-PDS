# Copyright 2024 DeepMind Technologies Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
t_init = 0
n_t = 100
dt = 0.1


"""Simplified config using mostly defaults for various simulation components."""
CONFIG = {
    "profile_conditions": {  # use default profile conditions
        "n_e": {0: {0.0: 1.5e20, 1.0: 0.5e20}},  # Initial electron density profile
        "normalize_n_e": False,
        "n_e_bar_is_f_GW": False,
        "n_e_right_bc": None,
        # 'initial_j_is_total_current': False    # the default is False, but I am wondering if this should not be True since you want to reinforce the 'total' plasma current to be a desired value, not only the ohmic current (?)
        "initial_j_is_total_current": True,  # the default is False, but I am wondering if this should not be True since you want to reinforce the 'total' plasma current to be a desired value, not only the ohmic current (?)
        "I_p": 15e6,
        "psi_source": "j",
    },
    "plasma_composition": {},  # use default plasma composition
    "numerics": {
        "evolve_current": True,
        "evolve_ion_heat": False,
        "evolve_electron_heat": False,
        "evolve_density": False,
    },
    # circular geometry is only for testing and prototyping
    "geometry": {
        "model_name": "circular",
        # 'n_rho': 25,
        "n_rho": 25,
    },
    "sources": {
        # Current sources (for psi equation)
        "generic_current": {
            "fraction_of_total_current": 0.2,
            "gaussian_width": 0.05,
            "gaussian_location": 0.4,
        },
        # Electron density sources/sink (for the ne equation).
        "generic_particle": {
            "S_total": 1e22,
            "particle_width": 0.25,
            "deposition_location": 0.0,
        },
        "gas_puff": {"S_total": 1e22, "puff_decay_length": 0.05},
        "pellet": {
            "S_total": 2e22,
            "pellet_width": 0.1,
            "pellet_deposition_location": 0.85,
        },
        # Ion and electron heat sources (for the temp-ion and temp-el eqs).
        "generic_heat": {
            "P_total": 120e6,
            "gaussian_width": 0.25,
            "gaussian_location": 0.0,
            "electron_heat_fraction": 0.66666,
        },
        "fusion": {},
        "ei_exchange": {},
        "ohmic": {},
    },
    "pedestal": {},
    "transport": {
        "core_transport_models": {
            "prescribed": {
                "model_name": "prescribed",
                "chi_i": 1e-4,
                "chi_e": 1e-4,
                "D_e": 1e-4,
                "V_e": 1e-4,
            },
        },
        "smoothing_width": 0.1,
    },
    "solver": {
        "solver_type": "linear",
        "use_pereverzev": True,
    },
    "time_step_calculator": {
        "calculator_type": "fixed",
        "dt": dt,
        "t_initial": t_init,
        "t_final": t_init + n_t * dt,
        "exact_t_final": True,
    },
    "neoclassical": {
        "bootstrap_current": {
            "model_name": "zeros",
        },
    },
}
