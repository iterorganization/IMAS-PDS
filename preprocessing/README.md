# Scenario preparation

A scenario's `data/` is derived from a DINA simulation and the ITER machine-description
collections by `preprocessing/prepare`. The result lands in the scenario data root,
`$SCENARIOS_REPO/<shot>/data`, which defaults to `scenarios/` in this repository and is
**not committed** (see [`scenarios/README.md`](../scenarios/README.md)). Point
`SCENARIOS_REPO` elsewhere, e.g. `/work/projects/pds/pds-scenarios`, to use another data
root.

This directory was moved from the pds-scenarios repository
(github.com/Ignition-Computing/pds-scenarios, commit c162cef) plus local changes.

| Path | Content |
|---|---|
| `prepare` | the preparation script (shell) |
| `dina2pds/` | the DINA -> PDS converter it calls (`convert_dina_data_to_input.py`, `preprocess_dina.py`, `preprocess_machine_description.py`) and the METIS-input builder (`convert_for_metis.py`, `make_metis_input.m`) |
| `check_scenario.py` | checks a prepared scenario against its DINA source and plots it |

The METIS workflows' `preprocess.sh` (`metis_nice_inverse_from_dina`, `metis_from_dina`) call `preprocessing/dina2pds` too, with `TOOLS=$PDS_REPO/preprocessing`.

## Recommended entry point

Describe the shot in a pulse file and let `bin/pds-configure` write `source.env` and run
the preparation (see [`cases/pulses/README.md`](../cases/pulses/README.md)):

```bash
bin/pds-configure cases/pulses/<shot>.yaml --prepare            # source.env + data/
bin/pds-configure cases/pulses/<shot>.yaml --prepare --create   # ... + cases + check
```

A pulse file with `workflows: []` only prepares the data. Running the script directly
works on any scenario directory that already has a `source.env`:

```bash
preprocessing/prepare 105084              # regenerate $SCENARIOS_REPO/105084/data
preprocessing/prepare 105084 --dry-run    # print the command, run nothing
preprocessing/prepare 105084 --metis      # also build data/metis_in (see METIS input)
```

## What it does

`preprocessing/prepare <scenario>` reads `$SCENARIOS_REPO/<scenario>/source.env` and calls
`preprocessing/dina2pds/convert_dina_data_to_input.py`, which:

1. reads the DINA `summary` and selects the timeslices over the viable range (magnetic
   axis R > 1 m and |Ip| > 50 kA), by exactly one of `N_TIMESLICES` (that many
   timeslices, uniformly in time; converter option `--n_timeslices`) or `DT_STEP` (one
   timeslice every `DT_STEP` seconds from the first viable time, each at the nearest
   viable raw sample; `--dt_step`);
2. copies `equilibrium`, `core_profiles` and `core_sources` at those slices into `data/in`,
   converting each to DD 4.0.0;
3. merges DINA's per-slice coil currents onto machine-description geometry, also into
   `data/in` — used only by validation plots comparing DINA's currents against NICE's
   inverse solution;
4. writes the static machine description — `pf_active`, `pf_passive`, `wall`, `iron_core`.

Slices that are not viable are skipped and logged, so the result can hold fewer than
`N_TIMESLICES` entries: 105084 asks for 41 and gets 40, 105073 gets 39. A non-viable pick
is replaced by the next viable raw sample (up to 10 ahead); when two picks reach the same
raw time, that slice is written once and the duplicate is logged (105033 had a
duplicated first slice before this check).

The converter ends with one summary line (WARNING level, so it is always shown): the
number of slices written, the selection method, the viable range and the slice spacing.
When `REPORT_T_START` and `REPORT_T_END` are set in `source.env` (`bin/pds-configure`
writes them from `time.t_start` / `time.t_end`), `prepare` passes them as
`--report_window` and the line also gives the number of slices inside that simulation
window and their spacing there. They are only reported; they do not change the data.

