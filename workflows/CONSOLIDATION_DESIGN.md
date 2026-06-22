# Consolidating PDS workflows into 2 (MUSCLE3 0.9 / yMMSL v0.2)

*Design agreed 2026-06-16. Goal: collapse the ~10 workflows in `pds/pds/workflows/`
into **two** top-level workflows, using yMMSL v0.2 subworkflows (models-as-implementations),
optional components, and `custom_implementations` swaps.*

## Decisions (locked)

1. **Scope of this effort**: author the v0.2 structure + validate it *parses and wires*
   under a MUSCLE3 0.9.1 venv. Do **not** rebuild NICE/TORAX/IMAS-MUSCLE3 actors against
   0.9 yet (the actors still link libmuscle 0.8.0; running end-to-end is a later step).
2. **The two workflows**:
   - **`inverse_convergence`** — all NICE-inverse timeslices → accumulate → TORAX
     transport over all slices; one such pass = a subworkflow. The outer Picard loop
     stays a **fixed-N shell loop** (`RERUN_N_TIMES` in `run_simulation.sh`), unchanged.
     Diagnostic only: log max |ΔI| across the 14 NICE coil-current waveforms between
     successive iterations (does **not** terminate the loop).
   - **`evolutive`** — pure **nice_evo ↔ torax direct co-simulation** by default.
     PCS magnetic_controller + temporal_coupler are **optional components** (holes,
     disabled by default via `custom_implementations: … null`). `nice_evo_rd` is a
     swap-in for `nice_evo` (adds core_profiles coupling).
3. **Transport is an interface hole**: `torax` is the default `custom_implementations`
   fill; `metis` is the documented alternative fill (METIS not runnable here — no MATLAB).
4. **Source is an interface hole**: default fill = the DINA-preprocessed `source`;
   future `efit_source` etc. plug into the same hole.

## Confirmed yMMSL v0.2 syntax (muscle3 0.9.1 / ymmsl **0.15.1-dev** in /tmp/m3_090_venv)

**Empirically verified 2026-06-16 against the actual venv** (the venv ships ymmsl
0.15.1-dev, not 0.16.0). All claims below were checked by loading + `resolve()` +
`check_consistent()` and by a real `muscle_manager --no-start-all` flatten. Key
differences from v0.1, and several corrections to the original draft of this section:

- Header: `ymmsl_version: v0.2`.
- Top key is **`models:`** (plural), a mapping `name -> model`. Each model has
  `description`, optional `ports:` (used only when the model is *nested*),
  `components:`, `conduits:`.
- **Subworkflow = model-as-implementation**: a component's `implementation:` may name
  *another model*. The nesting component **must declare `ports:`** (use `ports: {}` when
  the nested model has no model-level ports — which is our case, the two subworkflows are
  self-contained and expose no external ports).
- **Every component requires three keys: `name`, `ports`, and `description`.** A bare
  `{implementation: x}` or `{implementation: x, ports: {}}` is rejected by the loader
  (`Expected a key "description"/"ports"`). This is the single biggest gotcha. (`name`
  comes from the mapping key under `components:`.)
- **Optional component**: `optional: true` on the component. Combined with no
  `implementation:` it is an interchangeable *hole* that may be filled or disabled.
- **`custom_implementations:`** — mapping `<rootmodel>.<component>[.<subcomponent>…] ->
  impl_name`, or `-> null` to **disable** an optional component. **The key path is
  prefixed with the ROOT MODEL name**, not just the component — e.g.
  `inverse_convergence.pass.transport: torax`, *not* `pass.transport: torax`. Getting
  this wrong yields `Unknown model "pass" in custom_implementations`.
- **`imports:`** — list of strings `from <a.b.c> import implementation <name>`, where
  `<name>` is a model or program name. **Resolution is via the `YMMSL_PATH` env var (a
  `:`-separated list of dirs) and Python entry points — NOT relative to the importing
  file** (corrects the original draft). `a.b.c` maps to the relative path
  `a/b/c.ymmsl`, which is searched under each `YMMSL_PATH` dir. So set
  `YMMSL_PATH=<…>/pds/pds/workflows` and `from lib.programs import …` resolves to
  `workflows/lib/programs.ymmsl`. (`run_simulation.sh` must export this.)
