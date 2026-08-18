# PDS dependency modules (EasyBuild)

Everything the PDS workflows load is built with EasyBuild. Replaces the old
`setup_files/custom_modules/build_*.sh` scripts.

```bash
module load EasyBuild
bash build.sh                 # all of it
bash build.sh NICE CHEASE     # or just some

module use "$HOME/public/modules/all"
cd /path/to/your/pds/checkout && module load PDS
```

`module load PDS` wires in whichever checkout you are standing in (or `$PDS_REPO`
if you set it), so one shared build serves everybody's clone.

`build.sh` takes `EASYBUILD_PREFIX` (default `~/public`) and always passes
`--rpath` — see "Why `--rpath`", below.

## Most of this is not ours

The ITER codes are packaged upstream in
[easybuilders/easybuild-easyconfigs](https://github.com/easybuilders/easybuild-easyconfigs),
mostly by @SimonPinches. Those easyconfigs are pulled from their pull requests
with `eb --from-pr` rather than copied into this repository, so there is nothing
here to keep in sync, and each one disappears from `build.sh` by deleting a line
once its PR merges and SDCC installs it.

| Module | PR | Notes |
|---|---|---|
| IMAS-Cpp 5.6.0, IMAS-Fortran 5.6.0 | [#26547](https://github.com/easybuilders/easybuild-easyconfigs/pull/26547) | w/ DD 4.1.1 |
| IMAS-Python 2.3.0 | [#26546](https://github.com/easybuilders/easybuild-easyconfigs/pull/26546) | |
| MUSCLE3 0.10.0 | [#26276](https://github.com/easybuilders/easybuild-easyconfigs/pull/26276) | |
| INTERPOS 9.2.3 | [#25841](https://github.com/easybuilders/easybuild-easyconfigs/pull/25841) | CHEASE dependency |
| iWrap 2.0.0 | [#26506](https://github.com/easybuilders/easybuild-easyconfigs/pull/26506) | CHEASE dependency |
| IMAS-Validator 1.0.0 | [#26550](https://github.com/easybuilders/easybuild-easyconfigs/pull/26550) | **locally overridden** — see below |
| Waveform-Editor 0.3.1 | [#26553](https://github.com/easybuilders/easybuild-easyconfigs/pull/26553) | used unmodified |

## What is ours, and why

Each file says this at more length in its own header; this is the index.

### No upstream easyconfig exists

| File | Why it is here |
|---|---|
| `n/NICE/NICE-3.0.0-intel-2025b-pds.eb` | SDCC's NICE has MUSCLE3 0.9.1 in its RPATH, which beats any env var, so it cannot talk to the 0.10.0 manager. Rebuilt from the `v3.0.0` tag against EasyBuild's Eigen/SuiteSparse/MUSCLE3 instead of NICE's vendored submodules. |
| `c/CHEASE/CHEASE-2026.08-intel-2025b-pds.eb` | CHEASE's own `config_muscle3.sh` mixes intel-2023b and intel-2025b and cannot work on SDCC. Pins one consistent generation, runs the iWrap codegen, and shims `ifort`→`ifx` (intel-2025b dropped `ifort`; CHEASE's Makefile hardcodes the name). |
| `t/TORAX-MUSCLE3/TORAX-MUSCLE3-0.1.2-intel-2025b-pds.eb` | The official TORAX module is foss-2025b only and has no MUSCLE3 wrapper. Note this one lets pip resolve its own dependency tree — the header explains why that is not laziness. |
| `m/METIS-IRFM/METIS-IRFM-2026.08-pds.eb` | Named `-IRFM` because EasyBuild's `METIS` is the Karypis graph partitioner, an unrelated package this stack also pulls in. MATLAB source, no compile step. |
| `p/PDS/PDS-1.0.eb` | The PDS meta-module itself, replacing the hand-written `setup_files/PDS.lua` and its `sed`-based deploy step. Installs nothing: it declares IMAS-Python and IMAS-MUSCLE3 as real dependencies and wires your checkout into PATH/PYTHONPATH/YMMSL_PATH from a `modluafooter`. |
| `p/PCS/PCS-2026.08-pds.eb` | PCS + PCSSP as a shared checkout, so nobody needs their own `run/pcs` clone. MATLAB/Simulink source, no compile step. |

### Deviations from upstream

| File | Why it is here |
|---|---|
| `i/IMAS-Validator/IMAS-Validator-1.0.0-intel-2025b.eb` | Released imas_validator 1.0.0 calls `has_imas`, removed in IMAS-Python 2.3.0 — so PR #26550, which pairs exactly those two, crashes the OLC actor on every `validate()`. Carries a patch backporting the upstream fix. Deliberately keeps the **unsuffixed** name so PR #26551's IMAS-MUSCLE3 resolves to it and needs no local fork. |
| `i/IMAS-MUSCLE3/IMAS-MUSCLE3-1.0.0-intel-2025b-pds.eb` | Copy of PR [#26551](https://github.com/easybuilders/easybuild-easyconfigs/pull/26551) with the imas_muscle3 source swapped to a pinned develop commit, plus a patch. Two reasons: the 1.0.0 release ships only six actors (PDS also needs `recorder`, `iterator`, `passthrough`, added to develop afterwards), and workflows import actors from the package, which needs the `ymmsl.module` entry point from the unmerged `feature/ymmsl-path-entrypoints`. That branch predates the three extra actors, so the patch rebases it onto develop and registers all nine. |
| `y/ymmsl2svg/ymmsl2svg-0.1.0-intel-2025b-pds.eb` | The muscle3-dashboard graph card, which `build_imas_muscle3.sh` used to pip-install into the shared venv. Split into its own optional module for the same reason: so IMAS-MUSCLE3 stays untouched upstream. Load it next to IMAS-MUSCLE3, or don't — the dashboard degrades gracefully. |

## Why `--rpath`

Every actor in `workflows/lib/local_programs.ymmsl` declares `base_env: clean`,
so MUSCLE3 spawns it with a purged environment and only its own `modules:`
loaded. There is no inherited `LD_LIBRARY_PATH`, and NICE's and CHEASE's
makefiles emit explicit `-rpath` only for the IMAS libraries. `build_nice.sh` and
`build_chease.sh` patched this up after the fact with
`patchelf --force-rpath --add-rpath "$LD_LIBRARY_PATH"`; `--rpath` is EasyBuild
doing the same thing properly, at link time. Both easyconfigs have an `ldd`
sanity check that fails the build if you forget.

## Bumping a version

The five local codes without upstream releases pin a git commit and a
date-stamped `version`. Change both together, and rename the file to match —
old and new then coexist as separate modules, which is what makes a bad bump
recoverable.

`workflows/lib/local_programs.ymmsl` and `p/PDS/PDS-1.0.eb` name modules with
their full version, so both need the same edit. That is deliberate: nothing
silently drifts onto a new default when SDCC's module tree changes.
