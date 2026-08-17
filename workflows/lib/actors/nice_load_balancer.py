"""IMAS-aware NICE load balancer: whole-trace in, parallel per-slice NICE, whole-trace out.

Receives the five NICE-inverse input lanes as WHOLE-TRACE IDSs (one message each) from the
loop driver, slices them per time (get_slice, in memory), scatters the per-slice calls over
W unmodified nice_imas_inv workers round-robin (slot = k % W, W in flight), gathers the
equilibrium+pf_active results FIFO-per-slot in original order, reassembles them into
whole-trace IDSs (put_slice), and sends those back to the loop. This keeps the driver
working purely on whole traces -- the per-slice/scatter/gather/assemble all live here.

Lanes fixed to the NICE inverse contract. STATIC lanes (wall/pf_passive/iron_core) are
forwarded whole to every worker call (NICE re-reads them each F_INIT); the rest are sliced.

Each equilibrium slice is re-gauged before scatter (_anchor_psi). NICE derives its desired
boundary flux, and the normalization of the p'/ff' coordinate, from profiles_1d.psi[-1], so
whatever gauge the Picard state is in would become the coil-current target. Shifting the
whole psi array so its edge lands on the designed global_quantities.psi_boundary anchors
every iteration to the designed transformer-flux state; p'(psi)/ff'(psi) are invariant
under it. Slices without psi_boundary or without a psi profile pass through unchanged.
"""

import logging

import numpy as np
from imas import DBEntry, IDSFactory
from imas.ids_defs import CLOSEST_INTERP
from libmuscle import Instance, Message
from ymmsl.v0_2 import Operator

logger = logging.getLogger()

FWD_LANES = ["equilibrium", "wall", "pf_active", "pf_passive", "iron_core"]
RES_LANES = ["equilibrium", "pf_active"]
STATIC = {"wall", "pf_passive", "iron_core"}  # forwarded whole to each call, not sliced


def _split(trace, name, times):
    with DBEntry("imas:memory?path=/", "w") as db:
        ids = IDSFactory().new(name)
        ids.deserialize(trace)
        db.put(ids)
        return [db.get_slice(name, t, CLOSEST_INTERP).serialize() for t in times]


def _assemble(slices, name):
    with DBEntry("imas:memory?path=/", "w") as db:
        for s in slices:
            ids = IDSFactory().new(name)
            ids.deserialize(s)
            db.put_slice(ids)
        return db.get(name).serialize()


def _anchor_psi(ser):
    """Shift one equilibrium slice's profiles_1d.psi so psi[-1] == the designed
    psi_boundary (see module docstring). Returns (slice, shift) -- shift is None
    when the slice carries no anchor or no psi profile."""
    eq = IDSFactory().new("equilibrium")
    eq.deserialize(ser)
    ts = eq.time_slice[0]
    if not ts.global_quantities.psi_boundary.has_value or not len(ts.profiles_1d.psi):
        return ser, None
    shift = float(ts.global_quantities.psi_boundary) - float(ts.profiles_1d.psi[-1])
    if shift == 0.0:
        return ser, 0.0
    ts.profiles_1d.psi = np.asarray(ts.profiles_1d.psi) + shift
    return eq.serialize(), shift


def main() -> None:
    inst = Instance(
        {
            Operator.F_INIT: [f"{lane}_in" for lane in FWD_LANES],
            Operator.O_I: [f"{lane}_scatter[]" for lane in FWD_LANES],
            Operator.S: [f"{lane}_gather[]" for lane in RES_LANES],
            Operator.O_F: [f"{lane}_out_f" for lane in RES_LANES],
        }
    )
    while inst.reuse_instance():
        traces = {lane: inst.receive(f"{lane}_in").data for lane in FWD_LANES}
        with DBEntry("imas:memory?path=/", "w") as db:
            eq = IDSFactory().new("equilibrium")
            eq.deserialize(traces["equilibrium"])
            db.put(eq)
            times = [float(t) for t in db.get("equilibrium").time]
        n = len(times)
        per = {
            lane: _split(traces[lane], lane, times)
            for lane in FWD_LANES
            if lane not in STATIC
        }
        anchored = [_anchor_psi(s) for s in per["equilibrium"]]
        per["equilibrium"] = [s for s, _ in anchored]
        shifts = [sh for _, sh in anchored if sh is not None]
        w = inst.get_port_length(f"{FWD_LANES[0]}_scatter")
        logger.info(
            "nice_load_balancer: %d slices over %d workers; psi re-gauged on %d/%d slices"
            " (max |shift| %.3g Wb)",
            n,
            w,
            len(shifts),
            n,
            max((abs(s) for s in shifts), default=0.0),
        )

        res = {lane: [None] * n for lane in RES_LANES}
        started = done = 0
        while done < n:
            while started - done < w and started < n:
                slot, t = started % w, times[started]
                for lane in FWD_LANES:
                    data = traces[lane] if lane in STATIC else per[lane][started]
                    inst.send(f"{lane}_scatter", Message(t, data=data), slot)
                started += 1
            for lane in RES_LANES:
                res[lane][done] = inst.receive(f"{lane}_gather", done % w).data
            done += 1

        for lane in RES_LANES:
            inst.send(
                f"{lane}_out_f", Message(times[0], data=_assemble(res[lane], lane))
            )


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    main()