- **A subworkflow model file must itself `import` every hard-wired (non-hole)
  implementation it names.** When a model is imported, the resolver eagerly resolves the
  implementations of *its* components too; if `inverse_pass` wires `nice_inv`/`accumulator`/
  `sink`, those must be imported inside `lib/inverse_pass.ymmsl`. Hole/optional components
  (source, transport, validator, …) are exempt — they're filled by the scenario.
- `programs:` (mapping name -> Program) replaces v0.1 `implementations:`. Program fields:
  `modules`, `virtual_env`, `env`, `base_env` (lowercase, e.g. `clean`/`manager`),
  `executable`, `args`, `script`, `execution_model` (`direct`|`openmpi`|`intelmpi`|
  `srunmpi`|`manual`), `can_share_resources`, `keeps_state_for_next_use`, plus
  `ports`/`supported_settings`. A `script` is mutually exclusive with
  `executable`/`args`/`modules`/`env`/`virtual_env`/`base_env`.
- **Two different key conventions — verified by running, the earlier draft was wrong:**
  - `custom_implementations` keys are **root-model-prefixed**:
    `inverse_convergence.pass.transport`. (Else: `Unknown model "pass"`.)
  - `settings` and `resources` keys use the **bare instance name** (the root model is not
    part of instance names): `pass.nice_inv.xml_path`, `pass.source: {threads: 1}`.
    Using the root-model prefix on a setting silently misses the instance — the actor then
    dies with `KeyError: setting "<x>" was not set`.
- **`--start-all` requires a `resources:` entry per enabled component**
  (`{threads: N}`); `--no-start-all` does not. Disabled (`null`) optionals need none.
- The manager merges multiple files: `muscle_manager [opts] base.ymmsl scenario.ymmsl`;
  pick the top model with `-m <model>` when several are present. `--run-dir` must already
  exist. `--no-start-all` flattens + resolves + `check_consistent` and (with no manual
  instances) reports "Simulation completed successfully" / exit 0 without launching
  actors, writing the flattened graph to `<run-dir>/configuration.ymmsl`.

Minimal validated example (matches the shipped files):
```yaml
# lib/inverse_pass.ymmsl
ymmsl_version: v0.2
imports:
- from lib.programs import implementation nice_inv     # hard-wired impls imported here
models:
  inverse_pass:
    description: ...
    ports: {}
    components:
      source:    { description: hole, ports: {o_i: [equilibrium_out]} }   # hole
      nice_inv:  { description: ..., implementation: nice_inv,
                   ports: {f_init: [...], o_f: [...]} }
      transport: { description: hole, ports: {f_init: [...], o_f: [...]} } # hole
      validator: { description: opt, optional: true, ports: {f_init: [pf_active_in]} }
    conduits: { source.equilibrium_out: nice_inv.equilibrium_in }
---
# inverse_convergence/inverse_convergence.ymmsl
ymmsl_version: v0.2
imports:
- from lib.inverse_pass import implementation inverse_pass
- from lib.programs import implementation torax
models:
  inverse_convergence:
    description: ...
    components:
      pass: { description: ..., implementation: inverse_pass, ports: {} }
---
# scenario.ymmsl
ymmsl_version: v0.2
custom_implementations:        # root-model-prefixed
  inverse_convergence.pass.transport: torax
  inverse_convergence.pass.validator: null
settings:                      # bare instance name (no root model)
  pass.nice_inv.xml_path: /path/config_nice.xml
resources:                     # required by --start-all; bare instance name
  pass.nice_inv: {threads: 8}
```

### Disabled-optional-conduit risk: RESOLVED — dangling conduits are auto-dropped

The main open risk (§ Workflow B) is settled empirically: **a component disabled via
`custom_implementations: …: null` is removed from the flattened configuration together
with every conduit attached to it.** Verified by inspecting `<run-dir>/configuration.ymmsl`
after `--no-start-all`: disabling `temporal_coupler`/`magnetic_controller`/`sink_controller`
in the evolutive scenario removed those components and all their conduits, leaving exactly
the direct co-sim graph; `check_consistent` passed throughout. Conduit endpoints are
checked against the model's *declared* components (which still exist as declarations), so
the dangling conduits never trigger an error and are pruned at flatten time. **Therefore
NO separate conduit-set/variant files are needed for the default workflows.** (Caveat for
the *future* controller variant only: enabling an optional re-activates its conduits
*alongside* the still-present direct conduits, double-wiring shared receiver ports;
ymmsl does not flag this, so that variant should ship as a separate
`direct_cosim_controlled.ymmsl` model without the two direct conduits.)

