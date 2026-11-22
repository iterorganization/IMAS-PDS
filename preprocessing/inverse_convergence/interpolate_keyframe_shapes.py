"""Interpolate a few designed plasma shapes (keyframes) onto the export times of a run.

A keyframe entry holds a handful of equilibrium slices (for example the NICE inverse
equilibria of the Waveform-Editor shape editor at 6 times of a pulse). The
inverse_convergence workflow, however, exports its target at every input slice time, and
the waveform editor can only pick the closest keyframe outline (outlines have different
point counts, so `interp: linear` is not available for them). This script writes a new
entry with one equilibrium slice per output time, so that `closest` hands NICE the exact
interpolated shape at every export time.

Method
------
Per output time t, the slice contains:

- ``global_quantities.ip``, ``global_quantities.psi_boundary`` (also written to
  ``boundary.psi``) and ``vacuum_toroidal_field.b0`` (and ``r0`` if the keyframes have
  it): linear in time between the two surrounding keyframes, whatever their topology
  (the same as the waveform editor's ``interp: linear``).
- ``boundary.outline.r/z``: interpolation in polar coordinates about a fixed centre
  (R_c, Z_c) common to all frames. Every keyframe outline must be star-shaped about the
  centre (the polar angle of its vertices strictly monotonic over one turn, so that the
  radius r(theta) is single-valued); the script stops otherwise. Each keyframe is
  sampled on a common set of rays: ``n_rays`` equally spaced angles plus, for each
  diverted keyframe, the angle of its X-point, so that every keyframe X-point corner is
  kept exactly. r(theta) on a ray is the exact intersection of the ray with the keyframe
  polygon (no smoothing). Between two keyframes of the same topology, r(theta) is linear
  in time on every ray. This is linear interpolation of gap-like distances measured along
  fixed rays, as references made of linear segments between vertices are interpolated.
- Topology change (limiter -> diverted or back) between two keyframes: no blending. The
  outline steps at the given switch time (for 105073, the DINA X-point formation at
  10.918 s): the earlier keyframe before it, the later keyframe from it on.
- Before the first and after the last keyframe, every quantity holds the end keyframe.
- ``boundary.type`` is set to the topology used (0 limiter, 1 diverted).

Nothing else is done: no smoothing, no clamps, no pf_active (the coil currents of the
keyframes are not written; NICE computes its own).

The output outline is closed (first point repeated at the end) and runs in the same
direction as the keyframe outlines. The X-point of a diverted keyframe is taken as its
outline vertex of minimum Z (lower single null); the script prints it next to the
``contour_tree`` nodes for a cross-check, and reports, for every interpolated output
time, the distance between the interpolated outline's lowest vertex and the linear
interpolation of the two keyframe X-points.

Keyframe topology is read from ``boundary.type`` (0 limiter, 1 diverted) or, when that is
unset (as in the shape-editor entries), from ``--topology``.

usage:
  interpolate_keyframe_shapes.py <keyframe-uri> <out-uri>
      (--times T1,T2,... | --times-from <uri> [--times-from <uri> ...])
      [--t-min T] [--t-max T]
      [--topology limiter,limiter,diverted,...] [--switch-times 10.918,...]
      [--centre 6.2,0.5] [--n-rays 512]

Output times for inverse_convergence. The waveform editor exports on the /time of the
equilibrium the loop sends it (waveform_editor/muscle3.py, overlay mode). On iteration 0
that is the input (DINA) slice times within loop.t_min / loop.t_max
(workflows/lib/actors/outer_convergence_loop.py:181-188); from iteration 1 on it is the
TORAX output slice closest to each of them (_split + _hold_boundary keep the TORAX slice
time, lines 241-253), i.e. TORAX's fixed_dt grid, up to dt/2 away. Give both sets, e.g.
the DINA input and the out_nice entry of an earlier run of the same case and TORAX
settings, so that `closest` finds the exact interpolated shape on every iteration
(105073, two runs' worth of times):

  python interpolate_keyframe_shapes.py \\
      "imas:hdf5?path=/home/ITER/schneim/public/shape_editor_105073/imas_6slices" \\
      "imas:hdf5?path=cases/inverse_convergence_105073_shapes6/shapes_interp_imas" \\
      --times-from "imas:hdf5?path=cases/inverse_convergence_105073/preprocess/in" \\
      --times-from "imas:hdf5?path=cases/runs/<earlier run>/out_nice" \\
      --t-min 10 --t-max 143 \\
      --topology limiter,limiter,limiter,diverted,diverted,diverted \\
      --switch-times 10.918
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np

LIMITER, DIVERTED = 0, 1
TOPOLOGY_NAMES = {"limiter": LIMITER, "diverted": DIVERTED}


@dataclass
class Keyframe:
    """One designed shape: time, topology, closed outline and global quantities."""

    time: float
    topology: int
    r: np.ndarray
    z: np.ndarray
    ip: float
    psi_boundary: float
    b0: float
    r0: float | None = None


# --- geometry ------------------------------------------------------------------------


def _open_polygon(r, z):
    """Drop the repeated closing point, if any."""
    r, z = np.asarray(r, float), np.asarray(z, float)
    if r[0] == r[-1] and z[0] == z[-1]:
        return r[:-1], z[:-1]
    return r, z


def polar_angles(r, z, centre):
    """Unwrapped polar angles of the open polygon's vertices about `centre`."""
    rc, zc = centre
    return np.unwrap(np.arctan2(z - zc, r - rc))


