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
t_init = 225.00319561
n_t = 0
dt = 0.001


"""Simplified config using mostly defaults for various simulation components."""
CONFIG = {
    'profile_conditions': {            # use default profile conditions
        'n_e': {0: {0.0: 1.5e20, 1.0: 0.5e20}},  # Initial electron density profile
        'normalize_n_e_to_nbar': False,
        'n_e_nbar_is_fGW': False,
        'n_e_right_bc': None,
        # 'initial_j_is_total_current': False    # the default is False, but I am wondering if this should not be True since you want to reinforce the 'total' plasma current to be a desired value, not only the ohmic current (?)
        'initial_j_is_total_current': True    # the default is False, but I am wondering if this should not be True since you want to reinforce the 'total' plasma current to be a desired value, not only the ohmic current (?)
    },
    'plasma_composition': {},  # use default plasma composition
    'numerics': {
        't_initial': t_init,
        't_final': t_init + n_t * dt,
        'exact_t_final': True,
        'fixed_dt': dt,
        'resistivity_multiplier': 1,
        'evolve_current': True,
        'evolve_ion_heat': False,
        'evolve_electron_heat': False,
        'evolve_density': False,
    },
    # circular geometry is only for testing and prototyping
    'geometry': {
        'geometry_type': 'circular',
        # 'n_rho': 25,
        'n_rho': 25,
    },
    'sources': {
        # Current sources (for psi equation)
        'generic_current': {},
        # Electron density sources/sink (for the ne equation).
        'generic_particle': {},
        'gas_puff': {},
        'pellet': {},
        # Ion and electron heat sources (for the temp-ion and temp-el eqs).
        'generic_heat': {},
        'fusion': {},
        'ei_exchange': {},
        'ohmic': {},
    },
    'pedestal': {},
    'transport': {
        'model_name': 'constant', # 'qlknn', 'constant'
        'smooth_everywhere': True,
        'smoothing_width': 0.1,
        'chi_i': 1e-4,
        'chi_e': 1e-4,
        'D_e': 1e-4,
        'V_e': 1e-4,
    },
    'solver': {
        'solver_type': 'linear',
        'n_corrector_steps': 10,
        'use_pereverzev': True,
    },
    'time_step_calculator': {
        'calculator_type': 'fixed',
    },
    'neoclassical': {
        'bootstrap_current': {
            'model_name': 'zeros',
        },
    },
}
