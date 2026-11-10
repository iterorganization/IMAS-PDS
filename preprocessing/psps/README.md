# PSC in the loop and PSPS-like file generation

Code (not documentation) for running PDS with the Pulse Supervision Controller (PSC) in the
controller actor and for generating PSPS-like files from a designer Ip waveform.

## `ip_waveform_export/`

Converter from a designer Ip YAML (Waveform-Editor-style, with segments and events) to the
four PSC configuration files (PSCIntConfig.xml, PSCGlobalMonConfig.xml, BTree.xml, PS.xml),
the RefGen schedule XML, a PSPS "WF" JSON guess and a pulse_schedule IDS. Runs from any
location (`python3 ip_waveform_export.py --yaml ... --out-dir ...`); tests in `tests/`
(`pytest` from that folder, PyYAML needed); pcssp reference XML assets in `reference/`.

## `psc_run/`: the eight PSC-path scripts

Scripts that build the PCS wrapper with the PSC, generate the PSC run variants and their
workflow, submit the run, and generate the PSPS-like files from the run inputs.

- `make_psc_variants.py <repo root> <python> [<nominal yaml>]`: derives the four run variants
  A_nom, B_edit, C_zhold, D_eof from `ip_waveform_export/examples/ip_105073_psc.yaml` and
  runs the converter (`--cut-at 84.317598 --psc-config --refgen`) into
  `cases/input/psc/<V>/`. The nominal Ip reference defaults to the one already stored in
  `cases/input/psc/A_nom/ip_105073_psc_A_nom.yaml`.
- `make_p2d_workflow.py <in> <out>`: adds the `ps_source` component (pulse_schedule IDS,
  sent once) and the `pulse_schedule_in_f` port to the evolutive_controller workflow.ymmsl.
- `make_psc_workflow.py <in> <out>`: switches the magnetic_controller implementation to
  `magnetic_controller_psc` (`workflows/lib/psc_programs.ymmsl`).
- `build_psc_controller_wrapper.m`: MATLAB function that builds
  `controllers/CCS/pcssp_controller_and_ps_psc.slx` (the fork wrapper with the PSC in the Ip
  path) and compile-checks it with a PSC configuration folder.
- `build_psc_controller.sh`: Slurm job around `build_psc_controller_wrapper.m` (PCS + IMAS-MATLAB modules).
- `run_psc_evolutive.sh`: Slurm job that builds the case `cases/evolutive_controller_105073_psc_<V>`
  (the pulse_schedule IDS generated from the variant YAML, the two workflow scripts above, the
  case override expanded with envsubst) and runs it with `bin/pds-run-case.sbatch`;
  `VARIANT=A_nom|B_edit|C_zhold|D_eof|SMOKE`.
- `make_psc_two_file_set.py [V] [--out-dir DIR]`: writes the two-file designer equivalent
  (`<V>_waveforms.yaml` in the Waveform-Editor format, `<V>_segments.yaml` segment chain) of a
  variant's converter YAML. Default output `cases/input/psc/<V>/psps_like/`.
- `make_psc_psps_dataset.py [--out-dir DIR]`: writes the PSPS-equivalent PCS dataset JSON
  `psps_pcs_dataset_<V>.json` from the variant's YAML, refgen export, the four PSC files and
  the case override (same default output folder). Needs `PCS_PATH` for the real KCURR gains.

Submit the two Slurm scripts from the repo root (their `#SBATCH -o` paths are relative to it,
create `cases/runs/psc5_logs` or `cases/runs/psc4_logs` first), or use `sbatch --chdir`.

## Inputs and outputs in the repository

- The pulse_schedule IDS (DD 4.0.0) with the designer Ip reference is not stored: it is
  generated at run time by `run_psc_evolutive.sh` into `<case>/pulse_schedule_ids/ids/` from the
  variant's designer YAML with the converter `--ids` (needs imas-python, provided by the PDS
  module), read by `ps_source` and sent once to the controller's `pulse_schedule_in_f` port.
- `cases/input/psc/<V>/`: the PSC configuration of each variant (converter YAML, refgen XML,
  `psc_config_ip_105073_psc_<V>/` with the four PSC files).
- `cases/overrides/evolutive_controller_105073_psc_*.ymmsl`: the case overrides (variants A-D
  and the 0.2 s smoke window). Paths are written with `${PDS_REPO}` (repo root) and `${CASE_DIR}`
  (case folder) placeholders, expanded by `run_psc_evolutive.sh` (`envsubst '${PDS_REPO} ${CASE_DIR}'`,
  as `bin/pds-create-case` does): muscle_manager does not expand them, so expand the file first
  when passing it to `bin/pds-run-case` by hand.
- Controller glue in `controllers/CCS/` (`*_psc.*`, `psc_*.m`) and
  `workflows/lib/psc_programs.ymmsl`.

## Dependencies

- `local_installs/pcs-nightly`: the PCS framework with the Pulse Supervision Controller, a PDS
  local dependency installed by `pds_setup.sh` with `INSTALL_PCS_NIGHTLY="true"`
  (`setup_files/setup_pcs_nightly.sh`): `pcs` (`ssh://git@git.iter.org/pcs/pcs.git`, branch
  `master`) with `pcssp-nightly` (`ssh://git@git.iter.org/pcs/pcssp-nightly.git`, branch
  `merge_IGZ_PSC`, the only line carrying the PSC `src/psc/PSC.slx`) cloned under its `pcssp/`
  and the `scdds` submodule initialised. Both need SSH access to git.iter.org. `pds_setup.sh`
  pins the tested reference, pcs `aa217bc` and pcssp-nightly `ebf3ee0` (`PIN_PCS_NIGHTLY_PCS`,
  `PIN_PCSSP_NIGHTLY`; set empty to follow the branch tips). Used by `build_psc_controller.sh`,
  `make_psc_psps_dataset.py` and the actor in `workflows/lib/psc_programs.ymmsl`.
- MATLAB chain from the PDS modules: `PCS/2026.08-pds` (MATLAB with the muscle3 venv) and
  `IMAS-MATLAB/5.6.0-intel-2025b-DD-4.1.1`, loaded by `build_psc_controller.sh` and the actor script.
- `imas-python` (PDS module) for the pulse_schedule IDS export of the converter (`--ids`).

## Environment

- `PCS_PATH`: pcs + pcssp-nightly checkout; defaults to `local_installs/pcs-nightly` in
  `build_psc_controller.sh`, `make_psc_psps_dataset.py` and `workflows/lib/psc_programs.ymmsl`
  (export it to use another checkout; the scripts stop with an install hint when
  `$PCS_PATH/pcssp/src/psc` is missing).
- `PDS_REPO`: repo root; derived by the scripts when not exported.
- Site paths kept as such: `/work/projects/pds/modules/all` (modules) and
  `/scratch/users/$USER` (scratch work folders of the Slurm jobs).

The study notes, plans, figures and the P2 campaign history are kept outside this repository.
