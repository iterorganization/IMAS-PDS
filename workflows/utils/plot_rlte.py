"""Compare normalized temperature gradients R/LTe between DINA input and TORAX output.

R/LTe = -(R0/Te) dTe/dr with r = rho_tor_norm * a_minor (midplane-averaged minor
radius approximation; TORAX itself uses r_mid = (R_out - R_in)/2, which differs
by O(Shafranov shift) near the edge). Reads the inverse_convergence data dirs:
<scenarios>/<shot>/tmp/data/<shot>_in (DINA) and <shot>_out_torax (TORAX).

Usage:
    python plot_rlte.py <shot> [extra_out_suffix ...]

Extra suffixes plot additional TORAX variants, e.g.:
    python plot_rlte.py 105073 out_torax_clip_test out_torax_bgb_test

Writes <scenarios>/<shot>/tmp/pds_rlte_<shot>.png with two panels:
left R/LTe(rho) at a few times, right R/LTe at rho=0.6 vs time.
"""

import os
import sys
from pathlib import Path

import imas
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PDS_REPO = os.environ.get("PDS_REPO", str(Path(__file__).resolve().parents[2]))
SCEN = os.environ.get("SCENARIOS_REPO", str(Path(PDS_REPO).parent / "pds-scenarios"))


def load_rlte(path):
    """Return times, list of rho arrays, list of R/LTe arrays for one data dir."""
    with imas.DBEntry(f"imas:hdf5?path={path}", "r") as entry:
        cp = entry.get("core_profiles")
        eq = entry.get("equilibrium")
    teq = np.asarray(eq.time)
    R0 = np.array([ts.boundary.geometric_axis.r for ts in eq.time_slice])
    a = np.array([ts.boundary.minor_radius for ts in eq.time_slice])
    times, rhos, rltes = [], [], []
    for i, p in enumerate(cp.profiles_1d):
        te = np.asarray(p.electrons.temperature)
        if len(te) == 0:
            continue
        rho = np.asarray(p.grid.rho_tor_norm)
        j = np.argmin(abs(teq - cp.time[i]))
        r = rho * a[j]
        times.append(float(cp.time[i]))
        rhos.append(rho)
        rltes.append(-R0[j] * np.gradient(te, r) / te)
    return np.array(times), rhos, rltes


def main():
    shot = sys.argv[1] if len(sys.argv) > 1 else "105073"
    variants = [("in", "DINA"), ("out_torax", "TORAX")]
    variants += [(s, s.replace("out_torax_", "TORAX ")) for s in sys.argv[2:]]

    data = {}
    for suffix, label in variants:
        try:
            data[label] = load_rlte(f"{SCEN}/{shot}/data/{suffix}")
        except Exception as exc:
            print(f"skipping {shot}_{suffix}: {exc}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    ref_times = data["DINA"][0]
    plot_times = np.percentile(ref_times, [40, 60, 80])
    for label, (t, rhos, rltes) in data.items():
        for k, tt in enumerate(plot_times):
            i = np.argmin(abs(t - tt))
            ax1.plot(
                rhos[i],
                rltes[i],
                alpha=0.4 + 0.3 * k,
                color=f"C{list(data).index(label)}",
                label=f"{label} t={t[i]:.0f}s" if k == 2 else None,
            )
        ax2.plot(
            t, [np.interp(0.6, rhos[i], rltes[i]) for i in range(len(t))], label=label
        )
    ax1.axhline(16, color="k", ls=":", lw=1, label="QLKNN training max")
    ax1.set(
        xlabel=r"$\rho_{tor,norm}$",
        ylabel=r"$R/L_{Te}$",
        ylim=(0, 40),
        title=f"{shot}: profiles",
    )
    ax2.axhline(16, color="k", ls=":", lw=1)
    ax2.set(
        xlabel="time [s]",
        ylabel=r"$R/L_{Te}$ at $\rho=0.6$",
        title=f"{shot}: mid-radius evolution",
    )
    ax1.legend(fontsize=8)
    ax2.legend(fontsize=8)
    fig.tight_layout()
    out = f"pds_rlte_{shot}.png"
    fig.savefig(out, dpi=140)
    print("wrote", out)


if __name__ == "__main__":
    main()
