"""Exercise the shape toolkit on raw (unpreprocessed) DINA 105084 data.

Reads the DD3 source entry directly (boundary_separatrix, ragged outlines,
empty slices) -- the case the native waveform-editor shape import must handle
to replace preprocess_dina.py.
"""

import sys
from pathlib import Path

import imas
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from shape_toolkit import (
    canonical,
    distances_to_outline,
    fit_shape_params,
    interp_outlines,
    outline_error,
    render_params,
    split_separatrix,
)

URI = "imas:hdf5?path=/work/imas/shared/imasdb/ITER/3/105084/1"
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)


def sep_shape(eq, i):
    """(r, z, x_point) of the separatrix at slice i, or None if empty."""
    bs = eq.time_slice[i].boundary_separatrix
    r, z = np.asarray(bs.outline.r), np.asarray(bs.outline.z)
    if len(r) < 10:
        return None
    xpt = None
    if len(bs.x_point):
        xpt = (float(bs.x_point[0].r), float(bs.x_point[0].z))
    r, z, _legs = split_separatrix(r, z, x_point=xpt)
    return r, z, xpt


def nearest_slice(time, t):
    return int(np.argmin(np.abs(time - t)))


def plot_shape(ax, r, z, **kw):
    ax.plot(np.append(r, r[0]), np.append(z, z[0]), **kw)


