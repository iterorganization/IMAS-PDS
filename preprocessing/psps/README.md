# PSC in the loop and PSPS-like file generation

Code (not documentation) for running PDS with the Pulse Supervision Controller (PSC) in the
controller actor and for generating PSPS-like files from a designer Ip waveform.

## `ip_waveform_export/`

Converter from a designer Ip YAML (Waveform-Editor-style, with segments and events) to the
four PSC configuration files (PSCIntConfig.xml, PSCGlobalMonConfig.xml, BTree.xml, PS.xml),
the RefGen schedule XML, a PSPS "WF" JSON guess and a pulse_schedule IDS. Runs from any
location (`python3 ip_waveform_export.py --yaml ... --out-dir ...`); tests in `tests/`
(`pytest` from that folder, PyYAML needed); copies of pcs / pcssp reference files in
`reference/third_party/` (provenance and byte-for-byte check in its `PROVENANCE.md`).

## PSC run inputs

The controller is the usual one (`controllers/CCS/muscle_controller_NICE_IMAS_iter_init.m` and
`pcssp_controller_and_ps.slx`): the PSC is a block of the model (Subsystem Reference to `PSC`,
giving Ipl_ref, with z_meas = zpl, the current centre); with the setting `psc_enabled: 1` the
init gives it the four files of `psc_config_dir` and runs the model from t = 0, the PSC's clock.

- `make_mcls_psc_config.py`: adds the `force_control_mode` output (MCLS forced mode per segment)
  to a set of PSC files written by the converter (used for `cases/input/psc/ip_story_mockup/`).

The run is launched with `workflows/evolutive_controller/run_psc_cases.sh`
(`VARIANT=ip_story_mockup`, `SHORT_WINDOW=1` for the 0.2 s smoke check, `DRY_RUN=1` to only
build the case folder); see the section "PSC and MCLS case (ip_story_mockup)" of
`workflows/evolutive_controller/README.md`.

## Inputs and outputs in the repository

- `cases/input/psc/ip_story_mockup/`: the PSC + MCLS case (designer YAML, refgen XML,
  `psc_config/` with the four PSC files, `ids/`, MCLS mode table, README). The z excursion is
  measured on z_meas = NICE `global_quantities.current_centre.z` (README of the case).
- `cases/overrides/evolutive_controller_105073_ip_story_mockup.ymmsl`: the case override
  (window 115.817598 -> 138.0 s, PSC, MCLS). Paths are written with the
  `${PDS_REPO}` placeholder, expanded by `run_psc_cases.sh` (`envsubst`, as
  `bin/pds-create-case` does): muscle_manager does not expand it, so expand the file first when
  passing it to `bin/pds-run-case` by hand. The 0.2 s smoke window (`SHORT_WINDOW=1`) is
  written by the launcher.
- The PSC signals go in the run's `simulink_log.csv` once they are wired to the logger Mux
  (with their names in the init's `sig` list).

## Dependencies

- `local_installs/pcs-with-pcssp-nightly`: the PCS framework with the Pulse Supervision
  Controller, a PDS local dependency installed by `pds_setup.sh` with
  `INSTALL_PCSSP_NIGHTLY="true"` (`setup_files/setup_pcs_with_pcssp_nightly.sh`). It is not a
  repository of its own: a clone of `pcs` (`ssh://git@git.iter.org/pcs/pcs.git`, branch
  `master`) with a clone of `pcssp-nightly` (`ssh://git@git.iter.org/pcs/pcssp-nightly.git`,
  branch `merge_IGZ_PSC`, the only line carrying the PSC `src/psc/PSC.slx`) under its `pcssp/`
  and the `scdds` submodule initialised. Both need SSH access to git.iter.org. `pds_setup.sh`
  pins the tested reference, pcs `aa217bc` and pcssp-nightly `ebf3ee0`
  (`PIN_PCS_FOR_PCSSP_NIGHTLY`, `PIN_PCSSP_NIGHTLY`; set empty to follow the branch tips). Used
  by the MCLS model build and the programs `magnetic_controller` /
  `magnetic_controller_psc` in `workflows/lib/local_programs.ymmsl`. Its former name
  `local_installs/pcs-nightly` may exist as a compatibility symlink for older run directories.
- MATLAB chain from the PDS modules: `PCS/2026.08-pds` (MATLAB with the muscle3 venv) and
  `IMAS-MATLAB/5.6.0-intel-2025b-DD-4.1.1`, loaded by the controller program.
- `imas-python` (PDS module) for the pulse_schedule IDS export of the converter (`--ids`).

## Environment

- `PCS_PATH`: pcs + pcssp-nightly checkout; `local_installs/pcs-with-pcssp-nightly` (resolved
  with `readlink -f`) in the MCLS build and the controller programs.
- `PDS_REPO`: repo root; derived by the scripts when not exported.
- Site paths kept as such: `/work/projects/pds/modules/all` (modules) and
  `/scratch/users/$USER` (scratch work folders of the Slurm jobs).

The study notes, plans, figures and the campaign history are kept outside this repository.
