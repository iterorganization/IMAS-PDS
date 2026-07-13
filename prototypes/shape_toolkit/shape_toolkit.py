"""Prototype toolkit for time-interpolatable plasma shapes.

Canonical form: N points, counter-clockwise, starting at the outboard midplane
crossing, with the X-point (or a virtual pin) at a fixed index. Two outlines in
canonical form with the same N interpolate pointwise, regardless of their
original point counts.
"""

import numpy as np
from scipy.optimize import least_squares

from waveform_editor.shape_editor.plasma_shape_calc import compute_outline_from_params


def _chord_area(p):
    """Shoelace area of a polyline closed by the chord end -> start."""
    q = np.vstack([p, p[0]])
    return abs(np.sum(q[:-1, 0] * q[1:, 1] - q[1:, 0] * q[:-1, 1])) / 2


def split_separatrix(r, z, x_point=None, jump_factor=5.0, x_tol=0.5):
    """Extract the closed plasma boundary and leg polylines from a raw separatrix.

    Handles the layouts DINA writes to boundary_separatrix.outline: a closed loop
    plus leg sections after a coordinate jump, or a single open curve that closes
    only at the X-point (loop with leg tails). The boundary is the largest-area
    arc after cutting at jumps and at closest approaches to the X-point.

    Returns:
        (r_boundary, z_boundary, legs), legs a list of (r, z) arrays.
    """
    P = np.column_stack([np.asarray(r, float), np.asarray(z, float)])
    seg = np.hypot(*np.diff(P, axis=0).T)
    tol = jump_factor * max(np.median(seg), 1e-6)
    arcs = []
    for piece in np.split(P, np.nonzero(seg > tol)[0] + 1):
        if len(piece) < 3:
            continue
        if x_point is None:
            arcs.append(piece)
            continue
        d = np.hypot(*(piece - np.asarray(x_point, float)).T)
        if np.hypot(*(piece[0] - piece[-1])) < tol:  # closed: roll to X-point pass
            if d.min() < x_tol:
                piece = np.roll(piece[:-1], -int(np.argmin(d)), axis=0)
            arcs.append(piece)
            continue
        # open: cut at local minima of the distance to the X-point
        interior = [
            i
            for i in range(1, len(d) - 1)
            if d[i] < x_tol and d[i] <= d[i - 1] and d[i] <= d[i + 1]
        ]
        cuts = [0] * bool(d[0] < x_tol) + interior + [len(d) - 1] * bool(d[-1] < x_tol)
        cuts = [i for k, i in enumerate(cuts) if k == 0 or i - cuts[k - 1] > 5]
        for a, b in zip([0] + cuts, cuts + [len(piece) - 1]):
            if b - a >= 3:
                arcs.append(piece[a : b + 1])
    if not arcs:
        return np.asarray(r, float), np.asarray(z, float), []
    main = max(arcs, key=_chord_area)
    legs = [(p[:, 0], p[:, 1]) for p in arcs if p is not main]
    return main[:, 0], main[:, 1], legs


def _normalize(r, z):
    """Open polyline, counter-clockwise, no duplicate closing point."""
    r, z = np.asarray(r, float), np.asarray(z, float)
    if np.hypot(r[0] - r[-1], z[0] - z[-1]) < 1e-12:
        r, z = r[:-1], z[:-1]
    area = 0.5 * np.sum(r * np.roll(z, -1) - np.roll(r, -1) * z)
    if area < 0:
        r, z = r[::-1], z[::-1]
    return r, z


def centroid(r, z):
    """Polygon area centroid."""
    r, z = _normalize(r, z)
    rn, zn = np.roll(r, -1), np.roll(z, -1)
    cross = r * zn - rn * z
    a = cross.sum() / 2
    return ((r + rn) * cross).sum() / (6 * a), ((z + zn) * cross).sum() / (6 * a)


def _closed(r, z):
    """Closed polyline P (m+1, 2) and cumulative arc length s (m+1,)."""
    P = np.column_stack([r, z])
    P = np.vstack([P, P[0]])
    slen = np.hypot(*np.diff(P, axis=0).T)
    return P, np.concatenate([[0], np.cumsum(slen)])


def _at_arclength(P, s, si):
    """Points on polyline at arc lengths si (wrapped)."""
    si = np.mod(si, s[-1])
    i = np.clip(np.searchsorted(s, si, "right") - 1, 0, len(s) - 2)
    t = (si - s[i]) / np.maximum(s[i + 1] - s[i], 1e-30)
    return P[i] + t[:, None] * (P[i + 1] - P[i])


def _project(P, s, point):
    """Arc-length coordinate of the projection of `point` onto the polyline."""
    A, D = P[:-1], np.diff(P, axis=0)
    dd = np.maximum((D * D).sum(1), 1e-30)
    t = np.clip(((point - A) * D).sum(1) / dd, 0, 1)
    d = np.hypot(*(A + t[:, None] * D - point).T)
    i = np.argmin(d)
    return s[i] + t[i] * (s[i + 1] - s[i])


def _anchor(P, s):
    """Arc length of the outboard midplane crossing (z = centroid z, max r)."""
    cz = centroid(P[:-1, 0], P[:-1, 1])[1]
    dz = P[:, 1] - cz
    cross = np.nonzero(dz[:-1] * dz[1:] <= 0)[0]
    den = dz[cross] - dz[cross + 1]
    den = np.where(np.abs(den) < 1e-30, 1e-30, den)
    t = dz[cross] / den
    rc = P[cross, 0] + t * (P[cross + 1, 0] - P[cross, 0])
    k = np.argmax(rc)
    i = cross[k]
    return s[i] + t[k] * (s[i + 1] - s[i])


