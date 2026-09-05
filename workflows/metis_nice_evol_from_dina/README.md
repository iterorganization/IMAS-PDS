# metis_nice_evol_from_dina

## What it does

A MUSCLE3 workflow that runs METIS and NICE in genuine evolutive (forward, lockstep)
co-simulation, self-consistently, with a PCSSP magnetic controller closing the coil-current
feedback loop.

This is `evolutive_controller` with METIS in place of TORAX as the transport solver, and
`metis_nice_inverse_from_dina`'s METIS-from-DINA bootstrap in place of that workflow's NICE
inverse solve: each internal step, `metis` evolves the plasma transport and hands
`equilibrium` + `core_profiles` to `nice_evo_rd` (NICE's resistive-diffusion evolutive
free-boundary solver), which returns the updated `equilibrium` for METIS's next geometry, same
as `evolutive_controller`'s `torax`/`nice_evo_rd` pair. Unlike TORAX, METIS also needs a fresh
`pulse_schedule`/`core_profiles`/`core_sources` boundary condition every internal step (its own
actuator/current-drive input), supplied by `synchro_nice_metis` re-slicing METIS's own
DINA-derived input trace at NICE's current equilibrium timestamp. `metis_to_nice`
(`initial_state_splitter`) sits between `metis` and `nice_evo_rd`: METIS's actor emits N+1
messages on its O_I ports (its initial state right after F_INIT, then one per step), while
`nice_evo_rd` wants the initial state on its own F_INIT and only the N per-step messages on
S, so `metis_to_nice` splits the stream accordingly.

Ported from `itergit/feature/metis_nice_evol`'s
`workflows/metis_predictive_nice_evol_from_dina/workflow.ymmsl.template` ("first version of the
workflow with METIS + NICE evol + Controller" and its follow-up port/conduit fixes) into this
repo's current `workflow.ymmsl` + `settings.ymmsl` + `cases/overrides/` structure. The
single-metis arrangement is used, with `metis_to_nice` (`initial_state_splitter`) routing
METIS's initial O_I state to `nice_evo_rd`'s F_INIT and its later states to its S ports (see
above).

Structure lives in `workflow.ymmsl`; shared knobs in `settings.ymmsl`; per-shot bootstrap
timing (which DINA slice to start from has no sane generic default) in
`cases/overrides/metis_nice_evol_from_dina_<shot>.ymmsl`.

## Running it

Requires the scenario's raw DINA data in `pds-scenarios`. Build a case folder and hand it to
SLURM:

```bash
bin/pds-create-case metis_nice_evol_from_dina 105073   # -> cases/metis_nice_evol_from_dina_105073
sbatch bin/pds-run-case.sbatch cases/metis_nice_evol_from_dina_105073
```

`pds-create-case`'s `preprocess.sh` builds both `source_metis`'s METIS-formatted dataset and
`source_nice`'s DINA-derived machine description (same dual build as
`metis_nice_inverse_from_dina`), once, into `$CASE_DIR/preprocess/`.

## Notes

First end-to-end run on 2026-09-04 (shot 105084) found two blockers, both fixed: (1) a
NoMachine desktop session forwards `LD_PRELOAD=libdlfaker.so:libvglfaker.so` (VirtualGL)
through sbatch into every actor; on a compute node that hangs the Simulink engine start of
`magnetic_controller` until MUSCLE3's 10-minute peer timeout -- `bin/pds-run-case.sbatch` now
unsets it (same as upstream commit 855808f); (2) the METIS initial O_I message ending NICE's
time loop after one step -- fixed by `metis_to_nice` (see above).

**`synchro_nice_metis` uses `f_init`/`o_f`, not the branch's own latest (`s`/`o_i`) commit.**
The branch's final "change of port mode" commit (made the same day as the rest of this
addition) wired it as `s`/`o_i`, but `imas_muscle3.data_sink_source.muscled_sink_source` (see
that module's own docstring and `muscled_sink_source()`) only implements the `F_INIT`/`O_F`
operator pair for the hybrid sink/source actor -- there is no `S`/`O_I` support, and wiring
`s`/`o_i` as the branch did would very likely reproduce the "dead lock" its own commit history
mentions fixing once already (a `reuse_instance()` loop that only ever calls
`instance.receive`/`instance.send` against `Operator.F_INIT`/`Operator.O_F` port lists never
sees a message declared under `s`/`o_i`).

`f_init`/`o_f` (matching the branch's earlier `workflow_alternative.ymmsl.template`) is not
just a workaround for that, it's the correct MMSF macro-micro pairing for this actor:
`nice_evo_rd.equilibrium_o_i` (O_I, fires every internal step) drives `synchro_nice_metis`'s
`F_INIT`, so its `reuse_instance()` loop runs once per NICE step, each cycle sending one `O_F`
message -- not "sent once, ever". `synchro_nice_metis`'s `O_F` output then feeds `metis`'s `S`
ports (`pulse_schedule_in_s`/`core_profiles_in_s`/`core_sources_in_s`); MUSCLE3 does not
enforce a matching operator label across a conduit (confirmed against `libmuscle`'s
`mmsf_validator.py`/`port_manager.py`/`topology_store.py` -- operator is purely local
bookkeeping per instance), only that message cadence lines up, which it does here since
`nice_evo_rd.dt` and `metis`'s own internal `dt` are required to match by design. Verified
structurally with `ci/check_ymmsl.py`'s resolve/check_consistent/flatten machinery, which
passes either way -- this reasoning about message cadence is what actually decides it, since
the static checker doesn't validate operator pairing across conduits.

## Assumptions

- `nice_evo_rd`'s port names (`equilibrium_f_init`, `pf_active_s`, `equilibrium_o_i`, ...) and
  `magnetic_controller`'s (`equilibrium_in_f`, `equilibrium_in_s`, `pf_active_out_i`, ...) match
  `evolutive_controller`'s -- the same NICE/controller binaries, so the same real port names,
  which differ slightly from the branch's own (older) naming for the same ports.
- `metis`'s ports/settings (`metis_computation: 1`, the `metis_external_data_*` predictive
  defaults) match `metis_from_dina`/`metis_nice_inverse_from_dina`'s conventions.
- `nice_evo_rd.t_interval`/`nice_evo_rd.dt` default to `0.002`, matching the branch's own
  template (comment: "Need to match controller dt") -- not validated for solver stability here,
  same caveat as `evolutive_controller`'s `0.01` default.
- `config_nice.xml` is the branch's own `param.xml.template` with `use_desired_psib` 1 and `abserrIg` 3e5 (see the comment there); it differs from `evolutive_controller/config_nice.xml` in `algoMode` (21 vs 31), mesh refinement and profile degrees of freedom -- the latter was tried on 2026-09-04 and NICE's evolutive solve diverged at its third step with it, so the branch's config is kept.

## Input requirements

Same as `metis_nice_inverse_from_dina`: this shot's raw DINA source and standard machine
description in `pds-scenarios` (`source.env`), plus the ssh-gated PCS checkout and
`nice_imas_evo_rd_muscle3` binary (source-built, see `evolutive_controller`'s Input
requirements).

## Output

`sink_transport`, `sink_equilibrium`, and `sink_control` write METIS's evolved profiles, NICE's
evolutive equilibrium/pf_active, and the controller's corrected pf_active, respectively.