## Proposed file layout (under `pds/pds/workflows/`)

```
workflows/                              # set YMMSL_PATH to THIS dir so lib.* imports resolve
  lib/
    programs.ymmsl.template # ALL implementations: source, sink, accumulator, sink_source,
                            #   visualization, olc, nice_inv, nice_evo, nice_evo_rd, torax,
                            #   metis, temporal_coupler, magnetic_controller. .template
                            #   because it contains [BASEDIR_PLACEHOLDER].
    inverse_pass.ymmsl      # inverse subworkflow MODEL (no placeholders → plain .ymmsl);
                            #   imports its own hard-wired programs (nice_inv/accumulator/sink)
    direct_cosim.ymmsl      # evolutive subworkflow MODEL (plain .ymmsl); imports sink/sink_source
  inverse_convergence/
    inverse_convergence.ymmsl          # top-level (plain): imports lib.*, 1 component = inverse_pass
    scenarios/105084/scenario.ymmsl.template   # custom_implementations + settings
                                       #   (keys prefixed inverse_convergence.pass.*) + placeholders
    run_simulation.sh / preprocess_data.sh / create_runnable_files.sh / config_*  # reuse
  evolutive/
    evolutive.ymmsl                    # top-level (plain)
    scenarios/105084/scenario.ymmsl.template   # custom_implementations: controller/coupler/
                                       #   sink_controller=null, transport=torax, nice_evo=nice_evo
    …
```

Files containing `[…_PLACEHOLDER]` sed tokens get the `.ymmsl.template` suffix (expanded
by `create_runnable_files.sh`: `[BASEDIR_PLACEHOLDER]`/`[SUBDIR_PLACEHOLDER]`/`[SHOT_NR]`,
plus `[TSTART_PLACEHOLDER]` for evolutive, filled by preprocessing). Per this repo's `.gitignore` (`*.ymmsl` ignored, `!*.template` tracked) ALL source
files — including the placeholder-free structural models and top models — are committed as
`.ymmsl.template`; `create_runnable_files.sh` copies them verbatim to `.ymmsl`. **`run_simulation.sh` must `export YMMSL_PATH=<…>/pds/pds/workflows`** (or pass
the dir) so `from lib.programs import …` resolves.

## Workflow A — `inverse_convergence` (subworkflow `inverse_pass`)

Derived from `torax_nice_self_consistent_transport/workflow.ymmsl.template` (§3.4 of
`NICE_WORKFLOWS_EVALUATION.md`). Components & conduits of `inverse_pass` (one pass):

- `source` (hole) o_i: equilibrium, wall, pf_active, pf_passive, iron_core, core_profiles
- `nice_inv` f_init(equilibrium,wall,pf_active,pf_passive,iron_core) → o_f(equilibrium,pf_active)
- `accumulator` s(equilibrium,core_profiles) → o_f(equilibrium,core_profiles)
- `acc2` s(wall,pf_active,pf_passive,iron_core) → o_f(same)
- `transport` (hole; fill=torax) f_init(equilibrium,core_profiles) → o_i(equilibrium) →
  o_f(equilibrium,core_profiles)
- `sink_nice`, `sink_torax`
- `validator` (optional; fill=olc) f_init(pf_active)
- `visualization_nice`, `visualization_torax` (optional)

Conduits exactly as in the existing template (lines 51–81 of that file). Top model
`inverse_convergence` has one component `pass: {implementation: inverse_pass}`.
Scenario file: `custom_implementations: {pass.source: source, pass.transport: torax,
pass.validator: olc, pass.visualization_nice: …, pass.visualization_torax: …}` and the
`pass.*` settings (source_uri, sink_uri, xml_path, python_config_module, etc).

## Workflow B — `evolutive` (subworkflow `direct_cosim`)

Derived from `torax_nice_controller/workflow.ymmsl.template` (§3.5), **minus** the
controller by default. Components of `direct_cosim`:

- `source` o_i: equilibrium, pf_active, wall, pf_passive, iron_core, core_profiles
- `nice_evo` (hole/swap; fill=nice_evo, alt=nice_evo_rd)
  f_init(equilibrium,wall,pf_active,pf_passive,iron_core[,core_profiles for rd]) /
  s(equilibrium,pf_active[,core_profiles]) / o_i(equilibrium,pf_active)
- `transport` (hole; fill=torax) f_init(equilibrium,core_profiles) /
  s(equilibrium) / o_i(equilibrium,core_profiles)
- `temporal_coupler` (**optional**; default null): s(a_in,b_in)/o_i(a_out,b_out)
- `magnetic_controller` (**optional**; default null):
  f_init(equilibrium,pf_active)/s(equilibrium,pf_active)/o_i(pf_active)
- `sink_nice`, `sink_torax`, `sink_controller`(optional), `sink_source`,
  `visualization_*`(optional)

**Default (direct) wiring** (no coupler, no controller): wire
`transport.equilibrium_o_i → nice_evo.equilibrium_s` and
`nice_evo.equilibrium_o_i → transport.equilibrium_s` directly. The controller/coupler
variants are achieved by enabling those optional components and the alternative conduits.
Disabling a component drops its dangling conduits automatically (resolved — see the
"Disabled-optional-conduit risk" section above); the only caveat is the future
*controller* variant double-wiring, which ships as a separate model.

## Validation procedure (this effort's definition of done) — DONE ✔ (2026-06-16)

Both top models validate. Templates must be expanded first (so there are no `[…]`
tokens left in the YAML) and `YMMSL_PATH` must point at the expanded `workflows/` dir.
The commands that passed (against an expanded copy of the tree):
```bash
export YMMSL_PATH=<expanded-workflows-dir>
# parse check (per file):
/tmp/m3_090_venv/bin/python -c "import ymmsl,sys; ymmsl.load(open(sys.argv[1]).read())" <file>
# real flatten/wire test (resolves nesting + imports + custom_implementations, no actors):
mkdir -p run_inv
/tmp/m3_090_venv/bin/muscle_manager --no-start-all --run-dir run_inv -m inverse_convergence \
  inverse_convergence/inverse_convergence.ymmsl \
  inverse_convergence/scenarios/105084/scenario.ymmsl
mkdir -p run_evo
/tmp/m3_090_venv/bin/muscle_manager --no-start-all --run-dir run_evo -m evolutive \
  evolutive/evolutive.ymmsl evolutive/scenarios/105084/scenario.ymmsl
```
Result for both: `Simulation completed successfully.` / exit 0, and a flattened
`<run-dir>/configuration.ymmsl` with holes filled (transport=torax, source=source, …),
optionals correctly disabled (evolutive: coupler/controller/sink_controller dropped with
all their conduits, leaving the pure direct co-sim graph), and no unbound ports. The
`nice_evo → nice_evo_rd` swap and the inverse `validator=olc` fill also validate.

## Rebuild on MUSCLE3 0.9.1 + end-to-end run — DONE ✔ (2026-06-17)

The "do not rebuild yet" scope decision was lifted; the whole stack now runs on 0.9.1.

- **MUSCLE3 0.9.1 C++ (intel-2023b)**: built from source to `~/pds/opt/muscle3-0.9.1-intel`
  (`CXX=icpx`, `msgpack_ROOT=$EBROOTMSGPACKMINC`, cpp-only install needs `TOOLDIR` and
  `MUSCLE_LINUX=1` exported when invoking `libmuscle/cpp` directly). `source
  <prefix>/bin/muscle3.env` prepends its `PKG_CONFIG_PATH`/`LD_LIBRARY_PATH`.
- **NICE**: the 5 MUSCLE3-touching objects recompiled clean against the 0.9.1 headers
  (no API breakage) and relinked; `~/pds/pds/nice/run/*_muscle3` now link the 0.9.1
  libmuscle. 0.8.0 binaries backed up at `nice/run.bak.08`.
- **TORAX venv** (`run/TORAX-MUSCLE3/venv`) and a **new actors venv**
  (`~/pds/opt/venv-m3091-actors`: muscle3 0.9.1 + imas-python + h5py + imas_muscle3)
  carry the Python side. The 0.9.1 manager lives in the actors venv.
