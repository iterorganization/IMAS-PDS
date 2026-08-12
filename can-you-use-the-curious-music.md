# Modularise the PDS workflows with yMMSL v0.2 nesting + custom implementations

## Context

`workflows/` holds **9 workflow definitions across two incompatible generations**:

| Gen | Files | Members |
|---|---|---|
| v0.1 | monolithic `workflow.ymmsl.template`, `[BASEDIR_PLACEHOLDER]` sed-expansion via `create_runnable_files.sh`, launched by `run_workflow.sh` → `run_simulation.sh` | `metis_{interpretative,predictive}_from_dina`, `metis_{interpretative,predictive}_nice_inverse_from_dina`, `torax_nice_controller`, `torax_nice_rd_controller` |
| v0.2 | `workflow.ymmsl` + `settings.ymmsl` + `scenarios/<shot>/settings.ymmsl`, `imports:` from `workflows/lib/`, `envsubst` via `bin/pds-run` | `inverse_convergence`, `prescribed_transport`, `evolutive` (half-migrated, not runnable) |

Duplication is mechanical and measurable:

- `metis_interpretative_from_dina` vs `metis_predictive_from_dina` — 89 lines, **identical except 5 booleans** (`metis.metis_external_data_{electron_temperature,electron_density,ion_temperature,charge_effective,ECRH}`) and whitespace. Same for the `*_nice_inverse_*` pair at 136/135 lines. The METIS block is copy-pasted 4×. Their `model.name`s are also **swapped**: `metis_interpretative_from_dina` declares `name: metis_nice_inv_from_dina_[SHOT_NR]` and `metis_predictive_from_dina` declares `name: metis_from_dina_[SHOT_NR]` — neither is right, so pick the new variant names deliberately rather than carrying these over. *(This duplication is measured but **not** removed by this work — see Scope.)*
- `torax_nice_controller` vs `torax_nice_rd_controller` — 204/191 lines, differ by `nice_evo`→`nice_evo_rd`, two extra `core_profiles` ports/conduits, and whether `temporal_coupler` is present.
- Inside `inverse_convergence`, the `load_balancer` + `nice_inv` pair is written twice.
- Shell: `create_runnable_files.sh` (2 bodies / 6 dirs), `run_simulation.sh` (3 / 6), byte-identical `config_nice.xml` in two of four dirs (`inverse_convergence` and `prescribed_transport`, md5 `3647fd4c…`; the two `torax_nice_*/config_nice.xml.template` differ from those and from each other), 5 near-copies of `config_torax.py`, two **divergent** copies of `convert_dina_data_to_input.py`, byte-identical `make_metis_from_dina_interpretative.m` in two dirs.

**Goals**, as agreed:

- **A. Structure** — 3 reusable core models; a variant is composition, not a copy of the graph.
- **B. Scenarios leave the code repo** — scenario preparation and plotting move to a separate `pds-scenarios` repo. **A scenario is primarily a waveform-editor yaml**; it may also carry its own data and solver config, or point at data held elsewhere by URI.
- **C. No wrapper** — a run is `muscle_manager --start-all <workflow.ymmsl> <scenario.ymmsl>`, typed directly. `bin/pds-run` and `run_workflow.sh` are deleted, not replaced.
- **D. Any scenario × any workflow** — the scenario file contains no workflow knowledge.
- **E. One `transport` hole, with room for more than one filler.** TORAX fills it now; METIS is deferred (see Scope).
- **F. The waveform editor owns the scenario's data pointers and waveforms.**

## Scope: METIS is deferred

**The four `metis_*_from_dina` workflows stay exactly as they are, on the v0.1 mechanism, and are not migrated in this work.** So are `lib/transport_metis.ymmsl`, `lib/metis_from_dina.ymmsl`, and the METIS half of Goal E.

**SUPERSEDED — both reasons for deferring turned out to be false.** `/home/yannick/projects/METIS/workflow/muscle3/mfile` settles it:

- **There is no coupling mode.** `metis4muscle3_port_list.m` declares ONE fixed superset of ports — clock / pulse_schedule / equilibrium / plasma_profiles / plasma_sources / core_profiles / core_sources across F_INIT, S, O_I and O_F — with the comment *"ports is only used if they are connected !"*. METIS adapts to whatever the workflow wires, like the generic IMAS actors.
- **`metis4muscle3`'s first argument is `debug_level`, not a mode.** The signature is `metis4muscle3(debug_level, checkpoint_on_off, port_name_legacy)`; 0 = none, 1 = Matlab logfile, 2 = + debugger stop on error, 3 = + keyboard stop. So the "contradiction" that motivated this whole section — `metis4muscle3(2)` appearing with two disjoint port sets — was never a contradiction. The argument has nothing to do with ports.
- **The Goal E physics gap does not exist.** The superset contains `equilibrium_in_f`, `core_profiles_in_f` and `core_sources_in_f` simultaneously, plus `equilibrium_out_f` and `core_profiles_out_f`. METIS's ports are a *superset* of the `transport` contract, so no union mode, no adapter, no `plasma_profiles`→`core_profiles` rename is needed.

METIS is therefore **not** gated on another team, and the work below has been done. Kept as a record of why the deferral was proposed and why it was wrong.

*(Aside worth acting on: the templates pass `debug_level=2`, which enables `dbstop if all error`. The docstring says production should use 0. Carried over unchanged for equivalence; change deliberately.)*

**In scope — 5 of the 9 workflows:** `prescribed_transport`, `inverse_convergence`, `evolutive`, `torax_nice_controller`, `torax_nice_rd_controller`. These are exactly the ones built on the `design` and `evolutive_*` cores, and they carry the whole of Goals A–D and F.

Consequences to hold onto, since they cut against the target layout below:

- **`run_workflow.sh` and `run_simulation.sh` survive**, serving only the four METIS dirs. `bin/pds-run` still goes, because all three of its workflows migrate. Goal C ("no wrapper") therefore lands for the migrated set and not for the repo as a whole — a two-mechanism repo in the interim, which is the price of the descope and should be stated in the README rather than glossed.
- **`metis_alone_utils/`, `metis_nice_utils/`, the four METIS `scenarios/`, their `create_runnable_files.sh` / `pre|postprocess_data.sh` / `*.template`, and `make_metis_from_dina_interpretative.m` all stay.** Step 9's deletion list is narrowed accordingly.
- **`lib/programs.ymmsl` declares no METIS programs.** The old METIS templates carry their own inline `implementations:`, so the split is clean — no shared file needs a METIS entry.
- **The `transport` hole stays**, and is still load-bearing without METIS: `inverse_convergence` fills it with `torax`, `prescribed_transport` prunes it to `null`. What is deferred is only the *second filler*.
- **`pds-scenarios` absorbs no METIS prep** — the `imas convert` + MATLAB build (item 5 under "What the prep tool absorbs") stays in PDS with the workflows it serves.

Picking it up later costs one file read. `metis4muscle3.m` is at `$DIR_METIS4MUSCLE3` on the target install; reading it settles the mode table, and everything from "Split METIS by coupling mode" through `lib/metis_from_dina.ymmsl` below is written and ready to execute against it. Only the `metis4muscle3(4)` union mode needs someone else.

---

## Mechanics

Read from `/home/yannick/projects/ymmsl-python` (0.17.1.dev0), a cached `libmuscle` 0.9.1 and `ymmsl` 0.16.0, `/home/yannick/projects/IMAS-MUSCLE3` (`main` @ `5b4d2be`), and waveform-editor 0.3.1. Everything below is verified against those sources **except** where marked "open question" — note that the ymmsl and libmuscle sources are at different versions, so a claim resting on both is an inference, not a reading. **Re-confirm against the deployed muscle3 0.10.0** — Verification 0.

### Nesting and pruning

`libmuscle/manager/hammer.py::flatten()`:

- `process_components()` — `cmp_path = parent_path + component.name`; **`if impl_ref is None: continue`**, so a disabled optional component or unfilled hole is skipped.
- `process_conduits()` — any conduit whose endpoint resolves to `None` is skipped. **Pruning is automatic and total.**
- `glue_partial_conduits()` — conduits at model ports are held on a "plate" and joined with the outside conduit. Model ports are extension cables, and **a conduit may join ports of different names** — this is what makes the METIS adapter work.
- ymmsl's `apply_custom_implementations()` copy-on-writes each model along the path, so one submodel instantiated twice is independently customisable.
- **A partial conduit with no counterpart outside is silently dropped** — a typo'd model port loses a connection with no error. Hence the flatten-diff in Verification 2.

### Settings resolution — the key to Goal D

`libmuscle/settings_manager.py::get_setting`:

```python
for i in range(len(instance), -1, -1):
    name = instance[:i] + setting_name if i > 0 else setting_name
```

Longest instance prefix first, falling through to a **bare global name**. So:

> **Unprefixed key = scenario-level default, seen by every instance at any nesting depth. Prefixed key = workflow-level override, wins for that instance.**

The v0.1 templates already exploited this (`xml_path:` and `python_config_module:` are unprefixed there). This is what lets a scenario file be workflow-agnostic, and it means nesting depth no longer constrains the design.

### The three prefixes — MEASURED

Run on **muscle3 0.10.0 + ymmsl 0.17.0**, the deployed pairing, via `ci/gate_probe.py` (2026-08-12). Re-run it on the target install to confirm, but the answers below are what this plan is written against.

| What | Correct key form | If you get it wrong |
|---|---|---|
| **Instance names** (settings prefixes) | `run.inner` — nesting path only, **no** root model name | `get_setting` falls through; silent |
| **`custom_implementations`** | `probe.run.inner` — root model name **required** | `resolve()` raises — the one loud failure |
| **`resources`** | `run.inner` — the **flattened instance name** | silently falls back to 1 thread |

Verbatim:

```
instances: ['collector', 'driver', 'run.inner']
conduits:  ['Conduit(driver.x_out -> run.inner.x_in)', 'Conduit(run.inner.y_out -> collector.y_in)']
pruning: ok (spare absent)

custom_implementations   probe.run.inner  -> accepted        run.inner -> REJECTED
resources                probe.run.inner  -> threads=1 (ignored)
                         run.inner        -> threads=7  <-- takes effect
```

So a component at root depth is bare (`driver`), one level down is `run.inner`, and **case setting keys are `run.<component>.<setting>`**. Pruning and cross-boundary conduit gluing both work.

**Correction to an earlier draft of this plan.** It claimed ymmsl 0.17 and `hammer.flatten()` contradict each other on `custom_implementations`, because `_component_paths()` seeds with `m.name` while `flatten()` seeds with `Reference([])`. There is no contradiction: `resolve()` applies `custom_implementations` and **clears** them (`resolver.py:402`) before `flatten()` ever runs — the probe prints `custom_implementations after resolve(): {}`. hammer's empty seed governs instance names only, which is why the two conventions differ without conflicting. `hammer.py:265` still seeds with `Reference([])` in 0.10.0.

**Two silent-failure modes survive**, and `ci/check_ymmsl.py` must cover both:

- A setting key at the wrong depth. `get_setting` walks `run.waveform_editor` → `run` → bare, and **never tries `waveform_editor.waveforms`**. No error; the actor takes a default or raises `KeyError` far from the cause.
- A `resources` key that matches no instance. `get_resources` logs at debug and returns 1 thread. Today's `resources: {nice_inv: {threads: 2}, torax: {threads: 8}}` becomes `run.solve.nice` and `run.transport` once nested — miss that and TORAX quietly runs single-threaded.

Note also that ymmsl-python HEAD (0.17.1.dev0) changed `_check_resources` to walk model-name-prefixed paths. On 0.17.0 that check is lenient and the runtime form above is the only one that matters, but if PDS moves to 0.17.1+ the checker and the runtime may want different forms — re-run the probe on any ymmsl upgrade.

### Nothing expands variables

No `expandvars`/`expanduser`/`os.environ` in ymmsl's loader, libmuscle's config handling, or waveform-editor. Settings values are used verbatim; the `${SCEN}`/`${SHOT}` in today's files are expanded by `pds-run`'s `envsubst`.

The exception is **programs**: `libmuscle/native_instantiator/run_script.py` generates a bash script per instance and emits `. {virtual_env}/bin/activate`, `module load {modules}`, `exec {command} {args}` into it — so shell variables *are* expanded there. `env:` values go through `Popen(env=…)` and are **not**.

| Field | Emitted as | Shell-expanded? |
|---|---|---|
| `modules`, `virtual_env`, `executable`, `args`, `script` | bash script lines | ✅ |
| `env` | `Popen(env=…)` dict | ❌ |
| `settings` values | passed to the actor verbatim | ❌ |

### `muscle_manager` CLI

`ymmsl_files...`, `--start-all`, `--run-dir`, `--log-level`, `--location-file`, `-m/--model`.

### The IMAS-MUSCLE3 actors

Settings vocabulary is small and entirely usable as unprefixed globals: `source_uri`, `sink_uri`, `sink_mode`, `dd_version`, `t_min`, `t_max`, `iterative`, `interpolation_method`, `plot_file_path`, `keep_alive`, `open_browser`, `port`.

- **`source`** declares O_I `<ids>_out` for every IDS name; `get_port_list()` filters to connected ports. With `iterative: true` it walks `t_array` slice by slice; with `iterative: false` it calls `db_entry.get()` — the whole IDS in one message. That whole-trace mode is what `loop`/`load_balancer` depend on.
- **`sink_source`** is a **time-aligned re-emitter**, not a static injector. `sink_uri` is optional; `source_uri` is required (`sanity_check_ports()` enforces "has output ports ⟺ has `source_uri`"). Each reuse, `handle_sink()` receives the connected `_in` ports and — with no `sink_uri`, as in all four PDS instances — **discards the data**, returning `(t_cur, t_next)`. `handle_source()` then does `get_slice(ids_name, time_requested=t_cur, …)` and sends `Message(t_cur, …, next_timestamp=t_next)`. **The trigger supplies the time coordinate.**
- **`recorder_component` is absent from `main` but present on `develop`** — and `setup_files/setup_imas_muscle3.sh` already installs `develop` by default (it takes the branch as its second argument). So `rec_nice`/`rec_torax` are fine as they stand; there is nothing to merge or re-pin.
- **`feature/ymmsl-path-entrypoints` ships the entry-point mechanism** — `[project.entry-points."ymmsl.module"] imas_muscle3 = "imas_muscle3.actors:ACTORS"`, where `ACTORS` is an f-string embedding `sys.executable`, with the README documenting `imports: - from imas_muscle3 import implementation source_component`. It is **not** on `develop`. It would let PDS import the six IMAS actors instead of declaring them, and drop `YMMSL_PATH` — worth adopting once it lands, but purely a convenience. Until then `lib/programs.ymmsl` declares them and `YMMSL_PATH` is exported once, as `bin/pds-run` does today.

---

## The layering that delivers Goal D

Four artifacts, each answering one question:

| Artifact | Answers | Lives in | Committed? |
|---|---|---|---|
| **Scenario** | *what is being simulated* | `pds-scenarios` | yes — the **reference waveforms**, its data pointers, optionally its own data and solver config. **No ymmsl.** |
| **Workflow** | *how it is simulated* | PDS `workflows/` | yes — structure and variant composition. Defaults only; no paths. |
| **Case** | *a known-good pairing of the two* | PDS `cases/` | yes — which scenario each waveform editor reads, **waveform refinements or overrides**, solver configs, default output, default physics knobs |
| **Run override** | *what I am changing today* | wherever you work | no — a handful of lines, or absent entirely |

`Configuration.update()` is last-wins per key, so these simply stack:

```bash
# the default case
muscle_manager --start-all $PDS/workflows/inverse_convergence/workflow.ymmsl \
                           $PDS/cases/105084_convergence.ymmsl

# the same case, with something changed
muscle_manager --start-all $PDS/workflows/inverse_convergence/workflow.ymmsl \
                           $PDS/cases/105084_convergence.ymmsl \
                           ./cold-start.ymmsl
```

**Committed files use `${PDS_REPO}` and `${SCENARIOS_REPO}`, never absolute paths.** This reverses an earlier decision in this plan, which said no committed file may contain a variable *because* nothing expands them. The premise was right — there is no `expandvars` in ymmsl, libmuscle, IMAS-MUSCLE3, IMAS-Python or Waveform-Editor, all five checked — but the conclusion was wrong: the fix is to add the expansion, not to hardcode paths.

`ci/patches/muscle3-expand-settings-env-vars.patch` (written and tested) expands environment variables in string setting values inside `muscle_manager.load_configuration`, the single place the CLI merges every yMMSL file. An undefined variable raises an error naming it rather than being passed through literally to fail somewhere far away. This restores what `bin/pds-run`'s `envsubst` did, with no wrapper — Goal C survives.

### The case file

```yaml
# cases/105084_convergence.ymmsl -- a runnable default: this scenario, this output
#
# Setting keys are `run.<component>.<setting>` -- nesting path, no root model name.
# Measured on muscle3 0.10.0 + ymmsl 0.17.0; see "The three prefixes" above.
ymmsl_version: v0.2
settings:
  run.waveform_editor.waveforms: /…/pds-scenarios/105084_literal/waveforms.yaml
  run.we_final.waveforms:        /…/pds-scenarios/105084_md_only/waveforms.yaml
  run.solve.nice.xml_path:       /…/pds-scenarios/105084_literal/config_nice.xml
  run.final_solve.nice.xml_path: /…/pds-scenarios/105084_literal/config_nice.xml
  run.transport.python_config_module: /…/pds-scenarios/105084_literal/config_torax.py
  run.sink_nice.sink_uri:  "imas:hdf5?path=/…/work/105084_convergence/out_nice"
  run.sink_torax.sink_uri: "imas:hdf5?path=/…/work/105084_convergence/out_torax"
  run.loop.max_iterations: 2
```

