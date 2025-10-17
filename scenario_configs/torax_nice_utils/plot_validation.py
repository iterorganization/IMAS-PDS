"""
Validate output of simulations in FBE + Transport coupling
"""

import os
import matplotlib.pyplot as plt
import numpy as np
from imas import DBEntry, IDSFactory
from imas.ids_defs import CLOSEST_INTERP

# SHOT_NR = 105084
# T_LIST = [10, 150, 270]
SHOT_NR = 105092
T_LIST = [10, 110, 150]

PATHS = {
  # 'dina': f"/home/ITER/sanderm/gitrepos/pds/scenario_configs/{SHOT_NR}/tmp/data/{SHOT_NR}_in",
  'nice': f"/home/ITER/sanderm/gitrepos/pds/scenario_configs/{SHOT_NR}/tmp/data/{SHOT_NR}_out_nice",
  'torax': f"/home/ITER/sanderm/gitrepos/pds/scenario_configs/{SHOT_NR}/tmp/data/{SHOT_NR}_out_torax",
}
EQUILIBRIUM_FIGURE_PATH = f"/home/ITER/sanderm/gitrepos/pds/run/tmp/pds_run_equilibrium_{SHOT_NR}.png"
COIL_FIGURE_PATH = f"/home/ITER/sanderm/gitrepos/pds/run/tmp/pds_run_coils_{SHOT_NR}.png"

EQUILIBRIUM_FIELDS_0D = [
  # ('global_quantities', 'ip'),
  # ('global_quantities', 'magnetic_axis', 'b_field_phi'),
  # ('global_quantities', 'magnetic_axis', 'r'),
  # ('global_quantities', 'magnetic_axis', 'z'),
  # ('global_quantities', 'beta_pol'),
  # ('global_quantities', 'beta_tor'),
  # ('global_quantities', 'li_3'),
  # ('boundary', 'elongation'),
  # ('boundary', 'psi'),
  # ('boundary', 'triangularity'),
]

EQUILIBRIUM_FIELDS_1D = [
  ('profiles_1d', 'pressure'),
  ('profiles_1d', 'dpressure_dpsi'),
  ('profiles_1d', 'f'),
  ('profiles_1d', 'f_df_dpsi'),
  ('profiles_1d', 'psi'),
  ('profiles_1d', 'q'),
  ('profiles_1d', 'j_phi'),
  ('profiles_1d', 'gm2'),
  # ('profiles_1d', 'volume'),
  # ('profiles_1d', 'elongation'),
]

PLOT_KWARGS = {'marker': '.'}
GET_KWARGS = {'interpolation_method': CLOSEST_INTERP, 'lazy': True}

def nested_getattr(obj, name_list):
  if len(name_list) == 0:
    return obj
  else:
    new_obj = getattr(obj, name_list[0])
    return nested_getattr(new_obj, name_list[1:])

def main():
  dbs = {
    key: DBEntry(f"imas:hdf5?path={path}", 'r')
    for key, path in PATHS.items()
  }

  equilibrium_plots(dbs)
  pf_active_plots(dbs)

  for db in dbs.values():
    db.close()

def equilibrium_plots(dbs):
  eq_dict = {}
  equilibrium = list(dbs.values())[0].get('equilibrium', lazy=True)
  for t in equilibrium.time:
    eqs = {
      key: db.get_slice('equilibrium', time_requested=t, **GET_KWARGS)
      for key, db in dbs.items()
    }
    for field in EQUILIBRIUM_FIELDS_0D:
      if field[-1] not in eq_dict:
        eq_dict[field[-1]] = {key: [] for key in dbs.keys()}
      vals = {
        key: nested_getattr(eqs[key].time_slice[0], field).value
        for key in dbs.keys()
      }

      for key in dbs.keys():
        if key == 'dina':
          continue 
        if 'boundary' in field and hasattr(eqs[key].time_slice[0].profiles_1d, field[-1]):
          nice_arr = getattr(eqs[key].time_slice[0].profiles_1d, field[-1]).value
          nice_psi = eqs[key].time_slice[0].profiles_1d.psi.value
          nice_psi_norm = abs(nice_psi - nice_psi[0]) / abs(nice_psi[-1] - nice_psi[0])
          vals[key] = np.interp(0.99, nice_psi_norm, nice_arr)

      for key in dbs.keys():
        eq_dict[field[-1]][key].append(vals[key])
  nrows, ncols = (5, 2)
  fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(12,12))
  axes = axes.flatten()
  colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
  for i, (field_key, val) in enumerate(eq_dict.items()): 
    axes[i].set_title(field_key)
    axes[i].set_ylabel(field_key)
    axes[i].set_xlabel('time')
    for key in dbs.keys():
      axes[i].plot(equilibrium.time, eq_dict[field_key][key], label=key, **PLOT_KWARGS)
    axes[i].legend()
  for i, field in enumerate(EQUILIBRIUM_FIELDS_1D):
    idx = len(eq_dict) + i
    axes[idx].set_title(field[-1])
    axes[idx].set_ylabel(field[-1])
    axes[idx].set_xlabel('psi_norm')
    for i_t, t in enumerate(T_LIST):
      for num, key in enumerate(dbs.keys()):
        eq = dbs[key].get_slice('equilibrium', time_requested=t, **GET_KWARGS)
        val = nested_getattr(eq.time_slice[0], field)
        psi = eq.time_slice[0].profiles_1d.psi
        psi_norm = abs(psi - psi[0]) / abs(psi[-1] - psi[0])
        if num == 0:
          axes[idx].plot(psi_norm, val, label=f"t={t}", color=colors[i_t])
        else:
          axes[idx].scatter(psi_norm, val, color=colors[i_t], marker='.')
    axes[idx].legend()
  if 'dina' in dbs.keys():
    vals = []
    for t in equilibrium.time:
      dina_eq = dbs['dina'].get_slice('equilibrium', time_requested=t, **GET_KWARGS).time_slice[0]
      nice_eq = dbs['nice'].get_slice('equilibrium', time_requested=t, **GET_KWARGS).time_slice[0]
      vals.append(nice_eq.profiles_1d.pressure[0] / dina_eq.profiles_1d.pressure[0])
    axes[idx + 1].plot(equilibrium.time, vals, color=colors[0])
    axes[idx + 1].plot(equilibrium.time, np.array(eq_dict['beta_tor']['nice']) / np.array(eq_dict['beta_tor']['dina']), color=colors[1])

  fig.tight_layout(rect=[0, 0.03, 1, 0.95])
  fig.savefig(EQUILIBRIUM_FIGURE_PATH)

def pf_active_plots(dbs):
  coil_dict = {}
  pfas = {
    key: db.get('pf_active')
    for key, db in dbs.items()
  }
  nrows, ncols = (5, 3)
  fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(12,12))
  axes = axes.flatten()
  for key, pfa in pfas.items():
    for coil in pfa.coil:
      coil_name = str(coil.name)
      if coil_name not in coil_dict:
        coil_dict[coil_name] = max(coil_dict.values(), default=-1) + 1
        axes[coil_dict[coil_name]].set_title(coil_name)
        axes[coil_dict[coil_name]].set_ylabel('current')
        axes[coil_dict[coil_name]].set_xlabel('time')
      axes[coil_dict[coil_name]].plot(pfa.time, coil.current.data, label=key, **PLOT_KWARGS)
      axes[coil_dict[coil_name]].legend()
  fig.tight_layout(rect=[0, 0.03, 1, 0.95])
  fig.savefig(COIL_FIGURE_PATH)

if __name__ == '__main__':
  main()