- **IMAS-MUSCLE3 ported to ymmsl v0.2**: ymmsl ≥0.15 split into `v0_1`/`v0_2`; only
  `Operator`/`Settings`/`load`/`dump`/`save` stay top-level. All actor imports moved to
  `from ymmsl.v0_2 import …` (`Operator`, `SettingValue`), pinned `muscle3>=0.9` +
  `ymmsl>=0.15`. (Uncommitted on `main`; upstream-worthy.)

**End-to-end smoke**: `inverse_convergence` / 105084 ran to completion on the 0.9.1
stack (manager ↔ rebuilt C++ NICE ↔ migrated Python actors ↔ 0.9.1 TORAX), exit 0,
producing 40 NICE + 1854 TORAX equilibrium slices over t=2.4–280.4 s — matching the
original 0.8.0 production run. A reusable 0.9.1 program overlay + the run tree are at
`~/pds/pds/run/tmp/smoke_m3091/` (`lib/programs.ymmsl`: python actors via `virtual_env`,
NICE via a `script` that loads the module + sources `muscle3.env`, TORAX via its venv).

## Workflow A′ — `inverse_convergence_loop`: the outer loop inside MUSCLE3

An alternative to the fixed-N shell loop: express the outer Picard convergence as a
MUSCLE3 **reuse loop** in a higher-level model that imports the inverse work as a
subworkflow. Authored and flatten-validated (running needs actor support, below).

- `lib/inverse_pass_loop.ymmsl` — the inverse sweep as a subworkflow with **model ports**
  (`s:[target_in]`, `o_i:[result_out, coils_out]`), so the whole pass plugs in as one
  nested component. `transport` stays an interface hole.
- `inverse_convergence_loop/inverse_convergence_loop.ymmsl` — macro/micro coupling:
  ```
  driver.target_out (O_I) → pass.target_in (S)      # drive current target in
  pass.result_out  (O_I) → driver.result_in (S)     # result back
  pass.coils_out   (O_I) → driver.coils_in  (S)     # coils for the |ΔI| metric
  ```
  The `driver` (a `convergence_driver` program) owns the iteration count + the
  max|ΔI|-across-14-coils metric + tolerance/max-iter, and terminates by closing
  `target_out`, which ends the micro's reuse loop.

Flattening collapses the model ports correctly (e.g. `driver.target_out →
pass.nice_inv.equilibrium_in`, `pass.transport.equilibrium_o_i → driver.result_in`).

**Reusable components extracted**: (1) `convergence_driver` — a generic Picard /
under-relaxed fixed-point controller with the coil-current metric, reusable for any
iterated coupling; (2) `inverse_pass_loop` — the ported inverse sweep; (3) `transport`
hole (torax|metis). The existing source/sink/accumulator actors stay the leaf blocks.

**No S/O_I change to NICE is needed.** The loop is a standard macro/micro coupling: the
`convergence_driver` is the macro (`O_I`/`S`) and the pass is the micro (`F_INIT`/`O_F`) —
which is exactly the shape `nice_inv` already has. The macro sends the target, the micro
(unmodified NICE inverse → accumulate → TORAX) returns the result, and the macro feeds it
back, reusing the micro once per outer iteration. Proven runnable in
`run/tmp/proto_parallel_inv/conv_loop_demo.py` (Picard fixed point converges in 14 iters
with a plain F_INIT/O_F worker). The only remaining glue to run it on the real codes is
driving the micro at the right granularity (the driver feeds per-slice targets like the
source / dispatcher does); the fixed-N shell-loop `inverse_convergence` remains the
simplest runnable form meanwhile.

## MUSCLE3 0.10.0 rebuild + parallel NICE dispatcher — DONE ✔ (2026-06-18)

The whole stack was rebuilt 0.9.1 → **0.10.0** (latest release) to get dynamic ports:
MUSCLE3 0.10.0 C++ (intel) at `~/pds/opt/muscle3-0.10.0-intel`, NICE relinked against it,
and the Python venvs (actors + TORAX) bumped. **0.10.0 enforces an exact instance/manager
libmuscle version match**, so the whole stack must be on 0.10.0 (no mixed versions). Build
scripts: `~/pds/opt/build_muscle3_010.sh`, `build_nice_010.sh`.

