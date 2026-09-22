"""Re-gauge an equilibrium trace's poloidal flux onto its designed psi_boundary.

Whole trace in on F_INIT, whole trace out on O_F, one lane. Each time slice's
profiles_1d.psi is shifted so its edge value lands on that slice's
global_quantities.psi_boundary.

NICE inverse derives its desired boundary flux, and the normalization of the
p'/ff' coordinate, from profiles_1d.psi[-1] (`ReadDataInverseProblemSlice`), so
whatever gauge the equilibrium arrives in becomes the coil-current target.
Anchoring it on the designed psi_boundary ties every Picard iteration to the
designed transformer-flux state; p'(psi)/ff'(psi) are invariant under the shift.
Iteration 1 needs no shift (the DINA target is already in that gauge), but from
iteration 2 on the equilibrium comes back through TORAX in its own gauge, tens
of Wb away. Slices without psi_boundary or without a psi profile pass through
unchanged.

`nice_load_balancer` applies the same shift per slice as it scatters; this actor
is how the batch-mode inverse (whole trace straight into one NICE) keeps it.
"""

import logging

import numpy as np
from imas import IDSFactory
from libmuscle import Instance, Message
from ymmsl.v0_2 import Operator

logger = logging.getLogger()


def anchor_psi(eq):
    """Shift every time slice's profiles_1d.psi so psi[-1] == psi_boundary.

    Mutates `eq` (an equilibrium IDS) in place. Returns one shift per time slice,
    None where the slice carries no anchor or no psi profile.
    """
    shifts = []
    for ts in eq.time_slice:
        gq, p1 = ts.global_quantities, ts.profiles_1d
        if not gq.psi_boundary.has_value or not len(p1.psi):
            shifts.append(None)
            continue
        shift = float(gq.psi_boundary) - float(p1.psi[-1])
        if shift != 0.0:
            p1.psi = np.asarray(p1.psi) + shift
        shifts.append(shift)
    return shifts


def main() -> None:
    inst = Instance(
        {
            Operator.F_INIT: ["equilibrium_in"],
            Operator.O_F: ["equilibrium_out"],
        }
    )
    while inst.reuse_instance():
        msg = inst.receive("equilibrium_in")
        eq = IDSFactory().new("equilibrium")
        eq.deserialize(msg.data)
        shifts = anchor_psi(eq)
        done = [s for s in shifts if s is not None]
        logger.info(
            "psi_anchor: re-gauged %d/%d slices (max |shift| %.3g Wb)",
            len(done),
            len(shifts),
            max((abs(s) for s in done), default=0.0),
        )
        inst.send("equilibrium_out", Message(msg.timestamp, data=eq.serialize()))


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    main()