```yaml
# ./cold-start.ymmsl -- the whole override
ymmsl_version: v0.2
settings:
  run.loop.cold_start: true
  run.sink_nice.sink_uri: "imas:hdf5?path=./out_nice"
```

Because the case names instances, **each waveform editor gets its own scenario**. Two editors, two `*.waveforms` keys; a third later needs one more line and no change to the scenario store or to any shared naming convention. The same freedom covers the two NICE instances, which share a config today but need not.

Cases are the unit CI runs, so every committed pairing is known to resolve and to work. That is what makes the ad-hoc override safe to be hand-written: it is short, and everything it does not mention is already proven.

The settings fall-through in `settings_manager.py` is still worth knowing — a case can write a short key where a workflow has exactly one consumer and a fully-qualified one where it has several — but nothing in the design now *depends* on globals being unambiguous.

### Alternative: a self-contained case that imports its workflow

A case can name its workflow and be run alone:

```bash
muscle_manager --start-all cases/105084_convergence.ymmsl
```

```yaml
imports:
- from workflows.inverse_convergence.workflow import implementation inverse_convergence
```

This works, and the obvious objection to it is wrong. `resolver.py::load_resolve_module` calls `do_resolve()` on the *imported* file, which runs `apply_custom_implementations()` and then clears them (`resolver.py:402`) — **the imported model arrives already composed**, so a case importing a workflow is one line, not a copy of the variant composition. ymmsl's own fixtures do exactly this: `tests/ymmsl1/a/g.ymmsl` imports `test_model` from `a.e`, which carries its own `custom_implementations`. `find_impls()` pulls in every dependency model and program transitively, and `_root_models()` drops anything used as an implementation, so the imported workflow model is the sole root; `-m/--model` disambiguates if it ever isn't. The case can even re-compose on top, with paths rooted at the local name (`inverse_convergence.run.transport: …`).

The real cost is elsewhere: **`resolve_impl_imports()` copies only `models` and `programs`.** It never touches `settings` or `resources`, and `Implementation` has no field for either. So importing a workflow **silently discards that workflow file's `settings:` and `resources:` blocks** — including the `run.loop.max_iterations: 1` in the variant example above.

| | Stacking (`workflow.ymmsl case.ymmsl`) | Importing (`case.ymmsl` alone) |
|---|---|---|
| Workflow-level defaults & `resources:` | survive | **silently dropped** |
| Case is workflow-agnostic | yes | no — it names one workflow |
| Command line | two paths | one path |
| `YMMSL_PATH` needed | yes (for `lib.*`) | yes (repo root, for `workflows.*`) |

**Decision: stack.** Workflows must be able to carry defaults, and losing them without a diagnostic is the same silent-failure class this plan is trying to remove. The two forms compose, though, so if the one-path invocation is wanted for the common default, add a thin `runs/<name>.ymmsl` that imports the workflow and stacks the case on top — without moving every default into every case. Import module paths are dotted and resolved against `YMMSL_PATH` (`imports.py::module_path` → `a/b/c.ymmsl`), so `workflows.inverse_convergence.workflow` needs the repo root on the path, which costs nothing given `lib.*` already requires it.

### Waveforms: whole-file override, no merging

**Decision: a waveform override is a complete replacement.** `waveform_editor.waveforms` names exactly one file — either the scenario's reference waveforms or a case's override — and when a case overrides, the scenario's waveform yaml is not read at all for that editor. No merge, no layering, no upstream change.

The tool forces this today in any case: `Configuration.load_yaml(yaml_str)` (`waveform_editor/configuration.py:59`) takes a single YAML string, with no include, extends or merge, and `dump()` emits one document.

The cost is duplication, and it is measurable. `inverse_convergence/waveforms.yaml` is 66 lines, `scenarios/105084_literal/waveforms.yaml` is 90, and their `globals`, `machine_description` and `state` blocks — some 40 lines — are byte-identical. Only `targets` differs, where the literal variant replaces `{ref: input}` with explicit `{time: […], value: […]}` tendencies for r0, b0, Ip, `psi_boundary` and all 14 coils. An override must therefore restate the data pointers under `globals.imports`, which couples it to the scenario's data location.

**Consequence worth acting on: a full-replacement waveform file is indistinguishable from a scenario.** `105084_literal` is exactly that — a complete alternative pulse design, not a patch. So put complete designs in `pds-scenarios/` as sibling scenarios and let the case select one per editor; reserve override files inside `cases/` for genuinely run-shaped ones. This keeps `cases/` small and stops the same content existing under two names.

Pointing a *different* editor instance at a *different* file already works and needs nothing — that is how `we_final` gets machine-description-only waveforms.

*Later improvement, not required:* make `waveforms` accept a list merged last-wins per waveform path, mirroring how `muscle_manager --start-all` stacks yMMSL files and `Configuration.update()` merges them, so the system layers identically at every level. Worth raising upstream with the 40-line measurement as motivation; nothing here depends on it.

**Goal F — the waveform editor is the scenario.** The two IMAS entries (plasma input + machine description) are named inside `waveforms.yaml` under `globals.imports` (`input`, `input_md`), exactly as `scenarios/105084_literal/waveforms.yaml` already does, together with `machine_description:`, `state:` and `targets:`. So no `source_uri` appears in any ymmsl, and the WE feeds the MD lanes over its `o_f` ports — already how `prescribed_transport` and `inverse_convergence`'s main path work (neither contains a `sink_source`).

**Absolute URIs need no templating.** `md_collections/basic.env` already hardcodes `imas:hdf5?path=/work/imas/shared/imasdb/ITER_MD/3/111001/203/`, so naming data by absolute URI is established practice here. A scenario's `waveforms.yaml` may point at a shared store or at a `data/` directory it carries itself; either way it is committed verbatim, with no `.in` template, no prep-time materialisation and no `envsubst`. The variable problem disappears rather than being managed.

### Where `sink_source` survives

Now that its semantics are clear (time-aligned re-slicing, not static injection), the four instances split:

| Instance | Job | Fate |
|---|---|---|
| `source_nice` (metis_*) | inject the 4 NICE lanes, sliced at METIS's timestamp | **unchanged for now** — deferred with METIS; becomes the WE's MD exports when those workflows migrate |
| `sink_source` (torax_nice_*) | copy MD into the TORAX output entry | **replaced** by the WE's MD exports |
| `md_final` (inverse_convergence) | MD for the post-loop NICE pass | **replaced** by a second WE instance (`we_final`), so MD has one mechanism everywhere |
| `sink_source_nice` (torax_nice_*) | re-slice a *NICE output* entry at the live timestamp for the plotter | **kept** — genuinely a re-sampler, not MD injection |

### Outputs

Sink URIs are absolute and stated in the case, so a default run writes to a predictable place and an override can redirect it in two lines. Relative URIs under `--run-dir` would be tidier and remain worth testing, but nothing depends on them.

---

## Target layout

```
workflows/
  lib/                              # the reusable models -- 3 cores + adapters
    programs.ymmsl                  # only what IMAS-MUSCLE3 does not provide
    design.ymmsl                    # core model: inverse / pulse design
    evolutive_direct.ymmsl          #   forward co-sim, direct equilibrium exchange
    evolutive_coupled.ymmsl         #   forward co-sim via temporal_coupler
    evolutive_rd.ymmsl              #   forward co-sim, resistive-diffusion port set
    nice_inverse.ymmsl              # submodel: load_balancer + N× nice_inv
    # DEFERRED: metis_from_dina.ymmsl, transport_metis.ymmsl -- see Scope
    actors/
      outer_convergence_loop.py     # moved from inverse_convergence/
      nice_load_balancer.py         # moved from inverse_convergence/
      temporal_coupler.py           # moved from torax_nice_utils/
  prescribed_transport/workflow.ymmsl     # ~12-line variant workflows
  inverse_convergence/workflow.ymmsl
  evolutive/workflow.ymmsl
  torax_nice_controller/workflow.ymmsl
  torax_nice_rd_controller/workflow.ymmsl
  metis_interpretative_from_dina/         # UNCHANGED -- v0.1, own scripts + templates
  metis_predictive_from_dina/             #   "
  metis_interpretative_nice_inverse_from_dina/
  metis_predictive_nice_inverse_from_dina/
  metis_alone_utils/  metis_nice_utils/   # UNCHANGED -- serve the four above
cases/                                    # committed, CI-checked default pairings
  105084_prescribed.ymmsl
  105084_convergence.ymmsl
  105073_evolutive.ymmsl
  105073_controller.ymmsl
  ...
ci/check_ymmsl.py
run_workflow.sh                           # KEPT -- now serves only the four METIS dirs
```