def star_shape_check(r, z, centre):
    """Return (ok, orientation) for a closed outline about `centre`.

    ok: the polar angle is strictly monotonic along the outline and turns exactly once,
    so every ray from the centre crosses the outline exactly once. orientation: +1 for
    increasing angle (counter-clockwise in the R-Z plane), -1 otherwise.
    """
    ro, zo = _open_polygon(r, z)
    ang = polar_angles(np.append(ro, ro[0]), np.append(zo, zo[0]), centre)
    d = np.diff(ang)
    orientation = 1 if d.sum() > 0 else -1
    ok = bool(np.all(d * orientation > 0) and abs(abs(d.sum()) - 2 * np.pi) < 1e-9)
    return ok, orientation


def xpoint_of(r, z):
    """X-point of a lower-single-null outline: its vertex of minimum Z."""
    i = int(np.argmin(z))
    return float(r[i]), float(z[i])


def sample_on_rays(r, z, centre, thetas):
    """Radius at which each ray (angle in `thetas`) from `centre` crosses the outline.

    The crossing is the exact intersection of the ray with the polygon segment whose
    angular span contains the ray. The outline must pass `star_shape_check`.
    """
    ok, orientation = star_shape_check(r, z, centre)
    if not ok:
        raise ValueError(f"outline is not star-shaped about {centre}")
    ro, zo = _open_polygon(r, z)
    if orientation < 0:
        ro, zo = ro[::-1], zo[::-1]
    rc, zc = centre
    rr, zz = np.append(ro, ro[0]), np.append(zo, zo[0])
    ang = polar_angles(rr, zz, centre)  # increasing, spans exactly 2 pi
    th = ang[0] + np.mod(np.asarray(thetas, float) - ang[0], 2 * np.pi)
    k = np.clip(np.searchsorted(ang, th, side="right") - 1, 0, len(ang) - 2)
    # ray C + s (cos th, sin th) = P_k + u (P_k+1 - P_k)
    dx, dz = np.cos(th), np.sin(th)
    px, pz = rr[k] - rc, zz[k] - zc
    ex, ez = rr[k + 1] - rr[k], zz[k + 1] - zz[k]
    den = dx * ez - dz * ex
    s = (px * ez - pz * ex) / den
    return s


def ray_grid(keyframes, centre, n_rays):
    """n_rays equally spaced angles in [-pi, pi) plus each diverted keyframe's X-point
    angle, sorted, duplicates removed."""
    base = -np.pi + 2 * np.pi * np.arange(n_rays) / n_rays
    extra = []
    for kf in keyframes:
        if kf.topology == DIVERTED:
            xr, xz = xpoint_of(*_open_polygon(kf.r, kf.z))
            extra.append(np.arctan2(xz - centre[1], xr - centre[0]))
    thetas = np.unique(np.concatenate([base, np.asarray(extra, float)]))
    return thetas


# --- time interpolation --------------------------------------------------------------


