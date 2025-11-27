"""Simplified config using mostly defaults for various simulation components."""

imas_uri = "imas:hdf5?path=[BASEDIR_PLACEHOLDER]/scenario_configs/[SHOT_NR]_torax_nice/tmp/data/[SHOT_NR]_in/"

def get_imas_profile_conditions(imas_uri):
    import imas
    profile_conditions = {}
    with imas.DBEntry(imas_uri, 'r') as db:
        cp = db.get('core_profiles')
        T_i = {}
        T_e = {}
        n_e = {}
        for p1d in cp.profiles_1d:
            t = int(p1d.time)
            n_rho = p1d.grid.rho_tor_norm
            # change temperatures from eV in IDS to KeV for torax
            T_i[t] ={float(n_rho[i]): float(p1d.t_i_average[i]) / 1000 for i in range(len(n_rho))}
            T_e[t] ={float(n_rho[i]): float(p1d.electrons.temperature[i]) / 1000 for i in range(len(n_rho))}
            n_e[t] ={float(n_rho[i]): float(p1d.electrons.density[i]) for i in range(len(n_rho))}
        profile_conditions['T_i'] = T_i
        profile_conditions['T_e'] = T_e
        profile_conditions['n_e'] = n_e
    return profile_conditions

def get_imas_sources(imas_uri):
    import imas
    import numpy as np
    with imas.DBEntry(imas_uri, 'r') as db:
        cs = db.get('core_sources')
        times = np.array(cs.time)
        rho_n = np.array(cs.source[0].profiles_1d[0].grid.rho_tor_norm)
        heating = np.stack([np.array(cs.source[0].profiles_1d[t_i].electrons.energy) for t_i in range(len(cs.time))])
        psi = np.zeros(heating.shape)
        ecrh = (
            (times, rho_n, heating), # TEMP_EL
            (times, rho_n, psi), # PSI
        )
        sources = {
            'ecrh': {
                'mode': 'PRESCRIBED',
                'is_explicit': True,
                'prescribed_values': ecrh,
            }
        }
    return sources

def get_t_values(imas_uri):
    import imas
    import numpy as np
    with imas.DBEntry(imas_uri, 'r') as db:
        eq = db.get('equilibrium')
        t_initial = eq.time[0]
        t_final = eq.time[-1]
    return t_initial, t_final

t_initial, t_final = get_t_values(imas_uri)

CONFIG = {
    'profile_conditions': get_imas_profile_conditions(imas_uri),
    'plasma_composition': {
        'main_ion': {'H': 1},
    },
    'numerics': {
        't_initial': t_initial,
        't_final': t_final,
        'exact_t_final': True,
        'fixed_dt': 0.1,
        'adaptive_dt': False,
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
    # 'sources': {
    #     # Ion and electron heat sources (for the temp-ion and temp-el eqs).
    #     'generic_heat': {
    #         'gaussian_location': 0.12741589640723575,
    #         # Gaussian width in normalized radial coordinate r
    #         'gaussian_width': 0.07280908366127758,
    #         # total heating (including accounting for radiation) r
    #         'P_total': 1.0e6,
    #         # electron heating fraction r
    #         'electron_heat_fraction': 1.0,
    #     },
    # },
    'sources': get_imas_sources(imas_uri),
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