For the five migrated workflows: no `bin/`, no `scenarios/`, no `*.template`, no `pre/postprocess_data.sh`, no `utils/`, no `torax_nice_utils/`. The METIS dirs keep all of theirs.

**Variant is the workflow.** Each `workflows/<name>/workflow.ymmsl` is a thin root model: one component wrapping a `lib/` core model, plus `custom_implementations` choosing the blocks and any workflow-specific prefixed settings. Example:

```yaml
ymmsl_version: v0.2
imports:
- from lib.design import implementation design
- from imas_muscle3 import implementation source_component
models:
  prescribed_transport:
    description: Single-pass inverse solve against a prescribed boundary.
    components:
      run: {implementation: design, ports: {}}
custom_implementations:
  prescribed_transport.run.transport:   null
  prescribed_transport.run.final_solve: null
  prescribed_transport.run.we_final:    null
  prescribed_transport.run.validator:   null
  prescribed_transport.run.sink_torax:  null
  prescribed_transport.run.rec_torax:   null
settings:
  run.loop.max_iterations: 1
```

Adding a variant is a new ~12-line file, and it needs no new concept: it *is* a workflow.

Nesting under `run.` is free for anything a scenario states as an **unprefixed global** — those are seen at any depth. It is *not* free for the prefixed keys a case must write to distinguish two instances of the same program (the two waveform editors, the two NICE instances): those carry the full instance path, so their depth is fixed by this nesting and by whatever the Gate finds `flatten()` prepends. Keep the wrapper component named `run` in every workflow so that path is the same everywhere.

The `custom_implementations` keys above are written in the ymmsl ≥ 0.17 convention (root model name first), which its test fixtures confirm; the Gate re-checks that `flatten()` on the deployed muscle3 agrees.

---

## `workflows/lib/programs.ymmsl`

The installed IMAS-MUSCLE3 (`develop`) provides `source_component`, `sink_component`, `sink_source_component`, `olc_component`, `accumulator_component`, `visualization_component` and `recorder_component`. Declare those here in the short form and resolve them via `YMMSL_PATH`; switch to `imports: - from imas_muscle3 …` if the entry-point branch lands. Beyond them PDS declares:

- `waveform_editor` — from Waveform-Editor's own entry point if it has one, else `virtual_env` + `executable: waveform-editor`, `args: actor`.
- `nice_inv`, `nice_evo`, `nice_evo_rd`, `torax` — `script:` blocks, carried over verbatim from `lib/local_programs.ymmsl` (already correct: bash expands their paths).
- `magnetic_controller` — **must** use a `script:` block, since its `env:` entries reference install paths and `env:` is not expanded. (`metis_transport` and `metis_evo` would need the same treatment; both are deferred with METIS, and the old templates carry their own inline `implementations:`, so no METIS entry belongs in this file yet.)
- `loop`, `load_balancer`, `temporal_coupler` — the three PDS-owned actors, run in the IMAS-MUSCLE3 venv (all import `imas`).

Drop the unreferenced `convergence_driver` and `dispatcher`. **Declare `ports:` on the fixed-signature programs** — `nice_inv`, `nice_evo`, `nice_evo_rd`, `loop`, `load_balancer`, `temporal_coupler`, `magnetic_controller` — so `_check_consistent_ports` turns a wrong hole fill into a static error. Do **not** declare ports on the generic IMAS actors; they declare a port per IDS name and filter by connection.

**Correction found while writing the file: `torax` is not fixed-signature either.** It has two incompatible port sets in this repo and takes no mode argument, so like the generic actors it adapts to what is connected:

| Use | Ports |
|---|---|
| design co-sim (`inverse_convergence`) | `f_init: [equilibrium_in_f, core_profiles_in_f, core_sources_in_f]`, `o_f: [equilibrium_out_f, core_profiles_out_f]` |
| time-stepping co-sim (`torax_nice_{,rd_}controller`) | `f_init: [equilibrium_in_f, core_profiles_in_f]`, `s: [equilibrium_in_s]`, `o_i: [equilibrium_out_i, core_profiles_out_i]` |

Declaring either set makes the other a hard error, so `torax` ships with no `ports:`. This is the same shape as the METIS problem, in the program the plan assumed was the safe one — check `torax_muscle3.torax_actor` before declaring or splitting. It also means **the Goal E hole is not statically type-checked**: a wrong `transport` fill will not be caught by `check_consistent()`.

**`supported_settings` does not do what this plan claimed.** `_check_supported_setting` (`configuration.py:547-575`) iterates the settings an implementation *declares* and type-checks any that are set; a misspelled or mis-prefixed key matches nothing and is silently ignored. It catches wrong *types* on correctly-named settings, nothing more. It is therefore omitted from `lib/programs.ymmsl`, and catching a bad key falls entirely to `ci/check_ymmsl.py` cross-checking case keys against flattened instance names.

**Split METIS by coupling mode — DEFERRED (see Scope), and blocked on `metis4muscle3.m` when picked up.** The repo shows at least three distinct METIS port shapes, so one `metis` program with one declared port set is impossible and the program must be split. But **the mode↔port mapping cannot be inferred from the yMMSL files, because they contradict each other**:

- `ymmsl_files/metis_nice_inv_actor.ymmsl.template` declares `f_init: [clock_in_f]` with O_I outputs (`equilibrium_out_i`, `pulse_schedule_out_i`, `plasma_profiles_out_i`, `plasma_sources_out_i`) — while invoking `metis4muscle3(**2**)` at line 64.
- The four `metis_*_from_dina/workflow.ymmsl.template` also invoke `metis4muscle3(**2**)`, but declare a disjoint set: `f_init: [pulse_schedule_f_init, pulse_schedule_in_f, core_profiles_in_f, core_sources_in_f]`, `o_f: [equilibrium_out_f, pulse_schedule_out_f, plasma_profiles_out_f, plasma_sources_out_f, summary_out_f]`.
- `ymmsl_files/test_metis_actor.ymmsl` invokes `metis4muscle3(1)` with `f_init: [equilibrium_input_f]`, `o_f: [equilibrium_output_f]` — note `input`/`output`, not `in`/`out`.
- Mode 3 appears in the repo only on commented-out lines.

So one argument value maps to two disjoint port sets. Either the argument does not select the port set the way this plan assumed, or one of those files is stale. **Read `metis4muscle3.m` (not present on this machine) and derive the table from it before splitting the program or declaring `ports:` on any METIS entry** — a wrong table is worse than none, since a declared port set that does not match reality turns into either a spurious static error or, via an unwired port, a silently dropped conduit.

---

## Goal E: one `transport` hole — PARKED

The hole exists and TORAX fills it; `prescribed_transport` prunes it to `null`. A second
filler is not built.

**METIS's ports fit the contract but its coupling does not.** `metis4muscle3_port_list.m`
declares one fixed superset — including `equilibrium_in_f`, `core_profiles_in_f`,
`core_sources_in_f`, `equilibrium_out_f` and `core_profiles_out_f` — and uses only what is
connected, so `{run.transport: metis}` resolves and flattens cleanly. It would still be
wrong: the hole exchanges a whole trace per Picard iteration, while METIS steps in time
(`while ~metis_exit` over `t_cur`, time source chosen from a connected port by
`get_workflow_mode.m`, external data accumulated slice by slice). Matching port names say
nothing about matching message granularity.

An adapter would therefore need a whole-trace ↔ per-slice conversion on both sides, not a
port rename. `sink_source` already does trace→slice, and `accumulator_component` /
`lib/actors/temporal_coupler.py` already do slice→trace. Before building it, establish
METIS's per-operator granularity from `send_muscle3_messages.m` — whether O_F carries an
accumulated trace while O_I carries slices decides whether one side or both need adapting.

Corrections to earlier drafts, so they are not repeated: `metis4muscle3(N)`'s first
argument is `debug_level` (0 none, 1 logfile, 2 +debugger stop, 3 +keyboard), not a
coupling mode; there is no mode↔port mapping and no `metis4muscle3(4)` union mode to ask
for; and no `plasma_profiles`→`core_profiles` rename is needed, because METIS has
`core_profiles_out_f`.

## The three core models in `lib/`

### `lib/design.ymmsl`

| Component | Implementation | Optional |
|---|---|---|
| `source` | `source_component` | no |
| `loop` | `loop` | no |
| `waveform_editor` | `waveform_editor` | no |
| `solve` | `nice_inverse` submodel | no |
| `transport` | hole → `torax` (later also `transport_metis`) | yes |
| `sink_nice`, `rec_nice` | `sink_component`, recorder | no |
| `sink_torax`, `rec_torax`, `validator` | | yes |
| `we_final` | `waveform_editor` (replaces `md_final`) | yes |
| `final_solve` | `nice_inverse` submodel | yes |

