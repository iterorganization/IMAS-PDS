# Time-dependent plasma shapes in the Waveform Editor — design notes

Status: design + validated prototype, 2026-07-10. Companion files: `README.md`
(prototype results), `PLAN.md` (editor implementation plan), interactive UI
study: https://claude.ai/code/artifact/de9b9ff2-86c2-4f66-bad2-d59ddb8457b0

## Problem

Shape targets are 2D outlines with a variable number of points per time slice.
The waveform editor interpolates 0D+t well, but IDS-sourced shapes only support
`closest` — no smooth shape evolution, and workflows depend on
`preprocess_dina.py` to pre-chew DINA data.

## Core decisions

1. **Shape is a first-class concept, but not a new interpolation engine.** A
   shape is an ordinary waveform *group* plus two categorical stepwise channels:
   - `configuration`: limited / diverted (every pulse transitions at least once);
   - `mode`: how the boundary is defined — parameterized (a, center, κ, δ,
     X-point), gaps, weighted points, or IDS import.
   All defining quantities are plain 0D+t waveforms with the full tendency
   language (smooth/linear/piecewise/expressions, derivatives). A renderer
   evaluates the active channel set at time t into an outline.

2. **Definition-space interpolation ("tier 1") wherever the mode is constant.**
   Interpolating κ(t), gap values, point coordinates is exact, has no
   correspondence problem, and is just the existing tendency engine. Preserves
   authored intent (a linear κ ramp stays linear).

3. **Canonical outline form ("tier 2") for IDS-sourced/mixed shapes** — a
   canonicalization pass at import, not a second interpolation semantics:
   resample every slice to fixed N, counter-clockwise, anchored at the outboard
   midplane, X-point pinned at a fixed index when present. Then N per-point
   channels interpolate like any other 0D quantity.

4. **The limited→diverted transition sits ON a knot, never blended across.**
   Physically the boundary is continuous at divertor formation (X-point lands on
   the limited boundary); the right model is a continuity constraint at t_X
   (validate: distance(x_point(t_X), boundary(t_X)) < tol), with x_point/legs
   channels gaining validity at t_X. Measured on DINA 105084: interpolating
   across the transition with straddling knots → 130 mm rms error; transition on
   a knot pair → 0.5 mm (resampling floor).

5. **X-point legs are explicit channels**, parameterized by distance from the
   X-point, carrying weights — extra target points along the legs help NICE
   inverse convergence. Leg points join the boundary point set at export
   (weight = point duplication, as in the shape editor's weighted-points mode).

## Validation (raw DD3 DINA 105084, no preprocessing)

- `boundary_separatrix.outline` is NOT a closed loop: closed boundary + leg
  polylines after coordinate jumps, or (early diverted) one open curve closing
  only at the X-point, plus a detached vacuum-separatrix arc in the limited
  phase. `split_separatrix` handles all layouts → this is the robustness layer
  a native import needs; the equilibrium part of `preprocess_dina.py` becomes
  redundant (psi_norm/profiles/pf_active parts remain).
- Canonical resampling: 2.6–3.6 mm rms (N=96–192); worst error at the
  high-curvature top → curvature-adaptive sampling is the known refinement.
- Interp vs closest at knot midpoint: ~2× better from 10 s knot spacing
  (ramp-up, 40 s knots: 0.93 m vs 1.8 m max).
- 7-param fit tracks the whole pulse at ~42 mm rms (limited phase needs
  κ_u/κ_l, δ_u/δ_l to beat 119 mm). Sparse RDP knots on parameter traces add
  nothing on top of the fit floor.

## Editor interaction model (see UI study artifact)

- **Keyframe/auto-key** (animation industry): playhead time answers "when does a
  drag edit"; snap to an existing piecewise knot within tolerance, else insert;
  non-piecewise segments prompt convert-to-piecewise. Dope sheet shows knots per
  channel. DAW "touch" mode ≈ preview + NICE trial solve, commit on release.
- **JS owns the gesture, Python owns the model.** Browser component renders and
  drags at 60 fps; on release it sends a field-level diff
  (`{waveform, segment, field, value}`) — never a document rewrite. Python
  applies it via tendencies + ruamel (comments preserved) and returns the
  authoritative curve. Base for the timeline strip:
  animation-timeline-control (MIT); theatre.js rejected (AGPL studio).
- **Differentiable drag**: the outline and the waveform evaluation are
  differentiable w.r.t. definition fields. A drag anywhere (boundary point,
  mid-segment of a curve) is solved least-norm in *scaled* parameter space over
  the unlocked variables: Δp = S·Aᵀ(AAᵀ+λI)⁻¹·Δx. The scales/locks are UI;
  influence arrows at the grab point show each variable's direction.
  Finite-difference Jacobians suffice (no autodiff dependency until solvers
  enter the loop). Default scope: fields of the segment under the playhead.
- Handle protocol reserves `kind: tangent/control` for future Inkscape-style
  bezier editing.

## Open questions

- Gap segment set: take from machine description (md_collections/basic.env:
  wall 116000/4) or per-scenario config? Needed for gap↔gap interpolation.
- `shapes:` as top-level YAML section vs shape-typed group in the existing tree
  (leaning top-level; shapes are referenced by exporters, not IDS-path-keyed).
- Asymmetric parameterization (κ_u/κ_l, δ_u/δ_l) — extend
  `plasma_shape_calc.py` and the fit.
