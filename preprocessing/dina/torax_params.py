"""TORAX settings derived from a DINA run, read by the TORAX workflows' config_torax.py.

- ec_deposition: EC power density shape (rho, profile; max 1) for TORAX's ecrh, which the
  TORAX actor scales to the received EC power. As in DINA's own deposition, each launcher
  (pulse_schedule.ec) heats its 0.2-wide rho band at a density set by its peak power.
- impurities: n_imp/n_e at the flattop per impurity DINA carries (W, O, ...). TORAX's own
  radiation and Z_eff follow from these, as DINA's did.
- radiation_multiplier: DINA's W line radiation over what TORAX's mavrin_fit gives on
  DINA's flattop T_e and n_e with that W ratio, so TORAX radiates what DINA did.

usage: torax_params.py <dina-uri> <out-json>
"""

import json
import sys
from pathlib import Path

import imas
import numpy as np
from imas.ids_defs import CLOSEST_INTERP

# Each DINA launcher deposits over a 0.2-wide rho band ("rho=0.0-0.2", ...).
LAUNCHER_BAND = 0.2
DEPOSITION_POINTS = 200  # no point on a band edge
# DINA keeps unused species at numerical-zero densities (n/n_e ~1e-14 and below).
MIN_RATIO = 1e-8
IMPURITY_SYMBOLS = {2: "He", 4: "Be", 8: "O", 10: "Ne", 18: "Ar", 74: "W"}
LINE_RADIATION = 203
W_Z = 74
# TORAX's coronal Mavrin fit for W (torax/_src/physics/radiation/
# mavrin_coronal_cooling_rate.py): log10(L_W [W m^3]) quartic in log10(T_e [keV]).
W_MAVRIN_INTERVALS = [1.5, 4.0]
W_MAVRIN_COEFFS = np.array(
    [
        [-1.0103e-01, 5.1849e01, -3.6759e-01],
        [-1.0311e00, -6.3303e01, 2.6627e00],
        [-9.5126e-01, 2.2824e01, -6.2740e00],
        [3.8304e-01, -2.9208e00, 5.2499e00],
        [-3.0374e01, -3.0238e01, -3.2153e01],
    ]
)
# Flattop slices the radiation multiplier is averaged over (DINA's core sawteeth).
N_FLATTOP_SLICES = 8


def ec_deposition(pulse_schedule):
    rho = np.linspace(0, 1, DEPOSITION_POINTS)
    profile = np.zeros_like(rho)
    for launcher in pulse_schedule.ec.launcher:
        power = np.max(launcher.power.reference.data, initial=0.0)
        center = launcher.deposition_rho_tor_norm.reference.data[0]
        band = np.abs(rho - center) < LAUNCHER_BAND / 2
        profile[band] += power
    return {"rho": rho.tolist(), "profile": (profile / profile.max()).tolist()}


def impurity_ratios(core_profiles):
    profiles = core_profiles.profiles_1d[0]
    ratios = {}
    for ion in profiles.ion:
        symbol = (
            IMPURITY_SYMBOLS.get(int(ion.element[0].z_n)) if len(ion.element) else None
        )
        if symbol and len(ion.density):
            ratio = float(np.median(ion.density / profiles.electrons.density))
            if ratio > MIN_RATIO:
                ratios[symbol] = ratio
    return ratios


def w_cooling_rate(t_e_kev):
    t_e = np.clip(t_e_kev, 0.1, 100.0)
    coeffs = W_MAVRIN_COEFFS[:, np.searchsorted(W_MAVRIN_INTERVALS, t_e)]
    return 10 ** np.polyval(coeffs, np.log10(t_e))


def w_line_radiation(core_sources):
    return next(
        s.global_quantities[0].power
        for s in core_sources.source
        if s.identifier.index == LINE_RADIATION
        and len(s.species.ion.element)
        and s.species.ion.element[0].z_n == W_Z
    )


def radiation_multiplier(db, times, w_ratio):
    dina = torax = 0.0
    for t in times:
        sources = db.get_slice("core_sources", t, CLOSEST_INTERP, autoconvert=False)
        profiles = db.get_slice(
            "core_profiles", t, CLOSEST_INTERP, autoconvert=False
        ).profiles_1d[0]
        n_e = profiles.electrons.density
        l_w = w_cooling_rate(profiles.electrons.temperature / 1e3)
        dina += w_line_radiation(sources)
        torax += np.trapezoid(l_w * w_ratio * n_e**2, profiles.grid.volume)
    return float(dina / torax)


def main(uri, out_path):
    with imas.DBEntry(uri, "r") as db:
        summary = db.get("summary", autoconvert=False)
        pulse_schedule = db.get("pulse_schedule", autoconvert=False)
        ip = np.abs(summary.global_quantities.ip.value)
        t_flattop = summary.time[np.argmax(ip)]
        core_profiles = db.get_slice(
            "core_profiles", t_flattop, CLOSEST_INTERP, autoconvert=False
        )
        impurities = impurity_ratios(core_profiles)
        flattop = summary.time[ip >= 0.95 * ip.max()]
        times = np.linspace(flattop[0], flattop[-1], N_FLATTOP_SLICES)
        multiplier = (
            radiation_multiplier(db, times, impurities["W"])
            if "W" in impurities
            else 1.0
        )
    params = {
        "ec_deposition": ec_deposition(pulse_schedule),
        "impurities": impurities,
        "radiation_multiplier": multiplier,
    }
    Path(out_path).write_text(json.dumps(params, indent=2))
    print(f"TORAX params: {params | {'ec_deposition': '...'}}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