**Dynamic ports (0.10.0) — what it is.** Construct `Instance()` with no ports and discover
them at runtime via `list_ports()`; ports are defined by the yMMSL. It is for a *variable set
of named ports* (the `combiner` pattern), **not** vector/round-robin. Verified: a *dynamic*
port wired to a multiplicity-W component does become a vector (`is_vector=True`, length W,
slot send/recv) — vectorness is derived from the peer's multiplicity. But a dynamic port to a
*single* source resolves to scalar, so a resizable vector **front** can't be dynamic.

**Parallel NICE inverse — the dispatcher (option B, validated).** The N independent per-slice
inverses run over W workers via an IMAS-agnostic round-robin **scatter/gather multiplexer**
(`imas_muscle3.actors.dispatcher_component`, the load_balancer pattern):
```
driver (IMAS: reads source, sends N on resizable vector front, gathers N, writes sink)
   └─> dispatcher (IMAS-agnostic, no disk: round-robin to W, gather FIFO-per-slot, in order)
          └─> nice_imas_inv_muscle3 × W   (unmodified real NICE)
```
Because the dispatcher knows N (= front length) and counts started/done, it handles a **ragged
tail (N not divisible by W)** cleanly — no per-slot close detection. Output returns in original
(time) order; `timestamp`/`t_next` are preserved end-to-end. The disk/IMAS I/O lives in the
`driver` (the qmc role); the dispatcher only forwards serialized messages. The driver's front
ports must be declared resizable vectors (`name[]` + `set_port_length`).

**Validated:** real NICE ×4, N=10 over W=4 (ragged), exit 0, `max|ΔI|` vs the sequential
reference = 1.3e-5 A (floating-point → identical). Lanes are fixed to the NICE inverse
contract (5 in / 2 out) — a deliberate non-generic choice given the front can't be dynamic;
collapses to a lane-agnostic proxy if a generic vector-front/streaming-gather lands in MUSCLE3.

---

## End-to-end convergence — converging on 105084 (2026-06-18)

Status: the loop *converges* numerically on scenario 105084; it is **not** physics-validated.

`inverse_convergence/outer_convergence_loop.py` closes the outer Picard loop *inside*
MUSCLE3 (no shell-script RERUN). Topology: `loop -> lb (round-robin load balancer) ->
nice_inv[W] -> loop`; the loop assembles whole-trace equilibrium+core_profiles and drives
`torax` on F_INIT once per iteration; `torax.o_i -> viz`. (The concrete ymmsl for the
105084 dev run has absolute paths and is not tracked; templatize into the `lib/`
subworkflow templates for the repo.)

**Convergence fix — feed back the WHOLE TORAX output, matching `preprocess_data.sh
--rerun`** (which sets the next source to the previous `sink_torax`). Every field must
round-trip:
- equilibrium -> NICE inverse target (`_split` of the TORAX equilibrium),
- **core_profiles -> next TORAX F_INIT** (the original gap: reusing the *initial*
  core_profiles while the geometry evolved made geometry/profiles drift apart and diverge),
- **NICE output coils -> next NICE `pf_active` input**,
- wall / pf_passive / iron_core stay static.

With all three feedbacks (raw, no relaxation) it converges:
`max|ΔI|` 8188 -> 4866 -> 1185 -> 599 < tol(1000), **converged at iter 4** (105084, 10
slices, W=8). Feeding back only equilibrium diverges ~3×/iter and crashes.

Supporting actor changes (committed to their repos):
- TORAX (`torax-muscle3`, fork branch `feature/picard-restartable-actor`): restartable
  across reuses — reopen `db_out` per reuse, reset `last_communication` per reuse.
- visualization (`IMAS-MUSCLE3`, `feature/muscle3-0.9-v0.2-parallel-actors`): optional
  `trigger_in` F_INIT so the live monitor reuses once per outer iteration.

