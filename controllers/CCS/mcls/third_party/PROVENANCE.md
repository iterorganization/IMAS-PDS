# Provenance of the third-party MCLS files

The two MATLAB files in this folder come from the ITER PCS simulation-platform library repository `pcssp-iter`.
The library defaults in `../mcls_library_defaults.yaml` come from the same commit.

| Item | Value |
|---|---|
| Repository | `ssh://git@git.iter.org/pcs/pcssp-iter.git` |
| Branch, commit | `develop`, `8b30ca4b` (2025-11-10) |
| `MCLS.m` | script of the MATLAB Function block inside the library block `MCLS` (SID 9254; inner block `MATLAB Function1`, SID 9498) of `device_lib/generic/PCSSP_iter_cc_modules.slx`, i.e. `<P Name="script">` of `simulink/stateflow/chart_150.xml` in the unzipped `.slx` (9858 characters) |
| `ReadMCmode.m` | `device_lib/MCLS/MCLS_functions/ReadMCmode.m` |
| `../mcls_library_defaults.yaml` | YAML export of `device_lib/MCLS/MCLS_publicConfiguration/Config_MCLS.mat` (struct `configMCLS`), made by `../tools/mat_to_yaml_mcls.py` |

## Authorship

The last change of all three source files in `pcssp-iter` is commit `28e4d7c9` "Pull request #72: CREATE modules GPM 3"
(2024-02-12); this commit and the earlier ones touching `device_lib/MCLS` (`81ae97f9` 2024-01-31, `9b23758b` 2022-04-26) were
committed by Timo Ravensbergen. The original developers of the MCLS block are UNVERIFIED (the pull-request title points to the
CREATE modules).

The same library block is used in the `pcs` repository (`ssh://git@git.iter.org/pcs/pcs.git`), branch `XPT02`, commit `04e9b7f`
(2026-09-24, Luigi Pangione), through a library link: `assessment/TestCases/IntegratedAssessments/XPTL02_105033_mod1/fenix_iter.slx`,
`simulink/systems/system_7353.xml`, block `MCLS` (SID 9598, `SourceBlock` = `PCSSP_iter_cc_modules/MCLS`). It is configured there by
`assessment/TestCases/IntegratedAssessments/XPTL02_105033_mod1/setup_MCLS_01.m` (`TsMCLS = 0.1`).

## Changes made for PDS

`ReadMCmode.m`: unmodified; a 6-line comment header was added at the top (the file keeps its CRLF line ends).

`MCLS.m`: modified in 4 lines, all needed for MATLAB R2025b code generation of the MATLAB Function block (the library was built
with an older release). Line numbers are those of `MCLS.m`; "chart line" is the line in the original script.

| `MCLS.m` line | Change | Why |
|---|---|---|
| 9 | comment line added (points to this file) | documentation only |
| 153 (chart line 152) | `iactualmode = inextmode(imin);` becomes `iactualmode = inextmode(imin(1));` (plus a trailing comment) | R2025b code generation rejected the assignment of a possibly variable-size index (build job 1317052). `imin` is the second output of `min(pos)`, a scalar whenever `pos` is non-empty, which is always the case in this branch (a change needs a true column other than the actual mode, and such a column is in the actual mode's `NextEnabledModes`), so the result is the same |
| 179 (added after chart line 177) | `coder.varsize('icond', [1 12], [0 1]);` | `icond` is used both as the scalar 100 and as an index vector of up to NEnablingConditions = 12 entries; code generation needs an explicit variable-size declaration (build job 1317081) |
| 186 (added after chart line 183) | `coder.varsize('ccc', [12 1], [1 0]);` | `ccc` is a scalar `true` or a logical column `Conditions(icond)` (chart line 202); same reason |

No other line differs. Check (the original is regenerated from the library and compared):

```bash
P=<clone of pcssp-iter>    # e.g. /home/ITER/schneim/public/git/pds-other-version/pcssp-iter-develop
git -C "$P" show 8b30ca4b:device_lib/generic/PCSSP_iter_cc_modules.slx > /tmp/lib.slx
unzip -p /tmp/lib.slx simulink/stateflow/chart_150.xml \
  | python3 -c 'import re,html,sys; print(html.unescape(re.search(r"<P Name=\"script\">(.*?)</P>",sys.stdin.read(),re.S).group(1)),end="")' \
  > /tmp/MCLS_orig.m
diff /tmp/MCLS_orig.m MCLS.m          # expected: 8a9 (comment), 152c153, 177a179, 183a186
git -C "$P" show 8b30ca4b:device_lib/MCLS/MCLS_functions/ReadMCmode.m | diff - ReadMCmode.m   # expected: 0a1,6 (header)
```

To re-extract after a library update: run the same commands on the new commit, re-apply the three code changes above if code
generation still needs them, update this file, re-export the defaults with `../tools/mat_to_yaml_mcls.py`, and rebuild the
controller model with `controllers/CCS/mcls/model_build/build_mcls_controller.sh` (the script is embedded in
`controllers/CCS/pcssp_controller_and_ps_mcls.slx` at build time; MCLS.m is not read at run time).

## How PDS uses them

In the library, the four non-signal arguments of the block (`MCMode`, `StartingMode`, `NAlarms`, `NEnablingConditions`) are
Parameter data filled by the subsystem mask (`system_9254.xml`, mask initialization: `ReadMCmode(MCMode, diary, MCModeFieldstruct,
AlarmsStructure, EnablingConditions)`, `rmfield(MCMode, 'Name')`, `NAlarms = length(AlarmsStructure)`,
`NEnablingConditions = length(EnablingConditions)`). PDS has no library link: `../mcls_load_table.m` reproduces the mask
initialization from a mode-table YAML and `../mcls_library_defaults.yaml`, and the controller init puts the four values in the base
workspace.