The finished `data/` is left read-only: opening an IMAS entry even with mode "r" rewrites
its `master.h5`, and several jobs reading one entry at once race on that write.

## DD version: IMAS_VERSION=4.0.0

The converter writes at the session's default data-dictionary version. The stored data of
the five existing scenarios (105073/78/84/92/99) are DD 4.0.0, so `prepare` exports
`IMAS_VERSION=4.0.0` unless it is already set: regenerating them under another default
(the IMAS-MUSCLE3 module defaults to DD 4.1.1) gives different files. `bin/pds-configure`
sets it from the pulse-file key `prepare.dd_version` (default `"4.0.0"`) and records it as
a comment in `source.env`.

## MD_LAYOUT

`source.env` chooses where the machine description from step 4 goes. Getting this wrong is
quiet — the run either fails when `sink_source` cannot find a lane, or succeeds with the
wrong `pf_active`.

| `MD_LAYOUT` | Produces | For |
|---|---|---|
| `separate` (default) | `data/in` + `data/in_md` | workflows whose waveform editor imports the machine description — `prescribed_transport`, `inverse_convergence` |
| `combined` | `data/in` only | the forward co-simulations, whose `sink_source` re-emits all four machine-description lanes from one entry |

Under `combined`, `prepare` omits `--md_sink_uri`. The converter then defaults it to the
data sink and skips the machine-description `pf_active` entirely
(`write_pf_active=db_md_out is not db_out`), so the entry keeps DINA's `pf_active` **with**
its coil currents rather than the currentless machine-description one.

## source.env

Each scenario records the URIs it was built from (`bin/pds-configure` writes this file
from the pulse file):

```bash
SOURCE_URI="imas:hdf5?path=/work/imas/shared/imasdb/ITER/3/105084/1"
SUMMARY_URI="$SOURCE_URI"
MD_PF_ACTIVE="imas:hdf5?path=/work/imas/shared/imasdb/ITER_MD/3/111001/204"
MD_PF_PASSIVE="imas:hdf5?path=/work/imas/shared/imasdb/ITER_MD/3/115005/3"
MD_WALL="imas:hdf5?path=/work/imas/shared/imasdb/ITER_MD/3/116000/5"
MD_IRON_CORE="empty"   # empty for ITER
N_TIMESLICES=41
# simulation window (time.t_start/t_end), only for the preparation log
REPORT_T_START=2.4
REPORT_T_END=280.4
```

`N_TIMESLICES=41` can be replaced by `DT_STEP=1.0` (exactly one of the two; `prepare`
stops with an error otherwise). With `--metis`, `METIS_NBT` defaults to `N_TIMESLICES`,
so a `DT_STEP` scenario must set `METIS_NBT` (`prepare.metis.nbt`).

ITER has no iron core: `MD_IRON_CORE="empty"` makes the converter create an empty static
`iron_core` IDS (NICE takes an iron_core input, needed for WEST; give a real URI for such
a machine). Older source.env files point at `$TOOLS/md/iron_core_empty`, a reference entry
no longer shipped; the converter treats any URI whose path ends in `iron_core_empty` as
`empty`, so they still work.

Machine-description versions:

- the pulse-file set `basic` uses the active versions listed in
  `/work/imas/shared/imasdb/ITER_MD/3/md_summary.yaml` as of 2026-09-30: pf_active
  111001/204, pf_passive 115005/3, wall 116000/5;
- the five legacy scenarios (105073/78/84/92/99) were prepared with 111001/203, 115005/2
  and 116000/4; the pulse-file set `legacy` selects exactly these, use it only to
  reproduce those scenarios.

These paths are as they exist on the ITER SDCC cluster. They are read-only inputs; the only
thing `prepare` writes is the scenario's own `data/`.

## Where to run it

`prepare` needs a Python with `imas-python` and `imas_core` (and scipy, packaging).

**On SDCC** — everything is reachable, including MDSplus sources. The IMAS-MUSCLE3 module
used by `bin/pds-configure` has everything:

```bash
module use /work/projects/pds/modules/all
module load IMAS-MUSCLE3/1.0.0-intel-2025b-pds
preprocessing/prepare 105073
```

**Off-cluster** — works for HDF5 sources if you copy them locally first and point
`source.env` at the copies. `PREPARE_PYTHON` selects the interpreter:

```bash
rsync -a iter:/work/imas/shared/imasdb/ITER/3/105084/1/ /tmp/raw/dina_105084/
PREPARE_PYTHON=/path/to/venv/bin/python preprocessing/prepare 105084
```

Only `master.h5`, `summary.h5`, `equilibrium.h5`, `core_profiles.h5`, `core_sources.h5`,
`pf_active.h5` and the `ids_*` metadata are needed — about 312 MB for 105084, of which
`equilibrium.h5` is 251 MB.

MDSplus sources cannot be copied this way, so a scenario with one (105073) must be prepared
on SDCC.

## Data dictionary versions of the sources

The DINA and machine-description entries are stored under several DD 3.x versions and are
converted to DD 4.0.0 on the way in. Two things follow:

- **Compare like with like.** DD4 renamed `pf_active/coil/name` from
  `"Central Solenoid 3U (CS3U)"` to `"CS3U"`. Code that converts one side of a comparison
  and not the other fails on the first timeslice.
- **Never rely on the default DD.** IMAS-Python refuses to auto-convert across a major
  version, so `get()` on a DD 3.38.1 entry fails outright when the default is 4.x. Read raw
  with `autoconvert=False` and convert explicitly.

If you change anything in `preprocessing/dina2pds/`, run `prepare` under both a DD 3.x and a
DD 4.x default before trusting it.

## Reading the output

`prepare` ends with a per-directory file count and apparent size:

```
prepare: done
  in                        5 IDS files, 5.3MB
  in_md                     5 IDS files, 263KB
```

It deliberately does not use `du`. On the ITER parallel filesystem a freshly written file
can report almost no allocated blocks until it is flushed, so `du` run immediately after a
successful conversion makes it look as though nothing was written.

One warning per run is expected and harmless:

```
pf_active coil names differ between source and machine description for 14 of 14 coils;
matched by index instead. e.g. [0] 'CS3U' vs 'Central Solenoid 3U (CS3U)'
```

DINA and the machine description name the coils differently (and for the VS coils the names
are not even substrings of each other). Coil order is fixed ITER geometry and lines up by
index, so matching by index is correct.

## Older DINA runs

Older DINA runs (e.g. 105033) differ from the current ones in two ways, and `prepare`
handles both; each is logged once per run.

- **12-coil `pf_active`.** CS1 and VS3 are each one coil with two elements, where the ITER
  machine description has 14 single-element coils (CS1U, CS1L, VSU, VSL). The entry is
  converted to the 14-coil machine description following the DINA developer's conversion
  script (`pf.py`, `update_pfa`): CS1U = CS1L = I(CS1), each with half the CS1 voltage;
  VSU = -I(VS3) and VSL = +I(VS3), with voltages -V/2 and +V/2. There is no division by 4:
  the DINA IMAS wrapper already stores the per-turn current of the 4-turn VS coils. Supplies
  and circuits come from the machine description, with supply currents taken from the coils
  and the VS1 supply = -PF2 - PF3 + PF4 + PF5; coil and supply names are in DD 4 short form.
  The conversion is done only when the entry is not already in the 14-coil layout: an entry
  with the 14 single-element coils of the machine description (a native 14-coil DINA run, or
  one already converted, e.g. by `pf.py`) is merged coil by coil, and any other layout stops
  `prepare` with an "unsupported pf_active layout" error.
- **Radial grid short of the boundary.** When the `core_profiles` / `core_sources` radial
  grid ends within 1 % of rho_tor_norm = 1 (0.9964 for 105033), its last node is set to 1.0
  (profile values untouched): TORAX needs a boundary value at rho = 1.

