"""PSC-4: derive the PSC case workflow.ymmsl from the P2d one (make_p2d_workflow.py output):
magnetic_controller keeps its name, ports and conduits; only its implementation becomes
magnetic_controller_psc (workflows/lib/psc_programs.ymmsl), imported next to the original.
usage: python make_psc_workflow.py <p2d workflow.ymmsl> <out workflow.ymmsl>
"""

import sys

src, dst = sys.argv[1:3]
s = open(src).read()
IMP = "- from lib.local_programs import implementation magnetic_controller\n"
NEW_IMP = IMP + "- from lib.psc_programs import implementation magnetic_controller_psc\n"
OLD = "implementation: magnetic_controller,"
NEW = "implementation: magnetic_controller_psc,"
if s.count(IMP) != 1 or s.count(OLD) != 1:
    sys.exit(f"expected one import and one magnetic_controller implementation, found {s.count(IMP)}, {s.count(OLD)}")
open(dst, "w").write(s.replace(IMP, NEW_IMP).replace(OLD, NEW))
print(f"{dst}: magnetic_controller -> implementation magnetic_controller_psc")
