# IMAS PDS

The **Pulse Design Simulator** couples the codes used to design an ITER pulse —
NICE for free-boundary equilibrium, TORAX and METIS for transport, the
Waveform-Editor for targets, PCSSP for magnetic control — into simulations that
run as a single job, exchanging IMAS data through
[MUSCLE3](https://muscle3.readthedocs.io/).

PDS itself builds nothing. Each code is a separate EasyBuild module that MUSCLE3
loads when it starts that actor; this repository holds the couplings. A coupling
is a **workflow**; pairing one with a shot's data gives you a **case**, which is
what you run.

Licensed under LGPL-3.0-or-later; see [LICENSE.md](LICENSE.md),
[COPYING.LESSER](COPYING.LESSER) and [COPYING](COPYING).

## Quickstart

Requires access to the ITER cluster, where the module stack is published.

```bash
export PDS_REPO=/path/to/pds
export SCENARIOS_REPO=/path/to/pds-scenarios

module use /work/projects/pds/modules/all
module load PDS

bin/pds-create-case inverse_convergence 105073
sbatch bin/pds-run-case.sbatch cases/inverse_convergence_105073
```

Output lands in `cases/runs/inverse_convergence_105073/`.

Export `PDS_REPO` before the module load — it is how the module knows which
checkout to wire in. Without it, it falls back to your current directory.

## Documentation

Full documentation: **<https://docs.iter.org/PDS>**

| Page | Covers |
|---|---|
| Installing | What `module load PDS` sets up, and the tool stack |
| Running a case | Creating, submitting and reading a case |
| Available workflows | The five workflows, and which shots are exercised |
| Troubleshooting | First-run failures, including the silent ones |
| Contributing | Dev environment, checks, PR conventions |
| Local install | Building the stack from source |

Build it locally with `uv sync --extra docs && make -C docs html`.

For background on the MUSCLE3 actors, see the
[Confluence page](https://confluence.iter.org/display/IMP/PDS+-+Pulse+Design+Simulator).

## Repository layout

| Directory | Contents |
|---|---|
| `bin/` | Entry points: `pds-create-case`, `pds-run-case.sbatch` |
| `workflows/` | One directory per workflow, plus `lib/` for shared programs and actors |
| `cases/overrides/` | Per-shot tuning. Generated cases and run output also land under `cases/` |
| `setup_files/` | Easyconfigs for the module stack, and the from-source `setup_*.sh` scripts |
| `ci/` | Integration test driver and the static ymmsl checker |
| `pds/` | The Python package — deliberately tiny; the module puts the repo on `PYTHONPATH` |
| `controllers/` | MATLAB/Simulink sources for the PCSSP magnetic controller |
| `visualization/` | Recorder configurations, referenced by workflow settings |
| `docs/` | This documentation |

## Contributing

Run the four checks CI runs before pushing:

```bash
ruff format --check --diff . && ruff check . && uv run ty check . && uv run make -C docs html
```

See the Contributing page in the documentation for conventions, and for how to
run the integration tests, which need the cluster rather than GitHub.

## Related repositories

- [IMAS-MUSCLE3](https://github.com/iterorganization/IMAS-MUSCLE3) — general-purpose MUSCLE3 actors
- [Waveform-Editor](https://github.com/iterorganization/Waveform-Editor) — target waveform generation
- [NICE](https://gitlab.inria.fr/blfauger/nice/-/wikis/home) — free-boundary equilibrium
- [TORAX](https://github.com/google-deepmind/torax) — core transport
- [TORAX-MUSCLE3](https://github.com/iterorganization/TORAX-MUSCLE3) — MUSCLE3 actor for TORAX
- [METIS](https://gitlab.eufus.psnc.pl/g2jfa/metis) — fast integrated transport
- [CHEASE](https://gitlab.epfl.ch/spc/chease) — fixed-boundary equilibrium