Two fixes, ported from the former `workflows/utils` copy of the converter, apply to every
run:

- **Vessel units kept.** `wall.description_2d[0].vessel` keeps its two filled units
  (`resize(2, keep=True)`); the previous code emptied both, and NICE then logged
  "I set n_vessel=0".
- **Geometric axis filled.** For a DD 3 source, `equilibrium` `boundary.geometric_axis.r/z`
  are set, where not already filled, to the midpoints of the original boundary outline
  (fallback: the `boundary_separatrix` outline) before that outline is replaced by the
  separatrix outline. DINA fills `.r` but not `.z`, which the PCSSP magnetic controller
  uses as its vertical-position reference.

## Checking a prepared scenario

```bash
preprocessing/check_scenario.py <scenario> [--case CASE_DIR] [--t-min T] [--t-max T] [--dt DT] [--out PNG]
```

`bin/pds-configure --create` runs it automatically on each new case (figure
`<case>/check_<shot>.png`). `check_scenario.py` compares the raw DINA entry named by
`$SCENARIOS_REPO/<scenario>/source.env` (`SUMMARY_URI`, else `SOURCE_URI`) with the
prepared `$SCENARIOS_REPO/<scenario>/data/in`. `--case` points at a PDS case folder; the
loop window and TORAX time step are then read from its `workflow_settings.ymmsl` /
`scenario_settings.ymmsl` (`loop.t_min`, `loop.t_max`, `transport.torax.fixed_dt`, with
fallbacks such as `source.t_min`, `torax.t_final`, `torax.fixed_dt`). `--t-min`, `--t-max`
and `--dt` set or override these values directly.

It prints one `OK` or `WARN` line per check:

- the machine-description files present in `data/in_md` (`WARN` if the directory is missing);
- the number of prepared slices against `N_TIMESLICES` (`WARN` when fewer were written),
  or, with `DT_STEP`, against the approximate count (viable range / `DT_STEP` + 1;
  `WARN` when off by more than max(2, 10 %));
- whether the prepared time array is strictly monotonic (`WARN` lists the violations, e.g. a
  duplicated first slice);
- the prepared time window against the viable raw window (magnetic axis R > 1 m and
  |Ip| > 50 kA);
- with a loop window: how many prepared slices fall inside it, the minimum and maximum slice
  interval there and, with a time step, the number of TORAX fixed steps between them;
- the flattop of the raw plasma current (|Ip| > 95 % of peak) and the peak value.

The figure (default `$SCENARIOS_REPO/<scenario>/check_<scenario>.png`, or `--out`) shows the
raw DINA Ip with the viable range shaded, the prepared slices as dots, the loop window and
flattop markers, and below it a strip with one tick per prepared slice and smaller ticks for
the TORAX steps (capped at 5000 ticks).

## Provenance

`data/` carries no record of where it came from. The pulse file
`cases/pulses/<shot>.yaml` is the source of truth; `source.env` is generated from it and
states intent rather than what was actually run.

## METIS input

METIS does not take a plasma state the way TORAX does; it builds its input from a
`pulse_schedule` IDS (`get_metis_input_from_muscle3.m`). That is not part of `data/in`, so
scenarios used with a METIS workflow need one extra step:

```bash
module use $HOME/public/modules && module load PDS   # MATLAB, PDS-METIS, IMAS-MATLAB
preprocessing/prepare 105084 --metis
```

This runs METIS's own `prepare_IDS4METIS_from_dina` (via
`preprocessing/dina2pds/make_metis_input.m`) directly against the DINA source named in
`source.env` and writes `data/metis_in`. Set `METIS_MODE` (`interpretative`, the default, or
`predictive`) and `METIS_NBT` in the scenario's `source.env` (pulse file: `prepare.metis`)
to override the defaults. With a pulse file that has `prepare.metis`,
`bin/pds-configure --prepare` passes `--metis` itself.