Conduits carry over from `inverse_convergence/workflow.ymmsl` with `load_balancer`/`nice_inv` → `solve`, `load_balancer_final`/`nice_final` → `final_solve`, `md_final` → `we_final`:

```
source.{equilibrium,core_profiles}_out -> loop.*_in_f
loop.{equilibrium,core_profiles}_out_i -> waveform_editor.*_in
waveform_editor.{equilibrium,wall,pf_active,pf_passive,iron_core}_out -> solve.*_in
waveform_editor.core_sources_out  -> transport.core_sources_in_f
waveform_editor.core_profiles_out -> transport.core_profiles_in_f
solve.equilibrium_out   -> [transport.equilibrium_in_f, rec_nice.equilibrium_in, sink_nice.equilibrium_in]
solve.pf_active_out     -> [loop.pf_active_in_s, rec_nice.pf_active_in, sink_nice.pf_active_in]
transport.equilibrium_out_f   -> [loop.equilibrium_in_s, rec_torax.equilibrium_in]
transport.core_profiles_out_f -> [loop.core_profiles_in_s, rec_torax.core_profiles_in]
loop.equilibrium_out_f        -> sink_torax.equilibrium_in
loop.core_profiles_out_f      -> sink_torax.core_profiles_in
loop.pf_active_out_f          -> [sink_torax.pf_active_in, final_solve.pf_active_in, we_final.pf_active_in, validator.pf_active_in]
loop.equilibrium_target_out_f -> final_solve.equilibrium_in
we_final.{wall,pf_passive,iron_core}_out -> final_solve.*_in
```

Pruning `transport` leaves the `prescribed_transport` graph plus a single-pass loop; `loop.pf_active_in_s` is still fed by `solve`, while `loop.{equilibrium,core_profiles}_in_s` go unconnected — handled by the actor change below.

### `lib/evolutive_{direct,coupled,rd}.ymmsl`

Three files, not one with a swappable link. `temporal_coupler.py` **does not interpolate** — `DataCache.get_data()` is a zero-order hold returning the bytes verbatim (*"A more advanced, model-specific coupler would interpolate here"*), so no pass-through actor is needed; but it handles exactly **two peers with one lane each** (`S: [a_in, b_in]`, `O_I: [a_out, b_out]`), and the RD variant has **two** transport→NICE O_I→S lanes. Routing one through the coupler and the other directly would desynchronise them.

| File | Equilibrium exchange | NICE peer | Replaces |
|---|---|---|---|
| `evolutive_direct` | direct both ways | `nice_evo` | `evolutive` |
| `evolutive_coupled` | via `link` (`temporal_coupler`) | `nice_evo` | `torax_nice_controller` |
| `evolutive_rd` | direct + `core_profiles_o_i → core_profiles_s` | `nice_evo_rd` | `torax_nice_rd_controller` |

~6 conduit lines of overlap out of ~35; each file internally single-wired. This is what `lib/direct_cosim.ymmsl.template`'s own header recommended. Components: `source` and `transport` holes, the NICE peer, `waveform_editor` (replacing `sink_source` for MD), `sink_source_nice` (kept — see above), `sink_nice`, `sink_torax`, and optional `magnetic_controller`, `sink_controller`, `visualization_nice`, `visualization_torax`. Port names normalise to the `_f_init`/`_s` convention already used in `direct_cosim.ymmsl.template`.

### `lib/metis_from_dina.ymmsl` — DEFERRED (see Scope)

Retained as the design for when METIS is picked up; nothing in this section is built now.

`transport` (= `transport_metis`) → optional NICE branch (`nice_inv` bare, fed MD by the `waveform_editor`) → `sink_metis`. The four old workflows become four variant workflows differing in `custom_implementations` (NICE branch on/off) and the 5 `metis_external_data_*` settings; the ~20 shared METIS defaults live once here.

*Not folded into `design`:* the coupling order is reversed (METIS runs first and NICE fits coils to its equilibrium; in `design` NICE runs first and transport consumes its equilibrium). They converge to the same fixed point but a single pass differs, so merging would not be equivalence-preserving.

### `lib/nice_inverse.ymmsl`

Port names from `nice_load_balancer.py:68-73` (F_INIT `{lane}_in`, O_I `{lane}_scatter[]`, S `{lane}_gather[]`, O_F `{lane}_out_f`; `FWD_LANES = equilibrium, wall, pf_active, pf_passive, iron_core`, `RES_LANES = equilibrium, pf_active`):

```yaml
models:
  nice_inverse:
    ports:
      f_init: [equilibrium_in, wall_in, pf_active_in, pf_passive_in, iron_core_in]
      o_f:    [equilibrium_out, pf_active_out]
    components:
      load_balancer:   # implementation: load_balancer
      nice:            # implementation: nice_inv, multiplicity: [1]
    conduits:
      equilibrium_in: load_balancer.equilibrium_in            # model port -> component (×5)
      load_balancer.equilibrium_scatter: nice.equilibrium_in  # (×5)
      nice.equilibrium_out: load_balancer.equilibrium_gather
      nice.pf_active_out:   load_balancer.pf_active_gather
      load_balancer.equilibrium_out_f: equilibrium_out
      load_balancer.pf_active_out_f:   pf_active_out
```

Used twice in `design` (`solve`, `final_solve`), replacing the hand-copied `load_balancer_final`/`nice_final` pair; settings stay independent via `solve.nice.*` / `final_solve.nice.*`. **Not used by METIS** — inserting a load balancer would turn one whole-trace call into per-slice scatter/gather, which is not equivalence-preserving. **Limitation:** `multiplicity` is a model property, not overridable from an overlay, so all uses share one worker count (both are `[1]` today).

---

## Scenario repository

```
pds-scenarios/                    # separate git repo
  105084_literal/
    waveforms.yaml                # THE scenario: globals.imports {input, input_md}
                                  #   + machine_description / state / targets
    config_nice.xml               # optional: solver config, when it differs from the default
    config_torax.py               # optional
    info.md                       # provenance: DINA source URI, MD collection, n_timeslices, tool commit
    data/  in/  in_md/            # OPTIONAL -- a scenario may carry its own IDSs
  105084_md_only/                 # a machine-description-only scenario, for a second
    waveforms.yaml                #   waveform editor in the same run
  tools/
    prepare                       # DINA -> IDS conversion
    dina2pds/   convert_dina_data_to_input.py  preprocess_dina.py  preprocess_machine_description.py
    md_collections/basic.env
```

`make_metis_from_dina_interpretative.m` stays in PDS (`metis_alone_utils/`, `metis_nice_utils/`) with the workflows it serves; it moves here when METIS does, and the byte-identical duplicate is reconciled then.

**A scenario is a pulse design, not a dataset, and holds no ymmsl.** Its centre of gravity is `waveforms.yaml`; whether the IDSs sit beside it in `data/` or in a shared store like `/work/imas/shared/…` is per-scenario and invisible to the workflow, because either way `globals.imports` names them by absolute URI. Scenarios sharing a dataset point at the same URI, so one prepared dataset backs many pulse designs without being copied. Nothing in a scenario refers to a workflow, an instance name, or a MUSCLE3 setting — a scenario is just a design that some run may choose to feed to some editor.

This also means **git-lfs is only needed for the scenarios that carry data**, not for the repo as a whole — `.gitattributes` must still be committed before the first such dataset is added, or payloads enter normal git history irreversibly.

### What the prep tool absorbs

The 8 `preprocess_data.sh` do five separable things: (1) DINA→PDS input via `convert_dina_data_to_input.py` — note `find_interesting_time_slices()` computes energy/Bv weightings then discards them (`f = ft`, `preprocess_dina.py:176`), so selection is uniform-in-time; and `preprocess_pf_active()`'s docstring says it exists **only for validation plots**, so check whether it is still needed. (2) the `cp -r` hdf5 read-mode workaround → prep writes both copies. (3) `torax_nice_*` copying `inverse_convergence`'s `_out_nice` → the scenario points at the previous run's output directly. (4) `--rerun` bookkeeping → a `source_uri` override. (5) the METIS `imas convert` + MATLAB build — **not absorbed**; stays in PDS with the four unmigrated METIS workflows, so only 4 of the 8 `preprocess_data.sh` are retired now.

The 8 `postprocess_data.sh` are **only** plotting (`plot_validation*.py`) — the 4 belonging to migrated workflows are deleted, plotting having moved to a separate tool; the METIS 4 stay with their workflows.

---

## Python and upstream changes

