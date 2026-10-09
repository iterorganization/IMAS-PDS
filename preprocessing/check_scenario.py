#!/usr/bin/env python3
"""Check that a prepared scenario's preparation produced what is expected.

Compares the raw DINA entry named by <scenario>/source.env against the prepared
IMAS entry in <scenario>/data/in: number/monotonicity of prepared time slices,
prepared window vs viable raw window, (optionally) how prepared slices and the
TORAX fixed time step line up with a PDS case's loop window, and the flattop of
the raw plasma current. Prints OK/WARN lines to stdout, writes one PNG figure.

The scenario directory is $SCENARIOS_REPO/<scenario>, with SCENARIOS_REPO
defaulting to <PDS repo>/scenarios; $TOOLS in source.env expands to this
preprocessing/ directory.

Requires imas-python; run under the SDCC module environment, e.g.:
    module load IMAS-MUSCLE3/1.0.0-intel-2025b-pds
    preprocessing/check_scenario.py 105033 --case cases/inverse_convergence_105033
"""

import os

os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")

import argparse
import itertools
import math
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import imas
import matplotlib.pyplot as plt
import numpy as np

SETTINGS_FILES = ("workflow_settings.ymmsl", "scenario_settings.ymmsl")
SETTINGS_KEYS = (
    "loop.t_min",
    "loop.t_max",
    "transport.torax.fixed_dt",
    "torax.fixed_dt",
    "torax.t_final",
    "source.t_min",
    "source.t_max",
    "nice_evo_rd.t_end",
)


def parse_source_env(path, tools_dir):
    """Simple shell-style KEY="value" parser with $VAR expansion."""
    values = {"TOOLS": str(tools_dir)}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.split(" #", 1)[0].rstrip()
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        val = re.sub(
            r"\$([A-Za-z_][A-Za-z0-9_]*)",
            lambda mm: values.get(mm.group(1), mm.group(0)),
            val,
        )
        values[key] = val
    return values


def parse_case_settings(case_dir):
    """Tiny regex scan of the `settings:` block of workflow/scenario ymmsl files."""
    result = {}
    for fname in SETTINGS_FILES:
        path = Path(case_dir) / fname
        if not path.is_file():
            continue
        in_settings = False
        for raw_line in path.read_text().splitlines():
            if raw_line and not raw_line[0].isspace():
                in_settings = raw_line.strip().rstrip(":") == "settings"
                continue
            if not in_settings:
                continue
            stripped = raw_line.strip()
            for key in SETTINGS_KEYS:
                m = re.match(r"^" + re.escape(key) + r":\s*(.+?)\s*(#.*)?$", stripped)
                if m:
                    val = m.group(1).strip().strip("\"'")
                    result[key] = val
    return result


