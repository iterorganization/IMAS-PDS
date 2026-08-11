# Custom PDS dependency modules

Build scripts that produce Lmod modules for the PDS actor codes
(`NICE`, `IMAS-MUSCLE3`, `Waveform-Editor`, `TORAX-MUSCLE3`), instead of using
SDCC's official modules for them. See `../PDS.lua`'s header comment for the
full reasoning; in short:

- `NICE`'s official module is RPATH-linked to `MUSCLE3/0.9.1`, which conflicts
  with `IMAS-MUSCLE3`/`Waveform-Editor`'s `MUSCLE3/0.10.0` dependency. RPATH
  always wins over any modulefile trick, so this can only be fixed by
  rebuilding against `0.10.0`, which is what `build_nice.sh` does.
- `IMAS-MUSCLE3`/`Waveform-Editor`'s official modules are EasyBuild
  "PythonPackage" installs (shared interpreter + `PYTHONPATH` prepend, not a
  self-contained venv). Loading either pulls `MUSCLE3/0.10.0`'s `PYTHONPATH`
  into your interactive shell, which then leaks into every actor subprocess
  `muscle_manager` spawns from that shell -- the exact problem `bin/pds-run`
  was written to avoid for the manager itself. A real venv (`python -m venv`)
  sidesteps this: its own `bin/python` needs no `PYTHONPATH` at all. That's
  what `build_imas_muscle3.sh` / `build_waveform_editor.sh` produce.
- `TORAX-MUSCLE3` has neither problem itself, but the official `TORAX` module
  is `-foss-2025b` only (confirmed to conflict with this cluster's
  `intel-2025b` stack) and doesn't include the MUSCLE3 actor wrapper anyway,
  so it's built the same from-source-venv way for consistency.

`build_imas_muscle3.sh` also installs `muscle3-dashboard` (`muscle_dashboard`/
`m3dash`) into the *same* venv as `IMAS-MUSCLE3`, rather than a separate one.
Per `docs/source/courses/basic/muscle3_dashboard.rst`, a recorder tab's plot
file imports `imas_muscle3.visualization`, which needs `imas_muscle3` and the
full IMAS stack installed in the dashboard's own venv to render -- a lean,
separate `muscle3-dashboard` venv doesn't have that, but the `IMAS-MUSCLE3`
venv already does. So there's no separate dashboard module: loading
`IMAS-MUSCLE3` is enough to get `muscle_dashboard`/`m3dash` on `PATH` too.

## Usage

Each script takes a version string you choose plus a branch/tag, and installs
under `$PDS_SOFTWARE_ROOT` (default `~/public/software`) with a matching
modulefile under `$PDS_MODULES_ROOT` (default `~/public/modules`):

```bash
bash build_nice.sh              3.0.0-pds-intel-2025b   master
bash build_imas_muscle3.sh      1.0.0-pds-2026-08-10    develop   main
bash build_waveform_editor.sh   0.3.1-pds-2026-08-10    main
bash build_torax_muscle3.sh     develop-2026-08-10      develop
```

`build_imas_muscle3.sh`'s third argument is the `muscle3-dashboard` branch to
install (default `main`) -- unrelated to IMAS-MUSCLE3's own branch, the
second argument.

Then uncomment the matching `load(...)` line in `../PDS.lua` with the version
string you passed. Old and new versions coexist side by side under Lmod --
re-running a script with a new version string never overwrites the old one,
so rolling back is just switching which version `PDS.lua` loads.

## What each script sets

- `build_imas_muscle3.sh` / `build_waveform_editor.sh` / `build_torax_muscle3.sh`
  (via the shared `lib_venv_actor.sh`): `prepend_path("PATH", "<prefix>/venv/bin")`
  and `setenv("EBROOT<NAME>", "<prefix>")` -- nothing else. `PYTHONPATH` is
  never touched; the venv's own interpreter already knows its own
  site-packages.
- `build_nice.sh`: `prepend_path("PATH", "<checkout>/run")` and
  `setenv("EBROOTNICE", "<checkout>")`.

`workflows/lib/local_programs.ymmsl` consumes these `$EBROOT*` variables
directly (e.g. `$EBROOTIMASMUSCLE3/venv`, `$EBROOTNICE/run/nice_imas_inv_muscle3`).