def _bracket(times, t):
    """(k, w): t lies in [times[k], times[k+1]] with weight w of times[k+1]; ends hold."""
    if t <= times[0]:
        return 0, 0.0
    if t >= times[-1]:
        return len(times) - 2, 1.0
    k = int(np.searchsorted(times, t, side="right") - 1)
    return k, (t - times[k]) / (times[k + 1] - times[k])


def _switch_time(keyframes, k, switch_times):
    """Switch time of the topology change between keyframes k and k+1."""
    n_change = sum(
        keyframes[j].topology != keyframes[j + 1].topology for j in range(k + 1)
    )
    ts = switch_times[n_change - 1]
    if not keyframes[k].time < ts < keyframes[k + 1].time:
        raise ValueError(
            f"switch time {ts} is not between keyframes "
            f"{keyframes[k].time} and {keyframes[k + 1].time}"
        )
    return ts


class KeyframeInterpolator:
    """Interpolate keyframes in time as described in the module docstring."""

    def __init__(self, keyframes, centre=(6.2, 0.5), n_rays=512, switch_times=()):
        self.keyframes = sorted(keyframes, key=lambda kf: kf.time)
        self.times = np.array([kf.time for kf in self.keyframes])
        if len(self.keyframes) < 2:
            raise ValueError("need at least two keyframes")
        self.centre = tuple(float(c) for c in centre)
        n_change = sum(
            a.topology != b.topology
            for a, b in zip(self.keyframes, self.keyframes[1:], strict=False)
        )
        if len(switch_times) != n_change:
            raise ValueError(
                f"{n_change} topology change(s) between keyframes but "
                f"{len(switch_times)} switch time(s) given"
            )
        self.switch_times = [float(t) for t in switch_times]
        for k in range(len(self.keyframes) - 1):
            if self.keyframes[k].topology != self.keyframes[k + 1].topology:
                _switch_time(self.keyframes, k, self.switch_times)  # checks position
        self.orientation = []
        for kf in self.keyframes:
            ok, orient = star_shape_check(kf.r, kf.z, self.centre)
            if not ok:
                raise ValueError(
                    f"keyframe t={kf.time} is not star-shaped about {self.centre}"
                )
            self.orientation.append(orient)
        if len(set(self.orientation)) != 1:
            raise ValueError("keyframe outlines run in different directions")
        self.thetas = ray_grid(self.keyframes, self.centre, n_rays)
        self.radii = np.array(
            [
                sample_on_rays(kf.r, kf.z, self.centre, self.thetas)
                for kf in self.keyframes
            ]
        )

    def scalars(self, t):
        """Linear-in-time ip, psi_boundary, b0, r0 (None if a keyframe lacks it)."""
        out = {}
        for name in ("ip", "psi_boundary", "b0", "r0"):
            vals = [getattr(kf, name) for kf in self.keyframes]
            out[name] = (
                None
                if any(v is None for v in vals)
                else float(np.interp(t, self.times, vals))
            )
        return out

    def radius(self, t):
        """(r(theta) on self.thetas, topology) at time t."""
        k, w = _bracket(self.times, t)
        a, b = self.keyframes[k], self.keyframes[k + 1]
        if a.topology != b.topology and 0.0 < w < 1.0:
            ts = _switch_time(self.keyframes, k, self.switch_times)
            j = k if t < ts else k + 1
            return self.radii[j].copy(), self.keyframes[j].topology
        if w == 0.0:
            return self.radii[k].copy(), a.topology
        if w == 1.0:
            return self.radii[k + 1].copy(), b.topology
        return (1 - w) * self.radii[k] + w * self.radii[k + 1], a.topology

    def outline(self, t):
        """(r, z, topology) of the closed outline at time t, keyframe direction."""
        rad, topo = self.radius(t)
        rr = self.centre[0] + rad * np.cos(self.thetas)
        zz = self.centre[1] + rad * np.sin(self.thetas)
        if self.orientation[0] < 0:
            rr, zz = rr[::-1], zz[::-1]
        return np.append(rr, rr[0]), np.append(zz, zz[0]), topo

    def xpoint_error(self, t):
        """For a diverted interpolated time between two diverted keyframes: distance (m)
        between the outline's lowest vertex and the linear interpolation of the two
        keyframe X-points, and both points. None otherwise."""
        k, w = _bracket(self.times, t)
        a, b = self.keyframes[k], self.keyframes[k + 1]
        if not (0.0 < w < 1.0 and a.topology == b.topology == DIVERTED):
            return None
        xa = np.array(xpoint_of(*_open_polygon(a.r, a.z)))
        xb = np.array(xpoint_of(*_open_polygon(b.r, b.z)))
        lin = (1 - w) * xa + w * xb
        r, z, _ = self.outline(t)
        got = np.array(xpoint_of(r[:-1], z[:-1]))
        return float(np.hypot(*(got - lin))), got, lin


