"""Compare DINA 105084 shapes over the whole pulse with our parameterized definition.

Per sampled slice: fit the shape config (limited 5-param / diverted 7-param).
Then suggest sparse knots per parameter trace (Ramer-Douglas-Peucker), rebuild
the shape from linearly-interpolated parameters between knots (tier-1 interp),
and measure the boundary error of that sparse "own definition" against DINA.
"""

import json
import sys
from pathlib import Path

import imas
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from demo_dina import URI, nearest_slice, sep_shape
from shape_toolkit import fit_shape_params, outline_error, render_params

OUT = Path(__file__).parent / "out"
PARAM_NAMES = ["a", "center_r", "center_z", "kappa", "delta", "rx", "zx"]


def rdp_indices(t, y, eps):
    """Ramer-Douglas-Peucker on a 1D trace; returns sorted knot indices."""

    def rec(i, j):
        if j <= i + 1:
            return []
        yl = y[i] + (y[j] - y[i]) * (t[i : j + 1] - t[i]) / (t[j] - t[i])
        d = np.abs(y[i : j + 1] - yl)
        k = int(np.argmax(d))
        if d[k] > eps:
            return rec(i, i + k) + [i + k] + rec(i + k, j)
        return []

    return [0] + rec(0, len(t) - 1) + [len(t) - 1]


def main():
    entry = imas.DBEntry(URI, "r")
    eq = entry.get("equilibrium", lazy=True, autoconvert=False)
    time = np.asarray(eq.time)

    # sample times: dense-ish in ramp-up, coarser later; skip invalid early slices
    t_samples = np.concatenate(
        [np.arange(1.0, 12.0, 0.5), np.arange(12.0, time[-1] - 1, 2.0)]
    )
    fits, warm = [], {}
    for t in t_samples:
        i = nearest_slice(time, t)
        ip = eq.time_slice[i].global_quantities.ip
        if not ip.has_value or abs(float(ip)) < 50e3:  # dead/frozen slices
            continue
        s = sep_shape(eq, i)
        if s is None:
            continue
        family = "div" if s[2] is not None else "lim"
        params, err = fit_shape_params(s[0], s[1], x_point=s[2], x0=warm.get(family))
        warm[family] = params
        fits.append({"t": float(time[i]), "i": i, "family": family, "err": err, **params})
    print(f"fitted {len(fits)} slices, t = [{fits[0]['t']:.1f}, {fits[-1]['t']:.1f}] s")
    (OUT / "fits.json").write_text(json.dumps(fits, indent=1))

    # --- knot suggestion per parameter (diverted phase; limited phase is short) ---
    div = [f for f in fits if f["family"] == "div"]
    lim = [f for f in fits if f["family"] == "lim"]
    td = np.array([f["t"] for f in div])
    knots = {}
    print("\nsuggested knots per parameter (RDP, tol = 1% of range or >= 5 mm):")
    for name in PARAM_NAMES:
        y = np.array([f[name] for f in div])
        eps = max(0.01 * (y.max() - y.min()), 0.005)
        knots[name] = rdp_indices(td, y, eps)
        print(f"  {name:9s}: {len(knots[name]):3d} knots")

    # --- rebuild from sparse knots + measure boundary error --------------------
    def params_at(t):
        p = {}
        for name in PARAM_NAMES:
            y = np.array([f[name] for f in div])
            k = knots[name]
            p[name] = float(np.interp(t, td[k], y[k]))
        return p

    rows = []
    for f in div:
        s = sep_shape(eq, f["i"])
        rr, zz, _ = render_params(params_at(f["t"]))
        e_rec = outline_error(rr, zz, s[0], s[1])
        rows.append((f["t"], f["err"]["rms"], e_rec["rms"], e_rec["max"]))
    rows = np.array(rows)
    n_knots = len({(n, int(k)) for n in PARAM_NAMES for k in knots[n]})
    print(f"\nsparse definition: {sum(len(knots[n]) for n in PARAM_NAMES)} knots total")
    print(f"  per-slice fit error (family floor): mean rms {rows[:,1].mean()*1e3:.0f} mm")
    print(f"  sparse-knot reconstruction:         mean rms {rows[:,2].mean()*1e3:.0f} mm,"
          f" worst max {rows[:,3].max()*1e3:.0f} mm")

    # --- figures ----------------------------------------------------------------
    fig, axs = plt.subplots(4, 2, figsize=(13, 12), sharex=True)
    for ax, name in zip(axs.ravel(), PARAM_NAMES):
        y = np.array([f[name] for f in div])
        ax.plot(td, y, "-", lw=0.8, label="fit per slice")
        k = knots[name]
        ax.plot(td[k], y[k], "o-", ms=3, lw=0.8, label=f"{len(k)} knots")
        if lim and name not in ("rx", "zx"):
            ax.plot([f["t"] for f in lim], [f[name] for f in lim], ".", ms=2, color="0.6")
        ax.set_ylabel(name)
        ax.legend(fontsize=7)
    ax = axs.ravel()[-1]
    ax.plot(rows[:, 0], rows[:, 1] * 1e3, label="fit floor (rms)")
    ax.plot(rows[:, 0], rows[:, 2] * 1e3, label="sparse knots (rms)")
    ax.plot(rows[:, 0], rows[:, 3] * 1e3, ":", label="sparse knots (max)")
    ax.set(ylabel="boundary error [mm]", xlabel="t [s]")
    ax.legend(fontsize=7)
    for ax in axs[-1]:
        ax.set_xlabel("t [s]")
    fig.suptitle("DINA 105084 vs parameterized shape definition")
    fig.savefig(OUT / "dina_vs_own_definition.png", dpi=130, bbox_inches="tight")
    print(f"\nfigure: {OUT / 'dina_vs_own_definition.png'}")


if __name__ == "__main__":
    sys.exit(main())
