"""Derive the case workflow.ymmsl of the PSC (and PSC + MCLS) cases from workflows/evolutive_controller/workflow.ymmsl:
magnetic_controller keeps its name, ports and conduits; only its implementation becomes
magnetic_controller_psc (workflows/lib/local_programs.ymmsl), imported next to the original.
Called by workflows/evolutive_controller/run_psc_cases.sh.
usage: python make_psc_workflow.py <workflow.ymmsl in> <workflow.ymmsl out>
"""

import sys
from pathlib import Path

src, dst = sys.argv[1:3]
s = Path(src).read_text()
IMP = "- from lib.local_programs import implementation magnetic_controller\n"
NEW_IMP = (
    IMP + "- from lib.local_programs import implementation magnetic_controller_psc\n"
)
OLD = "implementation: magnetic_controller,"
NEW = "implementation: magnetic_controller_psc,"
if s.count(IMP) != 1 or s.count(OLD) != 1:
    sys.exit(
        f"expected one import and one magnetic_controller implementation, found {s.count(IMP)}, {s.count(OLD)}"
    )
Path(dst).write_text(s.replace(IMP, NEW_IMP).replace(OLD, NEW))
print(f"{dst}: magnetic_controller -> implementation magnetic_controller_psc")