def corner_angle_deg(r, z, arc=0.2):
    """Angle (degrees) at the lowest vertex of a closed outline between the chords to
    the outline points `arc` metres away along the outline on either side (a diagnostic
    of how sharp the X-point corner is, independent of the vertex spacing)."""
    ro, zo = _open_polygon(r, z)
    i = int(np.argmin(zo))
    ro, zo = np.roll(ro, -i), np.roll(zo, -i)
    rr, zz = np.append(ro, ro[0]), np.append(zo, zo[0])
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(rr), np.diff(zz)))])
    p = np.array([rr[0], zz[0]])
    a = np.array([np.interp(arc, s, rr), np.interp(arc, s, zz)]) - p
    b = np.array([np.interp(s[-1] - arc, s, rr), np.interp(s[-1] - arc, s, zz)]) - p
    c = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


# --- IMAS I/O ------------------------------------------------------------------------


def read_keyframes(uri, topology=None):
    """Keyframes from an equilibrium IDS (homogeneous time)."""
    import imas

    with imas.DBEntry(uri, "r") as db:
        eq = db.get("equilibrium", autoconvert=False)
    times = np.asarray(eq.time, float)
    b0 = np.asarray(eq.vacuum_toroidal_field.b0, float)
    r0 = (
        float(eq.vacuum_toroidal_field.r0)
        if eq.vacuum_toroidal_field.r0.has_value
        else None
    )
    kfs = []
    for i, ts in enumerate(eq.time_slice):
        if topology is not None:
            topo = topology[i]
        elif ts.boundary.type.has_value and int(ts.boundary.type) in (0, 1):
            topo = int(ts.boundary.type)
        else:
            raise ValueError(
                f"keyframe {i}: boundary.type unset, give --topology for every keyframe"
            )
        kfs.append(
            Keyframe(
                time=float(times[i]),
                topology=topo,
                r=np.asarray(ts.boundary.outline.r, float),
                z=np.asarray(ts.boundary.outline.z, float),
                ip=float(ts.global_quantities.ip),
                psi_boundary=float(ts.global_quantities.psi_boundary),
                b0=float(b0[i]),
                r0=r0,
            )
        )
        nodes = [
            (round(float(n.r), 3), round(float(n.z), 3)) for n in ts.contour_tree.node
        ]
        xp = xpoint_of(*_open_polygon(kfs[-1].r, kfs[-1].z))
        print(
            f"keyframe t={times[i]:.4f} {'diverted' if topo else 'limiter'}: "
            f"{len(kfs[-1].r)} points, lowest vertex ({xp[0]:.3f}, {xp[1]:.3f}), "
            f"contour_tree nodes {nodes}"
        )
    return kfs, eq.ids_properties.version_put.data_dictionary.value


def output_times(args):
    """Output times from --times, or the union of the equilibrium /time of every
    --times-from entry; then cut to [--t-min, --t-max]."""
    if args.times:
        times = np.array([float(t) for t in args.times.split(",")])
    else:
        import imas

        parts = []
        for uri in args.times_from:
            with imas.DBEntry(uri, "r") as db:
                parts.append(np.asarray(db.get("equilibrium", lazy=True).time, float))
        times = np.unique(np.concatenate(parts))
    if args.t_min is not None:
        times = times[times >= args.t_min]
    if args.t_max is not None:
        times = times[times <= args.t_max]
    return times


