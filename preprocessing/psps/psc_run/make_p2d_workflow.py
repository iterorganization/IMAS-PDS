"""P2d: derive a case workflow.ymmsl from the fork's workflows/evolutive_controller/workflow.ymmsl
(IMAS-PDS fork, branch torax-evolutive @5620eb5) in which the designer Ip reference comes from a
pulse_schedule IDS on disk (ip_waveform_export --ids).

Adds ONE source_component `ps_source` (o_i: pulse_schedule_out), the F_INIT port
pulse_schedule_in_f on magnetic_controller and the conduit
ps_source.pulse_schedule_out -> magnetic_controller.pulse_schedule_in_f. Every other line is
copied unchanged (ymmsl 0.17 allows `models:` in only one stacked file, so this cannot be an
overlay). usage: python make_p2d_workflow.py <workflow.ymmsl in> <workflow.ymmsl out>
"""

import sys

src, dst = sys.argv[1:3]
lines = open(src).read().splitlines(keepends=True)
OLD_PORTS = "ports: {f_init: [equilibrium_in_f, pf_active_in_f], s:"
NEW_PORTS = "ports: {f_init: [equilibrium_in_f, pf_active_in_f, pulse_schedule_in_f], s:"
COMP = (
    "      ps_source: {description: designer pulse_schedule IDS (ip_waveform_export --ids; "
    "Ip reference for KCURR) sent once, implementation: source_component, "
    "ports: {o_i: [pulse_schedule_out]}}\n"
)
CONDUIT = "      ps_source.pulse_schedule_out: magnetic_controller.pulse_schedule_in_f\n"
out, n = [], [0, 0]
for ln in lines:
    s = ln.strip()
    if s.startswith("magnetic_controller: {") and OLD_PORTS in ln:
        out.append(ln.replace(OLD_PORTS, NEW_PORTS))
        out.append(COMP)
        n[0] += 1
        continue
    out.append(ln)
    if s.startswith("magnetic_controller.pf_active_out_i:"):
        out.append(CONDUIT)
        n[1] += 1
if n != [1, 1]:
    sys.exit(f"expected 1 controller component and 1 controller conduit, found {n}")
open(dst, "w").write("".join(out))
print(f"{dst}: ps_source + pulse_schedule_in_f added (1 component, 1 port, 1 conduit)")