def main():
    entry = imas.DBEntry(URI, "r")
    eq = entry.get("equilibrium", lazy=True, autoconvert=False)
    time = np.asarray(eq.time)

    # Exact limited -> diverted transition
    i = nearest_slice(time, 9.0)
    while sep_shape(eq, i) and sep_shape(eq, i)[2] is None:
        i += 1
    i_div = i
    print(f"transition: last limited t={time[i_div-1]:.3f}s, first diverted t={time[i_div]:.3f}s")

    # --- 1. Resampling fidelity (ragged source -> canonical N) ----------------
    r, z, xpt = sep_shape(eq, nearest_slice(time, 100.0))
    print(f"\nresampling fidelity, flat-top slice ({len(r)} source points):")
    for n in (48, 96, 192):
        q = canonical(r, z, n, pin=xpt)
        d = distances_to_outline(q, r, z)
        dx = np.hypot(q[np.argmax(d), 0] - xpt[0], q[np.argmax(d), 1] - xpt[1])
        err = outline_error(q[:, 0], q[:, 1], r, z)
        print(
            f"  N={n:4d}: rms={err['rms']*1e3:6.2f} mm  max={err['max']*1e3:6.2f} mm"
            f"  (worst point {dx:.2f} m from X-point)"
        )

    # --- 2. Interpolation across the limited->diverted transition -------------
    # naive: knots straddle the transition; phase-aware: transition sits on knots
    i_a, i_b = i_div - 12, i_div + 12
    sa, sb = sep_shape(eq, i_a), sep_shape(eq, i_b)
    s_lim, s_dv = sep_shape(eq, i_div - 1), sep_shape(eq, i_div)
    t_a, t_b, t_lim, t_dv = time[i_a], time[i_b], time[i_div - 1], time[i_div]
    fig, axs = plt.subplots(1, 2, figsize=(11, 7))
    print(f"\ntransition interp, knots t={t_a:.2f} / {t_b:.2f}s; transition knots {t_lim:.2f} / {t_dv:.2f}s")
    print("   t [s]   naive rms/max [mm]    phase-aware rms/max [mm]")
    for j in range(i_a + 3, i_b, 3):
        st = sep_shape(eq, j)
        w = (time[j] - t_a) / (t_b - t_a)
        rn_, zn_, _ = interp_outlines(sa, sb, w, n=192)
        if j < i_div:
            wp = (time[j] - t_a) / (t_lim - t_a)
            rp, zp, _ = interp_outlines(sa, s_lim, wp, n=192)
        else:
            wp = (time[j] - t_dv) / (t_b - t_dv)
            rp, zp, _ = interp_outlines(s_dv, sb, wp, n=192)
        e_n = outline_error(rn_, zn_, st[0], st[1])
        e_p = outline_error(rp, zp, st[0], st[1])
        print(
            f"  {time[j]:6.2f}  {e_n['rms']*1e3:7.2f} /{e_n['max']*1e3:7.2f}"
            f"    {e_p['rms']*1e3:7.2f} /{e_p['max']*1e3:7.2f}"
        )
        plot_shape(axs[0], st[0], st[1], color="0.7", lw=3)
        plot_shape(axs[0], rp, zp, lw=1, label=f"t={time[j]:.2f}s")
    plot_shape(axs[0], s_lim[0], s_lim[1], color="C0", ls="--", label="knot (last limited)")
    plot_shape(axs[0], s_dv[0], s_dv[1], color="C3", ls="--", label="knot (first diverted)")
    axs[0].set(title="phase-aware interp (thin) vs DINA truth (gray)", aspect="equal")
    axs[0].legend(fontsize=7)

    # --- 3. Knot-spacing sweep: interp vs closest ------------------------------
    print("\nknot-spacing sweep (evaluated at knot midpoint):")
    print("  phase      dt [s]   interp rms/max [mm]   closest rms/max [mm]")
    rows = []
    for label, t_mid in [("ramp-up", 25.0), ("flat-top", 150.0)]:
        for dt in (2, 5, 10, 20, 40):
            ia, ib = nearest_slice(time, t_mid - dt / 2), nearest_slice(time, t_mid + dt / 2)
            im = nearest_slice(time, (time[ia] + time[ib]) / 2)
            sa_, sb_, st = sep_shape(eq, ia), sep_shape(eq, ib), sep_shape(eq, im)
            w = (time[im] - time[ia]) / (time[ib] - time[ia])
            ri, zi, _ = interp_outlines(sa_, sb_, w, n=192)
            e_int = outline_error(ri, zi, st[0], st[1])
            e_cls = outline_error(sa_[0], sa_[1], st[0], st[1])
            rows.append((label, dt, e_int, e_cls))
            print(
                f"  {label:9s} {dt:5.0f}   {e_int['rms']*1e3:7.2f} /{e_int['max']*1e3:7.2f}"
                f"    {e_cls['rms']*1e3:7.2f} /{e_cls['max']*1e3:7.2f}"
            )

    ax = axs[1]
    for label, marker in [("ramp-up", "o"), ("flat-top", "s")]:
        sel = [x for x in rows if x[0] == label]
        ax.loglog([x[1] for x in sel], [x[2]["max"] * 1e3 for x in sel], f"-{marker}", label=f"{label} interp")
        ax.loglog([x[1] for x in sel], [x[3]["max"] * 1e3 for x in sel], f"--{marker}", label=f"{label} closest")
    ax.set(xlabel="knot spacing [s]", ylabel="max boundary error [mm]", title="interp vs closest")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
    fig.savefig(OUT / "transition_and_sweep.png", dpi=130, bbox_inches="tight")

    # --- 4. Fit shape config onto outlines, view the error --------------------
    fig, axs = plt.subplots(1, 3, figsize=(14, 6))
    print("\nfit shape config onto DINA outlines:")
    for ax, t, lim in [(axs[0], 9.5, True), (axs[1], 100.0, False)]:
        st = sep_shape(eq, nearest_slice(time, t))
        params, err = fit_shape_params(st[0], st[1], x_point=st[2])
        rr, zz, _ = render_params(params)
        plot_shape(ax, st[0], st[1], color="0.6", lw=3, label="DINA")
        plot_shape(ax, rr, zz, color="C1", lw=1.2, label="fitted config")
        ax.set(title=f"t={t:.1f}s  rms={err['rms']*1e3:.0f}mm max={err['max']*1e3:.0f}mm", aspect="equal")
        ax.legend(fontsize=8)
        print(f"  t={t:6.1f}s: " + "  ".join(f"{k}={v:.3f}" for k, v in params.items()))
        print(f"            rms={err['rms']*1e3:.1f} mm  max={err['max']*1e3:.1f} mm")

    # --- 5. Interp between an outline and a shape config ----------------------
    st = sep_shape(eq, nearest_slice(time, 100.0))
    params, _ = fit_shape_params(*sep_shape(eq, nearest_slice(time, 30.0))[:2],
                                 x_point=sep_shape(eq, nearest_slice(time, 30.0))[2])
    cfg = render_params(params)
    for w in (0.0, 0.25, 0.5, 0.75, 1.0):
        ri, zi, _ = interp_outlines(cfg, st, w)
        plot_shape(axs[2], ri, zi, lw=1, color=plt.cm.viridis(w))
    axs[2].set(title="config (t=30 fit) -> outline (t=100)", aspect="equal")
    fig.savefig(OUT / "fit_and_config_interp.png", dpi=130, bbox_inches="tight")

    print(f"\nfigures in {OUT}")


if __name__ == "__main__":
    sys.exit(main())
