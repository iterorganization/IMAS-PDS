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


"""Simplified config using mostly defaults for various simulation components."""
CONFIG = {
    'profile_conditions': {
        # 'Ip': {
        #     0: 1e3,
        #     20: 3.5e6,
        #     260: 3.5e6,
        #     280: 0.7e6,
        # },
        # values taken from core profiles IDS
        'T_i': {
            0:   {0.0: 0.2, 0.2: 0.2, 0.4: 0.2, 0.6: 0.1, 0.8: 0.1, 1.0: 0.01},
            15:  {0.0: 2.7, 0.2: 2.4, 0.4: 1.8, 0.6: 1.8, 0.8: 0.4, 1.0: 0.04},
            260: {0.0: 2.8, 0.2: 2.6, 0.4: 1.8, 0.6: 1.0, 0.8: 0.4, 1.0: 0.03},
            280: {0.0: 1.1, 0.2: 1.0, 0.4: 0.7, 0.6: 0.4, 0.8: 0.2, 1.0: 0.02},
        },
        'T_e': {
            0:   {0.0: 1.0, 0.2: 0.9, 0.4: 0.8, 0.6: 0.6, 0.8: 0.4, 1.0: 0.01},
            15:  {0.0: 4.7, 0.2: 4.1, 0.4: 2.5, 0.6: 1.1, 0.8: 0.4, 1.0: 0.04},
            260: {0.0: 4.3, 0.2: 4.0, 0.4: 2.5, 0.6: 1.1, 0.8: 0.4, 1.0: 0.03},
            280: {0.0: 1.9, 0.2: 1.7, 0.4: 0.9, 0.6: 0.4, 0.8: 0.2, 1.0: 0.02},
        },
        'n_e': {
            0: {0.0: 1.4e18, 0.2: 1.3e18, 0.4: 1.3e18, 0.6: 1.2e18, 0.8: 1.0e18, 1.0: 0.7e18},
            15: {0.0: 10.9e18, 0.2: 11.1e18, 0.4: 11.6e18, 0.6: 11.9e18, 0.8: 11.6e18, 1.0: 3.7e18},
            260: {0.0: 12.7e18, 0.2: 12.6e18, 0.4: 12.5e18, 0.6: 12.3e18, 0.8: 11.4e18, 1.0: 3.7e18},
            280: {0.0: 5.8e18, 0.2: 5.6e18, 0.4: 5.1e18, 0.6: 4.4e18, 0.8: 3.4e18, 1.0: 1.3e18},
        },
    },
    'plasma_composition': {
        'main_ion': {'H': 1},
    },
    'numerics': {
        't_initial': 0,
        't_final': 290,
        'exact_t_final': True,
        'fixed_dt': 0.1,
        'resistivity_multiplier': 1,
        'evolve_current': True,
        # 'evolve_current': False,
        'evolve_ion_heat': False,
        'evolve_electron_heat': False,
        'evolve_density': False,
    },
    # circular geometry is only for testing and prototyping
    'geometry': {
        'geometry_type': 'circular',
        'n_rho': 25,
    },
    'pedestal': {},
    'sources': {
        # Ion and electron heat sources (for the temp-ion and temp-el eqs).
        'generic_heat': {
            'gaussian_location': 0.12741589640723575,
            # Gaussian width in normalized radial coordinate r
            'gaussian_width': 0.07280908366127758,
            # total heating (including accounting for radiation) r
            'P_total': 1.0e6,
            # electron heating fraction r
            'electron_heat_fraction': 1.0,
        },
    },
    'transport': {
        'model_name': 'qlknn',
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
        'bootstrap_current': {
            'model_name': 'zeros',
        },
    },
}
