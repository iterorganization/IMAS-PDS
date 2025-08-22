"""
Validate output of simulations in FBE + Transport coupling
"""

import os
import matplotlib.pyplot as plt
import numpy as np
from imas import DBEntry, IDSFactory
from imas.ids_defs import CLOSEST_INTERP

ORIGINAL_PATH = '/home/ITER/sanderm/gitrepos/pds/run/temp_data/105084_in'
RESULT_PATH = '/home/ITER/sanderm/gitrepos/pds/run/temp_data/105084_out'
EQUILIBRIUM_FIGURE_PATH = '/home/ITER/sanderm/gitrepos/pds/run/tmp/pds_run_equilibrium.png'
COIL_FIGURE_PATH = '/home/ITER/sanderm/gitrepos/pds/run/tmp/pds_run_coils.png'

EQUILIBRIUM_FIELDS = [
  # ('profiles_1d', 'elongation'),
  # ('profiles_1d', 'triangularity'),
  ('global_quantities', 'ip'),
  ('global_quantities', 'magnetic_axis', 'r'),
  ('global_quantities', 'magnetic_axis', 'z'),
  ('global_quantities', 'magnetic_axis', 'b_field_phi'),
  ('global_quantities', 'li_3'),
  ('global_quantities', 'beta_pol'),
  ('global_quantities', 'beta_tor'),
  ('boundary', 'psi'),
  ('boundary', 'elongation'),
  ('boundary', 'triangularity'),
  # ('x-point'),
]

PF_ACTIVE_FIELDS = [
  # ('coil currents'),
]

def nested_getattr(obj, name_list):
  if len(name_list) == 0:
    return obj
  else:
    new_obj = getattr(obj, name_list[0])
    return nested_getattr(new_obj, name_list[1:])

def main():
  db_org = DBEntry(f"imas:hdf5?path={ORIGINAL_PATH}", 'r')
  db_res = DBEntry(f"imas:hdf5?path={RESULT_PATH}", 'r')

  ###############
  # EQUILIBRIUM #
  ###############
  eq_dict = {}
  equilibrium = db_org.get('equilibrium', lazy=True)
  kwargs = {'interpolation_method': CLOSEST_INTERP, 'lazy': True}
  for t in equilibrium.time:
    eq_org = db_org.get_slice('equilibrium', time_requested=t, **kwargs)
    eq_res = db_res.get_slice('equilibrium', time_requested=t, **kwargs)
    for field in EQUILIBRIUM_FIELDS:
      if field[-1] not in eq_dict:
        eq_dict[field[-1]] = {'org': [], 'res': []}
      val_org = nested_getattr(eq_org.time_slice[0], field).value
      val_res = nested_getattr(eq_res.time_slice[0], field).value
      eq_dict[field[-1]]['org'].append(val_org)
      eq_dict[field[-1]]['res'].append(val_res)
  nrows, ncols = (4, 4)
  fig, axes = plt.subplots(nrows=nrows, ncols=nrows, figsize=(12,12))
  axes = axes.flatten()
  kwargs = {'marker': '.'}
  for i, (key, val) in enumerate(eq_dict.items()): 
    axes[i].set_title(key)
    axes[i].set_ylabel(key)
    axes[i].set_xlabel('time')
    axes[i].plot(equilibrium.time, eq_dict[key]['org'], label='org', **kwargs)
    axes[i].plot(equilibrium.time, eq_dict[key]['res'], label='res', **kwargs)
    axes[i].legend()
  fig.tight_layout(rect=[0, 0.03, 1, 0.95])
  fig.savefig(EQUILIBRIUM_FIGURE_PATH)

  #################
  # COIL CURRENTS #
  #################
  coil_dict = {}
  pfa_org = db_org.get('pf_active')
  pfa_res = db_res.get('pf_active')
  nrows, ncols = (4, 4)
  fig, axes = plt.subplots(nrows=nrows, ncols=nrows, figsize=(12,12))
  axes = axes.flatten()
  kwargs = {'marker': '.'}
  for coil in pfa_org.coil:
    coil_name = str(coil.name)
    if coil_name not in coil_dict:
      coil_dict[coil_name] = max(coil_dict.values(), default=-1) + 1
    axes[coil_dict[coil_name]].set_title(coil_name)
    axes[coil_dict[coil_name]].set_ylabel('current')
    axes[coil_dict[coil_name]].set_xlabel('time')
    axes[coil_dict[coil_name]].plot(pfa_org.time, coil.current.data, label='org', **kwargs)
  for coil in pfa_res.coil:
    coil_name = str(coil.name)
    axes[coil_dict[coil_name]].plot(pfa_res.time, coil.current.data, label='res', **kwargs)
    axes[coil_dict[coil_name]].legend()
  fig.tight_layout(rect=[0, 0.03, 1, 0.95])
  fig.savefig(COIL_FIGURE_PATH)

  db_org.close()
  db_res.close()

if __name__ == '__main__':
  main()