def write_entry(uri, interp, times, dd_version):
    """Write the interpolated equilibrium (homogeneous time) to `uri`."""
    import imas
    from imas.ids_defs import IDS_TIME_MODE_HOMOGENEOUS

    eq = imas.IDSFactory(dd_version).new("equilibrium")
    eq.ids_properties.homogeneous_time = IDS_TIME_MODE_HOMOGENEOUS
    eq.ids_properties.comment = (
        "Keyframe shapes interpolated by "
        "preprocessing/inverse_convergence/interpolate_keyframe_shapes.py "
        f"(centre {interp.centre}, {len(interp.thetas)} rays, keyframes "
        f"{', '.join(f'{t:.4f}' for t in interp.times)}, switch times "
        f"{interp.switch_times})"
    )
    eq.time = np.asarray(times, float)
    eq.time_slice.resize(len(times))
    b0 = []
    r0 = None
    for ts, t in zip(eq.time_slice, times, strict=True):
        sc = interp.scalars(t)
        r, z, topo = interp.outline(t)
        ts.time = float(t)
        ts.boundary.type = topo
        ts.boundary.outline.r = r
        ts.boundary.outline.z = z
        ts.boundary.psi = sc["psi_boundary"]
        ts.global_quantities.ip = sc["ip"]
        ts.global_quantities.psi_boundary = sc["psi_boundary"]
        b0.append(sc["b0"])
        r0 = sc["r0"]
    eq.vacuum_toroidal_field.b0 = np.asarray(b0)
    if r0 is not None:
        eq.vacuum_toroidal_field.r0 = r0
    with imas.DBEntry(uri, "w", dd_version=dd_version) as db:
        db.put(eq)


def report(interp, times):
    """Print the per-time diagnostics (topology, Ip, X-point error, corner angle)."""
    for kf in interp.keyframes:
        if kf.topology == DIVERTED:
            print(
                f"keyframe t={kf.time:.4f}: corner angle at the X-point "
                f"{corner_angle_deg(kf.r, kf.z):.1f} deg (input outline), "
                f"{corner_angle_deg(*interp.outline(kf.time)[:2]):.1f} deg (resampled)"
            )
    for t in times:
        sc = interp.scalars(t)
        r, z, topo = interp.outline(t)
        line = (
            f"t={t:9.4f} {'diverted' if topo else 'limiter '} "
            f"ip={sc['ip'] / 1e6:8.3f} MA psi_b={sc['psi_boundary']:8.3f} Wb"
        )
        xe = interp.xpoint_error(t)
        if xe is not None:
            line += (
                f" X-point err {xe[0] * 100:5.2f} cm (got {xe[1][0]:.3f},{xe[1][1]:.3f}"
                f" lin {xe[2][0]:.3f},{xe[2][1]:.3f}) corner {corner_angle_deg(r, z):.1f} deg"
            )
        print(line)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("keyframe_uri")
    p.add_argument("out_uri")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--times", help="comma-separated output times [s]")
    g.add_argument(
        "--times-from",
        action="append",
        help="IMAS URI whose equilibrium /time is used (repeatable: union)",
    )
    p.add_argument("--t-min", type=float)
    p.add_argument("--t-max", type=float)
    p.add_argument("--topology", help="comma-separated limiter/diverted per keyframe")
    p.add_argument("--switch-times", default="", help="one per topology change [s]")
    p.add_argument("--centre", default="6.2,0.5", help="R_c,Z_c [m]")
    p.add_argument("--n-rays", type=int, default=512)
    args = p.parse_args(argv)

    topology = (
        [TOPOLOGY_NAMES[s.strip()] for s in args.topology.split(",")]
        if args.topology
        else None
    )
    kfs, dd_version = read_keyframes(args.keyframe_uri, topology)
    switch = [float(s) for s in args.switch_times.split(",") if s.strip()]
    centre = tuple(float(c) for c in args.centre.split(","))
    interp = KeyframeInterpolator(kfs, centre, args.n_rays, switch)
    print(
        f"all {len(kfs)} keyframes star-shaped about {interp.centre}; "
        f"{len(interp.thetas)} rays"
    )
    times = output_times(args)
    report(interp, times)
    write_entry(args.out_uri, interp, times, dd_version)
    print(f"wrote {len(times)} slices to {args.out_uri} (DD {dd_version})")


if __name__ == "__main__":
    main()
