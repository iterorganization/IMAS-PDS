# Shape editor work plan

## Principles

- **Interpretable data underneath**: everything persists as Waveform-Editor YAML
  (tendencies + shape channels). UI widgets are stateless views over that model;
  no widget owns state, so the editor stays scriptable and diffable.
- **Animation-industry UX**: playhead, dope sheet (per-channel knot markers),
  auto-key editing, curve editor, touch-preview.
- **Host-agnostic components**: build the interactive pieces as self-contained
  TypeScript widgets (AnyWidget/ESM). They embed in Panel today and in a
  standalone page or Jupyter later — "outside Panel" becomes a deployment
  choice, not a rewrite.

## Library assessment (buy vs build)

| candidate | verdict |
|---|---|
| theatre.js | Closest to a full animation toolkit, but the studio UI is AGPL-3.0 (core is Apache-2.0) and it brings its own keyframe store that would compete with our YAML model. Reject as base; copy UX ideas. |
| animation-timeline-control (MIT, TS, canvas, zero deps) | Keyframe rows, drag/multi-select, snap, zoom, playhead. **Buy**: base for the dope-sheet strip. No curve editor (that stays a plot). |
| timeliner (zz85), mo.js timeline editor | Prototype-grade / stale. No. |
| Qt + pyqtgraph | Good dragging, wrong deployment for our SSH/web environment. |
| Bokeh built-ins | PointDrawTool/PolyEdit give client-side dragging in the R-Z view with no custom JS. **Use first** for X-point/gap/point dragging. |

Decision: buy the timeline strip, keep the R-Z view and curve editor as Bokeh
figures initially (draggable knots for piecewise tendencies), write thin
adapters. Custom TS curve editor only if Bokeh latency proves inadequate.

## Phases

0. **Comparison tools** (this prototype): per-slice fit over the pulse, RDP knot
   suggestion, error-vs-time of the sparse definition (`compare_dina.py`).
   Next: gap-set fitting (needs the official segment geometry), then a
   "DINA scenario -> draft shape YAML" generator — the native replacement for
   the equilibrium part of `preprocess_dina.py`.
1. **Data model in waveform_editor** (headless): shape group with
   `configuration`/`mode` categorical channels + parameter/gap/point channels,
   canonical outline import (`split_separatrix` + `canonical` in
   import_resolver), `shape_at(t)` API, transition continuity validation.
   YAML round-trip + tests against DINA fixtures.
2. **Read-only timeline UI**: playhead + dope sheet + R-Z scrub view.
   AnyWidget wrapper around animation-timeline-control, fed knot JSON derived
   from tendencies. Ship early, editing disabled.
3. **Editing**: auto-key (snap to existing piecewise knot at playhead else
   insert; other tendency types prompt convert-to-piecewise), drag knots in
   time (dope sheet) and value (curve editor, R-Z view), touch-preview with
   NICE trial solve committed on release.
4. **Workflow integration**: WE MUSCLE3 actor serves interpolated shapes to the
   `feature/we_scenario` workflows natively; retire preprocessed equilibrium input.

Widget <-> Python protocol: knot list `{channel, t, value, interp}` + playhead
events; edits arrive as diffs and are mapped onto tendencies in Python
(client-side optimistic render, batched commit on drag release).