def first_float(settings, keys):
    for key in keys:
        if key in settings:
            try:
                return float(settings[key])
            except ValueError:
                pass
    return None


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "scenario",
        help="scenario directory name under $SCENARIOS_REPO, e.g. 105033",
    )
    parser.add_argument(
        "--case",
        dest="case_dir",
        help="PDS case folder to read loop.t_min/t_max/dt from",
    )
    parser.add_argument("--t-min", type=float, default=None)
    parser.add_argument("--t-max", type=float, default=None)
    parser.add_argument("--dt", type=float, default=None)
    parser.add_argument(
        "--out",
        default=None,
        help="output PNG path (default: <scenario>/check_<scenario>.png)",
    )
    args = parser.parse_args()

    tools_dir = Path(__file__).resolve().parent
    root = Path(os.environ.get("SCENARIOS_REPO") or tools_dir.parent / "scenarios")
    scenario_dir = root / args.scenario
    env = parse_source_env(scenario_dir / "source.env", tools_dir)

    settings = parse_case_settings(args.case_dir) if args.case_dir else {}
    t_min = (
        args.t_min
        if args.t_min is not None
        else first_float(settings, ["loop.t_min", "source.t_min"])
    )
    t_max = (
        args.t_max
        if args.t_max is not None
        else first_float(
            settings,
            ["loop.t_max", "torax.t_final", "source.t_max", "nice_evo_rd.t_end"],
        )
    )
    dt = (
        args.dt
        if args.dt is not None
        else first_float(settings, ["transport.torax.fixed_dt", "torax.fixed_dt"])
    )

    raw_uri = env.get("SUMMARY_URI") or env.get("SOURCE_URI")
    with imas.DBEntry(raw_uri, "r") as db:
        sm = db.get("summary", autoconvert=False)
    t_raw = np.array(sm.time)
    ip_raw = np.array(sm.global_quantities.ip.value)
    R = np.array(sm.boundary.magnetic_axis_r.value)
    viable = (R > 1) & (np.abs(ip_raw) > 50e3)

    t_sel, ip_sel = None, None
    prepared_uri = f"imas:hdf5?path={scenario_dir}/data/in"
    try:
        with imas.DBEntry(prepared_uri, "r") as db:
            eq = db.get("equilibrium", lazy=True)
            t_sel = np.array(eq.time)
            ip_sel = np.array(
                [
                    float(eq.time_slice[i].global_quantities.ip)
                    for i in range(len(t_sel))
                ]
            )
    except Exception as exc:
        print(f"WARN: could not read prepared equilibrium from {prepared_uri}: {exc}")

    in_md_dir = scenario_dir / "data" / "in_md"
    if in_md_dir.is_dir():
        md_files = sorted(
            f.name for f in in_md_dir.glob("*.h5") if f.name != "master.h5"
        )
        print(
            f"OK machine-description files in data/in_md: {len(md_files)} ({', '.join(md_files)})"
        )
    else:
        print(f"WARN: data/in_md not found at {in_md_dir}")

    n_expected = env.get("N_TIMESLICES")
    n_expected = int(n_expected) if n_expected is not None else None
    dt_step = env.get("DT_STEP")
    try:
        dt_step = float(dt_step) if dt_step is not None else None
    except ValueError:
        print(f"WARN DT_STEP={dt_step!r} in source.env is not a number")
        dt_step = None
    if t_sel is not None:
        n_prepared = len(t_sel)
        if dt_step is not None and dt_step > 0 and viable.any():
            # One target every DT_STEP over the viable range; nearest-sample mapping,
            # deduplication and skipped slices make the count only approximate.
            span = float(t_raw[viable][-1] - t_raw[viable][0])
            n_approx = math.floor(span / dt_step + 1e-9) + 1
            tol = max(2, int(0.1 * n_approx))
            status = "OK" if abs(n_prepared - n_approx) <= tol else "WARN"
            print(
                f"{status} prepared slices: {n_prepared} (DT_STEP={dt_step:g} s,"
                f" expected ~{n_approx} = viable range {span:.3f} s / dt + 1)"
            )
        elif dt_step is not None:
            print(
                f"WARN prepared slices: {n_prepared} (DT_STEP={dt_step} s, no expected"
                " count: no viable raw sample or DT_STEP <= 0)"
            )
        else:
            status = (
                "OK" if (n_expected is None or n_prepared == n_expected) else "WARN"
            )
            print(f"{status} prepared slices: {n_prepared} (N_TIMESLICES={n_expected})")
        if n_prepared > 1:
            diffs = np.diff(t_sel)
            bad = np.where(diffs <= 0)[0]
            if len(bad) == 0:
                print(
                    f"OK prepared time array strictly monotonic ({n_prepared} slices)"
                )
            else:
                desc = ", ".join(
                    f"t[{i}]={t_sel[i]:.4f}->t[{i + 1}]={t_sel[i + 1]:.4f}"
                    for i in bad[:5]
                )
                print(
                    f"WARN prepared time array not strictly monotonic: {len(bad)} violation(s): {desc}"
                )
        if viable.any():
            v0, v1 = t_raw[viable][0], t_raw[viable][-1]
            p0, p1 = t_sel[0], t_sel[-1]
            status = "OK" if (p0 >= v0 - 1e-6 and p1 <= v1 + 1e-6) else "WARN"
            print(
                f"{status} prepared window [{p0:.3f}, {p1:.3f}] s vs viable raw window [{v0:.3f}, {v1:.3f}] s"
            )
        else:
            print("WARN no viable raw samples found (R>1 and |Ip|>50kA)")
        if t_min is not None and t_max is not None:
            in_window = t_sel[(t_sel >= t_min) & (t_sel <= t_max)]
            print(
                f"OK {len(in_window)} prepared slices fall inside loop window [{t_min:.3f}, {t_max:.3f}] s"
            )
            if len(in_window) > 1:
                intervals = np.diff(in_window)
                print(
                    f"OK slice interval in window: min={intervals.min():.4f} s, max={intervals.max():.4f} s"
                )
                if dt:
                    n_steps = int(sum(math.ceil(round(iv / dt, 9)) for iv in intervals))
                    print(
                        f"OK TORAX fixed steps between in-window slices (dt={dt:g} s): {n_steps}"
                    )
    else:
        n_prepared = 0

    flat = np.array([], dtype=int)
    if len(ip_raw):
        ip_abs = np.abs(ip_raw)
        peak = ip_abs.max()
        peak_t = t_raw[np.argmax(ip_abs)]
        flat = np.where(ip_abs > 0.95 * peak)[0]
        if len(flat):
            print(
                f"OK flattop |Ip|>95%: [{t_raw[flat[0]]:.3f}, {t_raw[flat[-1]]:.3f}] s; "
                f"peak {peak / 1e6:.3f} MA at t={peak_t:.3f} s"
            )

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(11, 7),
        dpi=130,
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    ax1.plot(t_raw, ip_raw / 1e6, color="#1f77b4", lw=1.2, label="DINA raw Ip")
    if viable.any():
        ax1.axvspan(
            t_raw[viable][0],
            t_raw[viable][-1],
            color="#1f77b4",
            alpha=0.08,
            label="viable raw range",
        )
    if t_sel is not None and ip_sel is not None and n_prepared:
        ax1.plot(
            t_sel,
            ip_sel / 1e6,
            "o",
            ms=4,
            color="#d62728",
            label="prepared slices (data/in)",
        )
    if t_min is not None:
        ax1.axvline(t_min, color="black", ls="--", lw=1, label="t_min/t_max")
    if t_max is not None:
        ax1.axvline(t_max, color="black", ls="--", lw=1)
    if t_min is not None and t_max is not None:
        ax1.axvspan(t_min, t_max, color="grey", alpha=0.08, label="loop window")
    if len(flat):
        for label, i in (("flattop start", 0), ("flattop end", -1)):
            ax1.annotate(
                label,
                (t_raw[flat[i]], ip_abs[flat[i]] / 1e6),
                fontsize=7,
                xytext=(4, 6),
                textcoords="offset points",
            )
    ax1.set_ylabel("Ip [MA]")
    ax1.grid(alpha=0.3)
    ax1.legend(loc="best", fontsize=8)

    n_ticks = 0
    capped = False
    if t_sel is not None and n_prepared:
        ax2.vlines(t_sel, 0, 1, color="#d62728", lw=1.2)
        n_ticks += n_prepared
    if dt and t_min is not None and t_max is not None and t_sel is not None:
        in_window = t_sel[(t_sel >= t_min) & (t_sel <= t_max)]
        step_ticks = []
        for a, b in itertools.pairwise(in_window):
            n_steps = max(1, math.ceil(round((b - a) / dt, 9)))
            step_ticks.extend(a + k * dt for k in range(1, n_steps))
        if n_ticks + len(step_ticks) > 5000:
            step_ticks = step_ticks[: max(0, 5000 - n_ticks)]
            capped = True
        if step_ticks:
            ax2.vlines(step_ticks, 0, 0.4, color="#7f7f7f", lw=0.6)
        n_ticks += len(step_ticks)
    if capped:
        print("NOTE: TORAX step ticks capped at 5000 in the figure")
    ax2.set_ylim(0, 1.15)
    ax2.set_yticks([])
    ax2.set_ylabel("slices / TORAX steps")
    ax2.set_xlabel("t [s]")
    ax2.grid(alpha=0.3, axis="x")

    bits = []
    if t_sel is not None:
        bits.append(f"{n_prepared} prepared slices")
    if t_min is not None and t_max is not None:
        bits.append(f"window [{t_min:.3g}, {t_max:.3g}]")
    if dt:
        bits.append(f"dt={dt:g}")
    title = args.scenario + (": " + ", ".join(bits) if bits else "")
    fig.suptitle(title)
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    out_path = (
        Path(args.out) if args.out else scenario_dir / f"check_{args.scenario}.png"
    )
    fig.savefig(out_path)
    print(f"Figure saved to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