def canonical(r, z, n=96, pin=None):
    """Resample an outline to canonical form.

    Args:
        r, z: outline coordinates (any point count, any orientation).
        n: number of output points.
        pin: optional (r, z) pinned at index n//2 (X-point, or the partner
            shape's X-point projected onto this outline).

    Returns:
        (n, 2) array; index 0 is the outboard midplane anchor.
    """
    r, z = _normalize(r, z)
    P, s = _closed(r, z)
    L = s[-1]
    s0 = _anchor(P, s)
    if pin is None:
        return _at_arclength(P, s, s0 + L * np.arange(n) / n)
    k = n // 2
    d = np.mod(_project(P, s, np.asarray(pin, float)) - s0, L)
    si = np.concatenate(
        [s0 + d * np.arange(k + 1) / k, s0 + d + (L - d) * np.arange(1, n - k) / (n - k)]
    )
    return _at_arclength(P, s, si)


def interp_outlines(shape_a, shape_b, w, n=96):
    """Interpolate two outlines; point counts may differ.

    Args:
        shape_a, shape_b: (r, z, x_point) tuples, x_point = (r, z) or None.
        w: interpolation weight in [0, 1] (0 -> a, 1 -> b).

    Returns:
        (r, z, x_point) at weight w; x_point is set only if both inputs have one.
    """
    ra, za, xa = shape_a
    rb, zb, xb = shape_b
    pin_a, pin_b = xa if xa is not None else xb, xb if xb is not None else xa
    A = canonical(ra, za, n, pin_a)
    B = canonical(rb, zb, n, pin_b)
    ca, cb = np.array(centroid(ra, za)), np.array(centroid(rb, zb))
    P = (1 - w) * ca + w * cb + (1 - w) * (A - ca) + w * (B - cb)
    x = tuple((1 - w) * np.asarray(xa) + w * np.asarray(xb)) if xa and xb else None
    return P[:, 0], P[:, 1], x


def distances_to_outline(pts, r, z):
    """Distance from each point in pts (n, 2) to the closed outline (r, z)."""
    P, _ = _closed(*_normalize(r, z))
    A, D = P[:-1], np.diff(P, axis=0)
    dd = np.maximum((D * D).sum(1), 1e-30)
    W = pts[:, None, :] - A[None]
    t = np.clip((W * D[None]).sum(2) / dd[None], 0, 1)
    proj = A[None] + t[..., None] * D[None]
    return np.hypot(*(pts[:, None, :] - proj).transpose(2, 0, 1)).min(1)


def outline_error(r1, z1, r2, z2, n=192):
    """Symmetric distance between two outlines: dict with rms and max [m]."""
    d1 = distances_to_outline(canonical(r1, z1, n), r2, z2)
    d2 = distances_to_outline(canonical(r2, z2, n), r1, z1)
    d = np.concatenate([d1, d2])
    return {"rms": float(np.sqrt((d**2).mean())), "max": float(d.max())}


def compute_outline_limited(a, center_r, center_z, kappa, delta, n):
    """Smooth closed Miller-type boundary (no X-point), for the limited phase."""
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    r = center_r + a * np.cos(theta + np.arcsin(delta) * np.sin(theta))
    z = center_z + a * kappa * np.sin(theta)
    return r, z


def render_params(params, n=96):
    """Render a shape config (dict) to an outline; diverted iff rx/zx present."""
    if "rx" in params:
        r, z = compute_outline_from_params(n_desired_bnd_points=n, **params)
        return np.asarray(r), np.asarray(z), (params["rx"], params["zx"])
    return (*compute_outline_limited(n=n, **params), None)


def fit_shape_params(r, z, x_point=None, n=96, x0=None):
    """Fit a parameterized shape config onto an outline.

    Args:
        r, z: target outline.
        x_point: (r, z) if the target is diverted -> fit rx/zx too.
        x0: optional warm-start parameter dict (same family).

    Returns:
        (params dict, error dict from outline_error).
    """
    r, z = _normalize(r, z)
    rmin, rmax, zmin, zmax = r.min(), r.max(), z.min(), z.max()
    a0, r0 = (rmax - rmin) / 2, (rmax + rmin) / 2
    z0 = centroid(r, z)[1]
    guess = [a0, r0, z0, (zmax - zmin) / (rmax - rmin), (r0 - r[np.argmax(z)]) / a0]
    lo = [0.3 * a0, rmin, zmin, 0.8, -0.9]
    hi = [1.5 * a0, rmax, zmax, 3.0, 0.9]
    names = ["a", "center_r", "center_z", "kappa", "delta"]
    if x_point is not None:
        guess += list(x_point)
        lo += [x_point[0] - a0 / 2, x_point[1] - a0 / 2]
        hi += [x_point[0] + a0 / 2, x_point[1] + a0 / 2]
        names += ["rx", "zx"]
    if x0 is not None and set(x0) >= set(names):
        guess = [float(np.clip(x0[k], lo_, hi_)) for k, lo_, hi_ in zip(names, lo, hi)]
    target = canonical(r, z, n, pin=x_point)

    def residual(x):
        try:
            rr, zz, xpt = render_params(dict(zip(names, x)), n)
            return (canonical(rr, zz, n, pin=xpt) - target).ravel()
        except (ValueError, ZeroDivisionError):
            return np.full(2 * n, 10.0)

    sol = least_squares(residual, guess, bounds=(lo, hi), x_scale="jac")
    params = dict(zip(names, sol.x))
    rr, zz, _ = render_params(params, n)
    return params, outline_error(rr, zz, r, z)