1. **`workflows/lib/actors/outer_convergence_loop.py`** — make the transport leg optional: guard the three `S` receives at lines 189–191 with `inst.is_connected(...)`; when `equilibrium_in_s` is unconnected, still receive `pf_active_in_s`, leave `target`/`cp` unchanged, and break after one iteration, emitting the design target on `equilibrium_out_f`. ~10 lines. This is what makes `prescribed_transport` a 12-line variant rather than a separate graph.
2. **`workflows/lib/actors/temporal_coupler.py`** — drop the duplicated import block and stale accumulator docstring (lines 1–38: two `import logging`, two `from libmuscle import …`, an unused `from libmuscle.runner import run_simulation`); replace the per-exchange `print()` at lines 261–272 with `logger.debug`.
3. **IMAS-MUSCLE3** — nothing required. `setup_files/setup_imas_muscle3.sh` already defaults to `develop`, which ships every actor the new models use, `recorder_component` included. Import the six IMAS actors via `ymmsl.module` entry points only once those land on `develop`; until then keep `YMMSL_PATH` and declare them in `lib/programs.ymmsl`.
4. **METIS** — nothing required, because METIS is out of scope. When picked up: read `metis4muscle3.m` for the mode table, then ask for a `metis4muscle3(4)` union mode (Goal E). This is the only item on this list owned by another team, which is why it is deferred.
5. **MUSCLE3** — `ci/patches/muscle3-expand-settings-env-vars.patch`, so committed cases use `${PDS_REPO}` / `${SCENARIOS_REPO}` instead of absolute paths. ~30 lines in `muscle_manager.load_configuration`; undefined variables become a named hard error. Worth upstreaming — every MUSCLE3 user hardcoding install paths into settings has this problem.

   **Note what this replaces.** Today's ymmsl files appear to support `${SCEN}`/`${SHOT}`/`${PDS_REPO}` in settings, and they do work — but the expansion is `bin/pds-run`'s `envsubst`, at three call sites (lines 69, 74, 85), which writes expanded copies to a temp dir and hands *those* to the manager. Stock muscle3 0.10.0 (the newest that exists) passes setting values through verbatim; confirmed by running `load_configuration` on a file containing `${TESTROOT}` and getting `'${TESTROOT}/data/in'` back. Deleting `bin/pds-run` for Goal C therefore removes the expansion, and this patch is what puts it back without a wrapper.

   **Decision (kept under review):** carry the patch. **If it is not merged in reasonable time, fall back to a thin `envsubst` wrapper** — that reinstates a wrapper against Goal C, but needs no patched muscle3 and is the mechanism that already works today. The trigger for switching is upstream inaction, not a technical failure. Recorded in `setup_files/apply_patches.sh`.
6. **Waveform-Editor — two things required, both now established.**

   **Branch.** The `globals.imports` mechanism every PDS `waveforms.yaml` depends on exists only on **`feature/reference-tendency-old`**. It is *not* on `develop` (HEAD `8886b04`), where `YamlGlobals` has `machine_description` as an IDS→URI dict and no `imports` at all — loading any PDS waveform file against develop fails with `'imports' is not a parameter of YamlGlobals`. `setup_files/setup_waveform_editor.sh` defaults to `develop` and must be changed, or PDS is pinned to a branch nobody has recorded.

   **Patch.** `ci/patches/patches/waveform-editor-relative-imports.patch` (written and tested) makes a relative `path=` in an import URI resolve against the directory the configuration was loaded from, so scenarios carry no absolute paths. It adds a `base_dir` to `WaveformConfiguration` and `ImportResolver`; absolute URIs, `{port: ...}` imports and string-loaded configurations are unaffected. All 290 Waveform-Editor tests pass with it applied, including the MUSCLE3 integration tests. Worth upstreaming.

   Overrides remain whole-file replacements, which the single-document loader supports. A list-merge for `waveforms` is still a later improvement, not a dependency.

---

## Execution order

0. Verification 0 gate.
1. `pds-scenarios` — **the repo now exists at `../pds-scenarios`**: `git init` on branch `main` (PDS is on `master`), no commits, no `.gitattributes`. So the git-lfs ordering constraint is live *now*, before anything is added: if any scenario will carry its own IDSs, run `git lfs install` and commit `.gitattributes` as **the first commit**. After a data blob lands in normal git history it cannot be removed without a rewrite. If no scenario will carry data — everything by URI into a shared store — skip lfs entirely and record that decision in the repo README, because it is hard to reverse cheaply later.

   **Data generation: 105084 done, 105073 not.** Generated locally with the repo's own
   converter from raw DINA pulled read-only off SDCC (`iter:` → `sdcc-login03`); the raw
   inputs are staged in `run/raw/` (gitignored). `pds-scenarios/105084/data/{in,in_md}` now
   holds 40 timeslices (one of 41 rejected as non-viable), DD 4.1.1, 5.6 MB. Verified by
   exporting both scenario configs through Waveform-Editor with the real data: they produce
   exactly the IDS sets their workflows' editors declare.

   105073 has scenario configs on SDCC but **no prepared data**, and its DINA source is an
   MDSplus tree. Generating it needs either a writable run on SDCC or an MDSplus-capable
   local reader.

   **Two pre-existing bugs in the prep scripts had to be fixed to get this far**, both
   DD-version handling and both invisible on SDCC:
   - `preprocess_dina.py::preprocess_pf_active` converted only the DINA slice to
     `DD_VERSION`, not the machine-description slice. Both are stored as DD 3.39.0, and DD4
     renamed `coil/name` from `"Central Solenoid 3U (CS3U)"` to `"CS3U"`, so the name
     assertion compared converted against unconverted and failed on the first timeslice.
   - `preprocess_machine_description.py::preprocess_pf_passive` was the only reader calling
     `get()` without `autoconvert=False`. The pf_passive MD is DD 3.38.1; auto-converting it
     to the environment's default DD fails outright when that default is a different major
     version (4.1.1 here). The other three readers already read raw and convert explicitly.

   Neither shows up on SDCC because the module-loaded IMAS-Python defaults to a DD 3.x, so
   the version gaps never open. They are environment-dependent, not machine-specific.

   Then: move `tools/` across (reconciling the two divergent `convert_dina_data_to_input.py`, but **not** the METIS MATLAB build — that stays in PDS, see Scope), write `tools/prepare`, and land `105084_literal` as the first scenario. Its `waveforms.yaml` already exists in PDS, but needs **two** fixes, not one: the `${SCEN}`/`${SHOT}` URIs replaced with absolute ones, **and its missing `machine_description:` key restored**. A malformed comment swallowed it —

   ```yaml
   # Static machine-description referencemachine_description:
     wall/*:
   ```

   — so the four MD entries currently parse as members of `globals`:

   ```
   top keys:     ['globals', 'state', 'targets']
   globals keys: ['dd_version', 'imports', 'wall/*', 'pf_passive/*', 'iron_core/*', 'pf_active/*']
   ```

   `inverse_convergence/waveforms.yaml` and `prescribed_transport/waveforms.yaml` carry the same mangled comment but survived because the real key follows on the next line. This means `105084_literal` has never run with its machine description — factor that into the reference outputs captured in Verification 3. If that scenario is to carry its own data, `git lfs install` and commit `.gitattributes` first.
2. **DONE.** `origin/develop` provides all seven actors the new models name — `source_component`, `sink_component`, `sink_source_component`, `olc_component`, `accumulator_component`, `visualization_component`, `recorder_component`.
3. **DONE.** `workflows/lib/programs.ymmsl` (no METIS entries; no `ports:` on `torax` — see above; no `supported_settings`, which does not catch misspellings) + the three actors moved to `workflows/lib/actors/`. Legacy references in `lib/local_programs.ymmsl`, `lib/programs.ymmsl.template` and `torax_nice_controller/workflow.ymmsl.template` were repointed so nothing breaks mid-migration.
4. **Structurally done; needs a case + data to be green.** `lib/nice_inverse.ymmsl` + `workflows/prescribed_transport/workflow.ymmsl`. Resolves, passes `check_consistent(selected_model=...)`, and flattens to 6 instances / 17 conduits with `solve.load_balancer` and `solve.nice` correctly glued across the model boundary and `resources: {solve.nice: {threads: 2}}` reaching the nested instance. Built as its own small model over `nice_inverse` (the documented fallback), not yet as a `design` variant — that decision belongs to step 5. **Note it now has a load_balancer where it had a bare `nice_inv`**, so its Verification 2 diff is expected to be non-empty.
5. **DONE.** `lib/design.ymmsl` + the `inverse_convergence` variant + the `outer_convergence_loop.py` change.

   **The flatten-diff is empty.** New `inverse_convergence` flattens to 14 components and 45 conduits; so does the old hand-written definition, and after renaming (`run.solve.*`→`load_balancer`/`nice_inv`, `run.final_solve.*`→`*_final`, `run.we_final`→`md_final`, `run.transport`→`torax`) the two sets are *identical* — no conduit added, dropped or rerouted. Verification 2 therefore passes exactly for this workflow: the composed model reproduces the hand-written coupling.

   Pruning verified too: nulling `transport`/`final_solve`/`we_final`/`validator`/`sink_torax`/`rec_torax` leaves 7 components and 21 conduits, with every conduit touching a pruned component gone and `loop.pf_active_in_s` still fed.

   The actor change probes `is_connected("equilibrium_in_s")` once per reuse and, when the transport hole is pruned, breaks after one iteration and emits the design target on `equilibrium_out_f` (`torax_eq` is `None`, so `final_eq` falls back to `target`).

   ***`prescribed_transport` is deliberately NOT converted to a `design` variant.*** It works today as its own small model over `nice_inverse` (6 components, 17 conduits) and matches its old graph. As a `design` variant it would cost an extra `loop` process, and — measured, not assumed — it would also connect `waveform_editor.core_profiles_in`, so the scenario would have to supply a `core_profiles` port-import that a single inverse pass does not otherwise need. That changes the scenario contract for no functional gain. The plan already allows this ("Fallback: its own small model built from the same `nice_inverse` submodel"); revisit only if a second pruned variant appears and the duplication starts to bite.
