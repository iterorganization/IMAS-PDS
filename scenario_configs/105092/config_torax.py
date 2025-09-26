"""Simplified config using mostly defaults for various simulation components."""

imas_uri = "imas:hdf5?path=/home/ITER/sanderm/gitrepos/pds/scenario_configs/105092/tmp/data/105092_in/"

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

# def get_imas_sources(imas_uri):
#     import imas
#     with imas.DBEntry(imas_uri, 'r') as db:
#         cs = db.get('core_sources')
#         n_time = len(cs.time)
#         ecrh = {}
#         for source in cs.source:
#             if len(source.profiles_1d) != n_time:
#                 continue
#             if len([
#                 p1d 
#                 for p1d in source.profiles_1d 
#                 if len(p1d.grid.rho_tor_norm) == len(p1d.electrons.energy)
#             ]) != n_time:
#                 continue
#             for t_i in range(n_time):
#                 t = int(cs.time[t_i])
#                 rho_n = source.profiles_1d[t_i].grid.rho_tor_norm
#                 if t not in ecrh.keys():
#                     ecrh[t] = {float(rho_n[i]): 0 for i in range(len(rho_n))}
#                 for i in range(len(rho_n)):
#                     ecrh[t][float(rho_n[i])] += source.profiles_1d[t_i].electrons.energy[i]
#         sources = {
#         'ecrh': {'extra_prescribed_power_density': ecrh}
#         }
#     return sources

CONFIG = {
    # 'profile_conditions': {
    #     # 'Ip': {
    #     #     0: 1e3,
    #     #     10: 3e6,
    #     #     147: 3e6,
    #     #     169: 1e3,
    #     # },
    #     # values taken from core profiles IDS
    #     'T_i': {
    #         0:   {0.0: 0.2, 0.2: 0.2, 0.4: 0.2, 0.6: 0.1, 0.8: 0.1, 1.0: 0.1},
    #         10:  {0.0: 2.5, 0.2: 2.1, 0.4: 1.4, 0.6: 0.8, 0.8: 0.4, 1.0: 0.1},
    #         147: {0.0: 1.6, 0.2: 1.6, 0.4: 1.5, 0.6: 1.0, 0.8: 0.5, 1.0: 0.1},
    #         169: {0.0: 0.8, 0.2: 0.7, 0.4: 0.6, 0.6: 0.3, 0.8: 0.2, 1.0: 0.1},
    #     },
    #     'T_e': {
    #         0:   {0.0: 1.0, 0.2: 0.9, 0.4: 0.8, 0.6: 0.6, 0.8: 0.4, 1.0: 0.1},
    #         10:  {0.0: 6.6, 0.2: 4.0, 0.4: 1.6, 0.6: 0.9, 0.8: 0.5, 1.0: 0.1},
    #         147: {0.0: 2.2, 0.2: 2.1, 0.4: 2.0, 0.6: 1.3, 0.8: 0.5, 1.0: 0.1},
    #         169: {0.0: 1.5, 0.2: 1.5, 0.4: 0.8, 0.6: 0.4, 0.8: 0.2, 1.0: 0.1},
    #     },
    #     'n_e': {
    #         0: {0.0: 1.35e18, 0.2: 1.34e18, 0.4: 1.31e18, 0.6: 1.22e18, 0.8: 1.03e18, 1.0: 0.7e18},
    #         10: {0.0: 12.7e18, 0.2: 12.7e18, 0.4: 12.55e18, 0.6: 11.82e18, 0.8: 10.1e18, 1.0: 3.5e18},
    #         147: {0.0: 15e18, 0.2: 14.6e18, 0.4: 13.7e18, 0.6: 12.2e18, 0.8: 10e18, 1.0: 3.6e18},
    #         169: {0.0: 5.3e18, 0.2: 5.1e18, 0.4: 4.5e18, 0.6: 3.6e18, 0.8: 2.6e18, 1.0: 1.1e18},
    #     },
    # },
    'profile_conditions': get_imas_profile_conditions(imas_uri),
    'plasma_composition': {
        'main_ion': {'H': 1},
    },
    'numerics': {
        't_initial': 0,
        't_final': 170,
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