Launched on a compute node (sun, exclusive, W=8, TORAX 8 threads); TORAX transport
dominates wall-time (~1–3.5 min/iter, independent of #slices). **Follow-up:** confirm
physics correctness, then express this flat topology in the modular `lib/` templates.
express this validated flat topology in the modular `lib/` subworkflow templates.

## Option C — IMAS-aware load balancer + thin driver (2026-06-19)

The per-slice scatter/gather/assemble moved out of the driver into an IMAS-aware
`nice_lb.py`, so the driver (`outer_convergence_loop.py`, now the thin version) exchanges
only WHOLE-TRACE IDSs — one exchange per Picard iteration, no per-slice MUSCLE3 loop.

- `nice_lb.py`: whole-trace in (5 NICE lanes) -> `get_slice` -> round-robin scatter over W
  workers (worker-facing ports are vectors `[]`) -> gather FIFO-per-slot -> `put_slice`
  assemble -> whole-trace equilibrium + coils out (loop-facing ports scalar). Static lanes
  (wall, pf_passive, iron_core) forwarded whole to each call; equilibrium/pf_active sliced.
- `outer_convergence_loop.py` (thin): sends target + MD whole-trace to lb, gets back
  whole-trace equilibrium + coils, drives TORAX once, holds the prescribed boundary+Ip,
  checks coil convergence. No `set_port_length`, no per-slice send/receive.
- `workflow_c.ymmsl`: `loop -> lb -> nice_inv[W] -> lb -> loop`, `loop -> torax -> loop`,
  viz trigger. Passes `ymmsl Configuration.check_consistent()`.

Validated bit-identical to the per-slice driver (105084, 10 slices, W=8): `max|dI|`
6043 -> 691 < tol, converged at iter 2, exit 0. **Roadmap:** conduit filters (static-once
via `repeat`, reducers) once muscle3 implements filter *application* (absent in 0.10 and
develop — only parsed/flattened); Waveform-Editor in the loop + shape editor for variable
timestepping (the lb's get_slice-at-requested-times is the hook).

## Consolidation landed — `inverse_convergence` is the flat loop (2026-06-22)

The flat SEL-pipeline loop is now THE `inverse_convergence` workflow; the older/alternative
forms of the same NICE-inverse⇄TORAX approach were removed and the reusable assets folded in.

- **Pipeline + waveform editor**: `loop --target--> we --(+Ip,B0)--> lb(nice)
  --equilibrium--> torax --evolved--> loop` (+ `lb --coils--> loop`). The loop is a clean SEL
  submodel (one O_I pulse / one S pulse per iteration, 0 MMSF warnings); NICE's equilibrium
  goes straight to TORAX. The Waveform-Editor actor (`we`) overlays the designed Ip(t)+B0
  onto the target equilibrium in place (its `equilibrium_in` port selects overlay mode).
- **New TORAX port convention** (upstream `iterorganization/TORAX-MUSCLE3` develop, which now
  carries our restartable actor + a `last_communication` fix): `<ids>_in_f`/`_out_f`/`_out_i`.
- **Stacking, not placeholders-in-one-file**: `inverse_convergence/workflow.ymmsl.template`
  (topology + programs via `[BASEDIR_PLACEHOLDER]` + resources) is stacked with
  `scenarios/<shot>/settings.ymmsl` (the scenario paths, from `settings.ymmsl.template` with
  `[SUBDIR_PLACEHOLDER]`/`[SHOT_NR]`): `muscle_manager --start-all workflow.ymmsl settings.ymmsl`.
  `run_simulation.sh` drops the shell RERUN (convergence is internal) and runs the venv manager.
- **Assets relocated** into `inverse_convergence/` from the retired flagship: config templates,
  `preprocess/postprocess/create_runnable/run_simulation`, and `scenarios/` (5 shots). The loop
  writes its converged NICE result to `scenarios/<shot>/tmp/data/<shot>_out_nice`, which the
  evolutive controllers consume (their `preprocess_data.sh` repointed there).
- **Removed**: `torax_nice_self_consistent_transport/` (one-pass + shell-rerun; assets moved
  out), `inverse_convergence_loop/` (the A′ prototype), `lib/inverse_pass{,_loop,_parallel}`
  and the modular `inverse_convergence.ymmsl.template`/`scenarios/105084/scenario.ymmsl.template`.
- **Kept**: `evolutive`, `lib/{direct_cosim,programs}`, `torax_nice_{controller,rd_controller}`
  (evolutive roadmap), `torax_nice_utils`, `metis_*`.

Verified on 105084 (10 slices, W=8) via the stacked templates: converges at iter 2,
`max|dI|` 6043 -> 670 < tol, 0 MMSF warnings, `Simulation completed successfully` / exit 0.