6. **DONE, but partly on inference — see the caveat.** `lib/metis_dina.ymmsl` + `lib/transport_metis.ymmsl` + the METIS variants. Built ahead of reading `metis4muscle3.m`, on the explicit understanding that it can be reverted.

   **Goal E is parked** — see that section. What follows is the from-DINA consolidation only.

**Grounded, and verified by flatten-diff:** `lib/metis_dina.ymmsl` reproduces the old templates exactly — `metis_from_dina` 3 components / 9 conduits and `metis_nice_inverse_from_dina` 6 / 17, both **zero difference** against `metis_interpretative_from_dina` and `metis_interpretative_nice_inverse_from_dina` (modulo `source_nice` → `waveform_editor`, which is the intended change). All four old templates share one port set, so nothing here is inferred.

   **Four workflows became two.** Interpretative vs predictive is five settings, not a graph difference, and settings live in cases — so `metis_from_dina` (NICE branch pruned) and `metis_nice_inverse_from_dina` (branch present) cover all four, with the distinction carried by four cases.

   **No adapter, no cases, no scenario data.** `lib/transport_metis.ymmsl` was written speculatively and has been deleted; the four METIS cases and the fabricated `config_nice.xml` are gone too. `source_nice` stays a `sink_source` rather than becoming a waveform editor, so the model is exactly equivalent to what it replaces. What remains is structure only, unused until METIS is picked up.

   The `metis` program carries no `ports:`, for the same reason as `torax` and more so — `metis4muscle3(2)` appears with two disjoint port sets in this repo.
7. **DONE.** `lib/evolutive_{direct,coupled,rd}.ymmsl` + the three variant workflows.

   ***`evolutive` has been dropped.*** It is not a valid graph: `magnetic_controller.pf_active_out_i` is the only sender to `nice_evo.pf_active_s`, NICE receives on that port unconditionally, and the workflow pruned the controller — so the run aborts with *"Tried to receive on port pf_active_s which is disconnected, and no default value was given"*. Confirmed at runtime on SDCC.

   The old definition had the identical hole (`evolutive.cosim.magnetic_controller: null` in its scenario template), which is why it was never runnable and why the plan could only list this as an untested risk. Removed: `workflows/evolutive/`, `lib/evolutive_direct.ymmsl`, `cases/105073_evolutive.ymmsl`. `git show` recovers them.

   To bring it back, one of: keep the controller (making it `torax_nice_controller` minus the temporal coupler, and requiring PCS); give NICE a default for `pf_active_s`; or find a sender that makes physical sense for an uncontrolled run. The first is a one-line change to the workflow — it was written and then reverted, deliberately, because it makes the *distinguishing feature* of the variant the exchange mechanism rather than the absence of a controller, and that is a design decision rather than a fix.

   **Flatten-diff is zero for both runnable predecessors:** `torax_nice_controller` 12 components / 31 conduits and `torax_nice_rd_controller` 11 / 31, each matching its old template exactly.

   **Both remaining variants require PCS** (`$PDS_REPO/run/pcs`, `setup_files/setup_pcs.sh`); it is not provided by `module load PDS`.

   **Port names came from the two working controller templates, not from `lib/direct_cosim.ymmsl.template`.** That file declares the transport hole as `equilibrium_f_init` / `equilibrium_s` / `equilibrium_o_i`, but TORAX's actual ports are `equilibrium_in_f` / `equilibrium_in_s` / `equilibrium_out_i`. It was never runnable, so the mismatch had never surfaced. Same for its `magnetic_controller` ports. Delete it in step 9 rather than migrating it.

   Three files rather than one with a swappable link, as planned: a single model carrying both the direct and the coupler conduits would leave two senders on `transport.equilibrium_in_s` and `nice_evo.equilibrium_s`, which `check_consistent()` does not flag but which is a double-wire at runtime. `direct_cosim.ymmsl.template`'s own header had reached the same conclusion.

   `magnetic_controller` and `sink_controller` are optional in all three; `evolutive` prunes them, the two controller workflows keep them.

   *Carried over unchanged for equivalence:* `sink_torax` declares a `core_profiles_in` port that nothing feeds, in the old templates and now. Worth removing once someone confirms it is dead.
8. **Started.** `cases/105084_prescribed.ymmsl` and `cases/105084_convergence.ymmsl`, both self-contained (they import their workflow, so one file on the command line) and both free of absolute paths. Two scenarios landed in `pds-scenarios`: `105084` (prescribed-shaped) and `105084_convergence` (adds the `cp` core_profiles port-import the transport leg needs). Neither has data yet. Remaining: the evolutive and controller pairings, once step 7 lands.

   Original scope for reference — **write `cases/`** — one committed default per pairing that exists today, so every workflow has a runnable entry point and CI has a real set to resolve. This is what replaces the deleted `scenarios/<shot>/settings.ymmsl` files, and it is where the old per-scenario knobs (`t_min`, `psi_offset`, `max_iterations`) land.
9. **Docs and CI done; DELETIONS NOT DONE, deliberately.**

   **Done:** `README.md`, `docs/source/{usage,available_workflows,adding_workflows}.rst` now describe the case-file invocation, with the legacy `run_workflow.sh` path documented as legacy and scoped to the four METIS workflows. Every reference to `torax_nice_self_consistent_transport`, a workflow that no longer exists, is gone from the repo. `docs/source/courses/basic/run.rst` is renamed but carries a warning: it still teaches the legacy invocation and its scenario 105092 has no case, which belongs with the `training/` work in step 10. `ci/run_test_workflows.sh` now applies the patches (`setup_files/apply_patches.sh`) and runs both static gates — `ci/gate_probe.py` and `ci/check_ymmsl.py` — before anything else; neither needs scenario data, so they run everywhere.

   **Not done, and should not be until a run has happened:** deleting the old templates, `scenarios/`, shell scripts and `lib/direct_cosim.ymmsl.template`. This plan's own Verification 3 says *"Capture reference outputs before deleting anything"*, and nothing has been run — there is no `/work/imas`, no prepared data, and no reference outputs. Every new definition is verified **structurally** (flatten-diff zero against the old graphs) and **not at all** dynamically. Deleting the only proven-working definitions on the strength of a static check would throw away the thing the comparison needs.

   The order to follow: prepare `pds-scenarios` data → run each old workflow and capture outputs → run each case → compare IDSs → then delete. `ci/run_test_workflows.sh` carries this note inline, next to the two legacy runs it still performs.

10. *(follow-up)* Same treatment for `ymmsl_files/` — 9 `test_*.ymmsl.template` + 9 generated copies and `training/`'s 12 files / 952 lines all re-declare the same `implementations:`/`resources:` blocks.

---

## Verification

**0. Gate — DONE.** `ci/gate_probe.py` + `ci/gate_probe.ymmsl`, landed in the repo and rerunnable anywhere ymmsl and muscle3 are importable (no scenario data, no actors, no IMAS):

```bash
python ci/gate_probe.py
```

Run on **muscle3 0.10.0 + ymmsl 0.17.0** on 2026-08-12. It fixes the three prefix conventions (see "The three prefixes"), and confirms nesting, pruning and cross-boundary conduit gluing all behave as this plan requires. **Re-run it on the target install, and on any ymmsl/muscle3 upgrade** — two of its three answers fail silently when wrong.

Still to confirm on the target install: that `run_script.py` emits `. {virtual_env}/bin/activate` and `exec {command} {args}` (true in the 0.10.0 wheel read here).

