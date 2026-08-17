# Custom PDS dependency modules

Build scripts that produce modules for the PDS actor codes.

## Usage

Each script takes a version string you choose plus a branch/tag, and installs
under `$PDS_SOFTWARE_ROOT` (default `~/public/software`) with a matching
modulefile under `$PDS_MODULES_ROOT` (default `~/public/modules`). For example:

```bash
bash build_nice.sh              3.0.0-pds-intel-2025b   master
bash build_imas_muscle3.sh      1.0.0-pds-2026-08-10    develop
bash build_torax_muscle3.sh     develop-2026-08-10      develop
```
