# Provenance of the third-party reference files

Copies of ITER PCS / PCSSP files, kept only as references for the converter tests (`tests/test_roundtrip.py`,
`tests/test_eh_example.py`) and for the reading rules re-implemented in `tests/psxml_rules.py`. They are not
used at run time. Checked on 2026-11-21 by comparing git blob hashes (`git hash-object` of the copy against
`git rev-parse <commit>:<path>` in the source repository).

| File | Repository | Branch | Commit (date) | Original path | Match |
|---|---|---|---|---|---|
| `PS_NominalWaveforms.xml` | `ssh://git@git.iter.org/pcs/pcs.git` | `add-AM` | `bb29ad6` (2026-08-31) | `top-models/magnetic-control/CREATE_TC_01/PSC_config/PS_NominalWaveforms.xml` | byte-identical (blob `b657df8`) |
| `BTreeNominalWaveforms.xml` | `ssh://git@git.iter.org/pcs/pcs.git` | `add-AM` | `bb29ad6` (2026-08-31) | `top-models/magnetic-control/CREATE_TC_01/PSC_config/BTreeNominalWaveforms.xml` | byte-identical (blob `41b07d9`) |
| `PS_FWHLEH.xml` | `ssh://git@git.iter.org/pcs/pcssp.git` | `PSC-FWHL` | `2233365` (2025-03-10) | `generic/psc/Tests/assets/PS_FWHLEH.xml` | byte-identical (blob `308bcd5`) |
| `BTreeFWHL.xml` | `ssh://git@git.iter.org/pcs/pcssp.git` | `PSC-FWHL` | `2233365` (2025-03-10) | `generic/psc/Tests/assets/BTreeFWHL.xml` | byte-identical (blob `6267140`) |
| `parsePSXML.m` | `ssh://git@git.iter.org/pcs/pcssp-nightly.git` | `merge_IGZ_PSC` | `ebf3ee0` (2026-08-31) | `src/psc/+REFGEN/+MODEL/parsePSXML.m` | not identical: header lines 6, 8 and 12 (author names) replaced by `[redacted]`; the code is otherwise unchanged (source blob `633d867`, copy `e86b32b`) |

Source checkouts used for the comparison: the study clones of `pcs`, `pcssp` and `pcssp-nightly` (outside this
repository); the same `parsePSXML.m` blob is in the PDS local install `local_installs/pcs-with-pcssp-nightly/pcssp`
(pcssp-nightly `ebf3ee0`).