**1. Static resolve + flatten — `ci/check_ymmsl.py`**, over **every case in `cases/`**:
```python
cfg = ymmsl.load_as(Configuration, Path('workflows/inverse_convergence/workflow.ymmsl'))
cfg.update(ymmsl.load_as(Configuration, Path('cases/105084_convergence.ymmsl')))
resolve(Reference('inverse_convergence'), cfg)
cfg.check_consistent()
flat = flatten(cfg).root_model()
print(sorted(map(str, flat.components)), sorted(map(str, flat.conduits)))
```
Catches unfilled holes, missing imports, bad `custom_implementations` paths, and — thanks to the declared program `ports:` — a wrong hole fill. Needs no scenario data. Since cases are committed, this runs over the real set rather than examples; a case should also declare which workflow it belongs to in a comment header so the checker can pair them automatically.

**Three additional checks in the same script**, each closing a silent-failure hole that no upstream check covers:

1. **Prefixed setting keys resolve.** For every multi-part key in every case, assert some flattened instance name is a prefix of it. `get_setting` falls through silently, so a key at the wrong depth is invisible at runtime — this is the direct consequence of the Gate, and the only thing that keeps cases honest as nesting changes.
   **And the same for `resources`:** assert every key names a flattened instance exactly. A miss returns 1 thread with only a debug log, so `torax`'s 8 threads would vanish without a trace.
2. **Model ports are wired inside.** For each model in `workflows/lib/*.ymmsl`, assert every declared port appears as an endpoint in that model's own conduits. An unwired model port passes `Model.check_consistent` and `_check_consistent_ports` (see Goal E above) and then makes `flatten()` drop the caller's conduit with no diagnostic.
3. **Scenario `waveforms.yaml` shape.** Assert top-level keys ⊇ `{globals, machine_description, state, targets}` and that `globals` holds only `dd_version`/`imports`. `105084_literal` is broken today in exactly this way (see step 1); this is a class of failure, not a one-off.

**2. Flatten-diff against the old definitions — the load-bearing check.** For each of the 5 migrated workflows, flatten the new pair and diff components and conduits against the old `workflow.ymmsl.template`. Because a partial conduit with no counterpart is *silently dropped*, a mistyped model port yields a missing conduit and no error; this diff is the only thing that catches it.

**2b. Patches applied.** `setup_files/apply_patches.sh` from the `run/` directory. Idempotent, and it *verifies* rather than assumes — it re-reads a `${HOME}` probe through `load_configuration` after patching, because a patch can apply cleanly and still be a no-op if upstream moved. Also warns if Waveform-Editor is not on `feature/reference-tendency-old`.

**3. Runtime smoke tests**, cheapest first:
```bash
muscle_manager --start-all $PDS/workflows/prescribed_transport/workflow.ymmsl     cases/105084_prescribed.ymmsl
muscle_manager --start-all $PDS/workflows/inverse_convergence/workflow.ymmsl      cases/105084_convergence.ymmsl
muscle_manager --start-all $PDS/workflows/evolutive/workflow.ymmsl                cases/105073_evolutive.ymmsl
muscle_manager --start-all $PDS/workflows/torax_nice_controller/workflow.ymmsl    cases/105073_controller.ymmsl
muscle_manager --start-all $PDS/workflows/torax_nice_rd_controller/workflow.ymmsl cases/105073_rd.ymmsl
```
The Goal D test is that the first two cases name the **same scenario** (105084) while driving two different workflows; add a third 105084 case against `evolutive` if a suitable one exists, since with METIS deferred the sample is thinner than planned. Then add a fourth check: stack a two-line override onto one case and confirm only the overridden key changes. Compare produced IDSs against a pre-migration run by direct IDS comparison (`imas compare`, or a per-slice field diff), since the plot scripts are being deleted. **Capture reference outputs before deleting anything.**

**4. Goal E proof — deferred with METIS.** The structural half is covered by Verification 1: `prescribed_transport` (hole pruned to `null`) and `inverse_convergence` (hole filled by `torax`) flatten from the same `design` model. The two-filler swap waits for `transport_metis`.

**5. CI.** `ci/run_test_workflows.sh` passes with the new two-file invocation and a cloned `pds-scenarios` — **and still runs the four METIS workflows on the old path**, since they are unchanged. Do not let the migration silently drop their coverage.

---

## Risks and open points

**Nothing now blocks starting.** The Gate has been run (`ci/gate_probe.py`, muscle3 0.10.0 + ymmsl 0.17.0): nesting, pruning, cross-boundary gluing and `custom_implementations` all behave as this plan needs, and the three prefix conventions are measured. Everything remaining is scoped to a sub-goal, degrades gracefully, or is already true today.

A note on what kind of risk dominates here. The failures this plan must guard against are almost all **silent**: `flatten()` drops a partial conduit with no counterpart; `get_setting` falls through a mis-prefixed key to a default; an unwired model port passes every static check; a mangled YAML comment turns `machine_description` into a member of `globals`. None of them raise. The flatten-diff (Verification 2) and the three added checks in Verification 1 exist because the alternative is discovering these from wrong physics.

### Gate

- **yMMSL / MUSCLE3 capability.** If the deployed ymmsl predates 0.15, nested models and `custom_implementations` do not exist and the whole approach is impossible; if it predates 0.17 the `resources` keys must be unprefixed. `bin/pds-run` already targets `muscle_manager` 0.10.0 and `inverse_convergence` already runs on v0.2 with `imports:`, so this is very likely fine.
- **~~The prefix convention at depth.~~ Resolved** — measured on muscle3 0.10.0 + ymmsl 0.17.0 via `ci/gate_probe.py`; see "The three prefixes". Settings and `resources` key on the flattened instance name (`run.<component>`), `custom_implementations` keys carry the root model name. Re-run the probe on any ymmsl/muscle3 upgrade, since two of the three failure modes are silent.

### Scoped to one goal

- **~~The METIS union mode.~~** No longer a risk to this work — METIS is out of scope (see Scope). What remains is a **cost**, not a risk: the repo runs two mechanisms until METIS is migrated, and the four METIS workflows keep their duplication. That duplication was a real share of the motivation in Context, so the consolidation this delivers is smaller than the one measured there.

### Checked and dismissed

- **~~PDS depends on unmerged IMAS-MUSCLE3 work.~~** It does not. `setup_files/setup_imas_muscle3.sh` already takes a branch argument defaulting to **`develop`**, and `origin/develop` already ships `recorder_component.py`. Nothing needs merging and no new pin needs arranging. The `ymmsl.module` entry points are absent from `develop`, but they were only ever a convenience for dropping `YMMSL_PATH` — which `bin/pds-run` sets today and which the fallback in this plan keeps. Adopt them if and when they land on `develop`.

### Remaining
- **Cases carry absolute paths and must be maintained** — one per pairing worth keeping, each pinned to a store layout. (`supported_settings` is no longer listed here: it moved into step 3 as required work, since with the case layer built entirely on prefixed setting keys it is the only static mechanism that catches a misspelling.)
- **Relative sink URIs remain untested** — worth trying so a case need not spell out every output path, but nothing depends on it now.
- **Waveform editor replacing `sink_source`** must reproduce its *time-aligned re-slicing*, not just the file read. `we_final` in particular is a new use of the WE outside the loop; if it does not fit, keep `md_final` as `sink_source`.
- **`prescribed_transport` as a single-pass `loop`** costs a code change and an extra process. Fallback: its own small model built from the same `nice_inverse` submodel.
- **`nice_evo.pf_active_s` unconnected when the PCS controller is disabled** — true today too, never runtime-tested.
- **`multiplicity` not overridable from an overlay** — all uses of `nice_inverse` share one worker count.
- **git-lfs is a prerequisite only for scenarios that carry their own data**; `.gitattributes` must precede the first such `git add` or payloads enter normal git history irreversibly. Scenarios pointing at a shared store need none of it. **The repo is empty as of now, so this is decidable at zero cost — and only at zero cost until the first commit.**
- **CI needs prepared data** — it currently generates inputs via `preprocess_data.sh`; it must clone `pds-scenarios` and reach whatever store those scenarios name. Infrastructure change to arrange with whoever owns the Bamboo agent.
- **Waveform-Editor is the single point of failure for scenario inputs** once it owns `globals.imports`, and its config schema is moving — the `imports:` mechanism in `105084_literal/waveforms.yaml` does not exist in 0.3.1, so PDS will be pinned to a recent Waveform-Editor much as it is to an IMAS-MUSCLE3 branch.
- **Waveform variants are full file copies, by decision.** ~40 lines of `globals`/`machine_description`/`state` are restated per variant, and an override that changes one target must restate the data pointers too — so a scenario's data cannot move without touching every override of it. This is the one place the compose-don't-copy principle does not reach; keeping complete designs in `pds-scenarios/` rather than `cases/` limits how far it spreads.
- **Nothing can be run end-to-end on this machine.** All runtime verification happens on the target install.
