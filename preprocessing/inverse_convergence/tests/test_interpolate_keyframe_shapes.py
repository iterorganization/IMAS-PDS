"""Tests of interpolate_keyframe_shapes.py on synthetic outlines (no IMAS needed)."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interpolate_keyframe_shapes import (
    DIVERTED,
    LIMITER,
    Keyframe,
    KeyframeInterpolator,
    sample_on_rays,
    star_shape_check,
    xpoint_of,
)

CENTRE = (6.2, 0.5)


def ellipse(a, kappa, n=300, z0=0.5):
    """Closed counter-clockwise ellipse about (6.2, z0), first point repeated."""
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    r, z = 6.2 + a * np.cos(th), z0 + kappa * a * np.sin(th)
    return np.append(r, r[0]), np.append(z, z[0])


def diverted(a, kappa, xr, xz, n=300):
    """Upper half-ellipse closed by two straight lines through an X-point below."""
    th = np.linspace(0, np.pi, n)
    r, z = 6.2 + a * np.cos(th), 0.5 + kappa * a * np.sin(th)
    r = np.concatenate([r, [xr]])
    z = np.concatenate([z, [xz]])
    return np.append(r, r[0]), np.append(z, z[0])


def kf(t, topo, rz, ip):
    return Keyframe(t, topo, rz[0], rz[1], ip, -10.0 - ip / 1e6, -5.3)


def frames():
    return [
        kf(4.0, LIMITER, ellipse(1.8, 1.2), -2e6),
        kf(10.0, LIMITER, ellipse(1.9, 1.4), -3e6),
        kf(18.0, DIVERTED, diverted(2.0, 1.6, 5.1, -3.4), -4e6),
        kf(65.0, DIVERTED, diverted(2.0, 1.8, 5.2, -3.5), -15e6),
    ]


def test_star_shape_check():
    r, z = ellipse(1.8, 1.2)
    assert star_shape_check(r, z, CENTRE) == (True, 1)
    assert star_shape_check(r[::-1], z[::-1], CENTRE) == (True, -1)
    # a centre outside the outline: rays cross it twice or not at all
    assert not star_shape_check(r, z, (9.0, 0.5))[0]
    # a C-shaped (non star-shaped) outline
    th = np.linspace(0.3, 2 * np.pi - 0.3, 200)
    rc = np.concatenate([6.2 + 2 * np.cos(th), 6.2 + 1 * np.cos(th[::-1])])
    zc = np.concatenate([0.5 + 2 * np.sin(th), 0.5 + 1 * np.sin(th[::-1])])
    assert not star_shape_check(rc, zc, CENTRE)[0]
    with pytest.raises(ValueError):
        KeyframeInterpolator(
            [kf(0, LIMITER, (rc, zc), 1), kf(1, LIMITER, ellipse(1, 1), 1)], CENTRE
        )


def test_rays_hit_polygon_exactly():
    r, z = diverted(2.0, 1.6, 5.1, -3.4)
    th = np.array([np.arctan2(-3.4 - 0.5, 5.1 - 6.2)])
    s = sample_on_rays(r, z, CENTRE, th)
    assert s[0] == pytest.approx(np.hypot(5.1 - 6.2, -3.4 - 0.5), abs=1e-12)
    # on a circle the crossing radius is the circle radius up to the chord sag
    rc, zc = ellipse(2.0, 1.0, n=2000)
    s = sample_on_rays(rc, zc, CENTRE, np.linspace(-3, 3, 50))
    assert np.all(np.abs(s - 2.0) < 2.0 * (1 - np.cos(np.pi / 2000)) + 1e-12)


def test_keyframe_times_reproduced():
    fr = frames()
    it = KeyframeInterpolator(fr, CENTRE, 256, switch_times=[10.9])
    for i, f in enumerate(fr):
        rad, topo = it.radius(f.time)
        assert topo == f.topology
        np.testing.assert_array_equal(rad, it.radii[i])
        sc = it.scalars(f.time)
        assert sc["ip"] == f.ip and sc["psi_boundary"] == f.psi_boundary
        r, z, _ = it.outline(f.time)
        # every output point lies on the keyframe polygon: its ray radius is itself
        th = np.arctan2(z - 0.5, r - 6.2)
        np.testing.assert_allclose(
            np.hypot(r - 6.2, z - 0.5), sample_on_rays(f.r, f.z, CENTRE, th), atol=1e-9
        )
        if f.topology == DIVERTED:
            assert xpoint_of(r, z) == pytest.approx(xpoint_of(f.r, f.z), abs=1e-12)


def test_linear_in_time_between_same_topology():
    it = KeyframeInterpolator(frames(), CENTRE, 256, switch_times=[10.9])
    for t in (5.0, 7.0, 30.0, 50.0):
        k = int(np.searchsorted(it.times, t) - 1)
        w = (t - it.times[k]) / (it.times[k + 1] - it.times[k])
        rad, _ = it.radius(t)
        np.testing.assert_allclose(rad, (1 - w) * it.radii[k] + w * it.radii[k + 1])
        ips = [f.ip for f in it.keyframes]
        assert it.scalars(t)["ip"] == pytest.approx((1 - w) * ips[k] + w * ips[k + 1])
    # the midpoint radius is the mean of the neighbours
    r1, _ = it.radius(18.0)
    r2, _ = it.radius(65.0)
    np.testing.assert_allclose(it.radius(41.5)[0], 0.5 * (r1 + r2))
    # X-point error is reported only between two diverted keyframes
    assert it.xpoint_error(7.0) is None
    err = it.xpoint_error(41.5)
    assert err is not None and err[0] >= 0.0


def test_topology_step_and_holds():
    fr = frames()
    it = KeyframeInterpolator(fr, CENTRE, 256, switch_times=[10.9])
    for t, j in ((10.5, 1), (10.8999, 1), (10.9, 2), (15.0, 2)):
        rad, topo = it.radius(t)
        np.testing.assert_array_equal(rad, it.radii[j])
        assert topo == fr[j].topology
    # Ip stays linear across the topology change
    assert it.scalars(14.0)["ip"] == pytest.approx(-3.5e6)
    # holds before the first and after the last keyframe
    np.testing.assert_array_equal(it.radius(0.0)[0], it.radii[0])
    np.testing.assert_array_equal(it.radius(100.0)[0], it.radii[-1])
    assert it.scalars(100.0)["ip"] == fr[-1].ip
    assert it.scalars(0.0)["ip"] == fr[0].ip
    # switch time count and position are checked
    with pytest.raises(ValueError):
        KeyframeInterpolator(fr, CENTRE, 256, switch_times=[])
    with pytest.raises(ValueError):
        KeyframeInterpolator(fr, CENTRE, 256, switch_times=[20.0])
