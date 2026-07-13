# Shape toolkit prototype

Geometry kit for time-interpolatable plasma shapes, targeting first-class shape
support in the Waveform-Editor (shape = waveform group + categorical mode/
configuration channels; outlines canonicalized at import). Validated against the
raw DD3 DINA entry of scenario 105084 — the data `preprocess_dina.py` exists to
tame; a native shape import based on this kit can replace its equilibrium part.

## Tools (`shape_toolkit.py`)

- `split_separatrix(r, z, x_point)` — extract the closed boundary + divertor-leg
  polylines from a raw `boundary_separatrix.outline` (handles DINA's layouts:
  closed loop + leg sections, or open loop closing only at the X-point; limited
  slices with a detached vacuum-separatrix arc).
- `canonical(r, z, n, pin)` — resample to N points, CCW, anchored at the outboard
  midplane crossing, X-point (or partner pin) at fixed index n//2. Makes outlines
  of any point count pointwise-interpolatable.
- `interp_outlines(a, b, w)` — centroid-separated pointwise interpolation between
  canonicalized outlines (exact under pure translation).
- `outline_error(...)` — symmetric boundary distance (rms/max), the "view the
  error" metric.
- `fit_shape_params(r, z, x_point)` — least-squares fit of the parameterized
  config (a, center, kappa, delta [, rx, zx]) onto an outline; limited shapes use
  `compute_outline_limited` (Miller, no X-point), diverted the NICE-derived
  `compute_outline_from_params` from the Waveform-Editor shape editor.

## Run

```bash
~/pds/Waveform-Editor/venv/bin/python demo_dina.py   # figures in out/
```

## Findings (DINA 105084)

- Canonical N=96/192 resampling error: 3.6/2.6 mm rms. Max error (~45 mm) sits at
  the high-curvature top (near the upper secondary X-point), not at the pinned
  lower X-point -> curvature-adaptive point allocation is the known improvement.
- Interp vs closest at knot midpoint (max error): ~2x better from 10 s knot
  spacing up (ramp-up, 40 s knots: 0.93 m vs 1.8 m); below ~5 s spacing the
  resampling floor dominates and closest is comparable.
- Limited->diverted transition (t = 10.87 s): interpolating across it with
  straddling knots gives 130 mm rms mid-transition; putting the transition on a
  knot pair (last-limited / first-diverted) recovers the resampling floor
  (0.5 mm) there. Confirms the "transition is a knot, not a blend" design rule.
- Config fit: diverted flat-top 55 mm rms / 107 mm max with the 7-parameter
  family; limited 119 mm rms — single kappa/delta cannot express the up-down
  asymmetry -> add kappa_u/kappa_l, delta_u/delta_l to the config.
