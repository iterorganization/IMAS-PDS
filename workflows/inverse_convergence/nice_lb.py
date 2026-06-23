"""IMAS-aware NICE load balancer: whole-trace in, parallel per-slice NICE, whole-trace out.

Receives the five NICE-inverse input lanes as WHOLE-TRACE IDSs (one message each) from the
loop driver, slices them per time (get_slice, in memory), scatters the per-slice calls over
W unmodified nice_imas_inv workers round-robin (slot = k % W, W in flight), gathers the
equilibrium+pf_active results FIFO-per-slot in original order, reassembles them into
whole-trace IDSs (put_slice), and sends those back to the loop. This keeps the driver
working purely on whole traces -- the per-slice/scatter/gather/assemble all live here.

Lanes fixed to the NICE inverse contract. STATIC lanes (wall/pf_passive/iron_core) are
forwarded whole to every worker call (NICE re-reads them each F_INIT); the rest are sliced.
"""

import logging

from imas import DBEntry, IDSFactory
from imas.ids_defs import CLOSEST_INTERP
from libmuscle import Instance, Message
from ymmsl.v0_2 import Operator

logger = logging.getLogger()

FWD_LANES = ["equilibrium", "wall", "pf_active", "pf_passive", "iron_core"]
RES_LANES = ["equilibrium", "pf_active"]
STATIC = {"wall", "pf_passive", "iron_core"}  # forwarded whole to each call, not sliced


# _split/_assemble round-trip each slice through the IMAS in-memory backend (serialize ->
# put/put_slice -> get_slice/get). This reuses IMAS' own homogeneous-time handling and
# CLOSEST_INTERP resampling, so it is correct for any IDS, at the cost of a
# serialize/deserialize plus a DBEntry call per slice. A pure-Python alternative (indexing
# .time_slice[] and copying nodes directly) would avoid the backend round-trip, but would
# have to reimplement slice selection / time-mode handling per IDS and is more fragile. The
# per-slice cost here is small next to a NICE solve, so the backend round-trip is the
# deliberate default; revisit only if slice (de)serialization shows up in a profile.
def _split(trace, name, times):
    with DBEntry("imas:memory?path=/", "w") as db:
        ids = IDSFactory().new(name); ids.deserialize(trace); db.put(ids)
        return [db.get_slice(name, t, CLOSEST_INTERP).serialize() for t in times]


def _assemble(slices, name):
    with DBEntry("imas:memory?path=/", "w") as db:
        for s in slices:
            ids = IDSFactory().new(name); ids.deserialize(s); db.put_slice(ids)
        return db.get(name).serialize()


def main() -> None:
    inst = Instance({
        Operator.F_INIT: [f"{l}_in" for l in FWD_LANES],
        Operator.O_I: [f"{l}_scatter[]" for l in FWD_LANES],
        Operator.S: [f"{l}_gather[]" for l in RES_LANES],
        Operator.O_F: [f"{l}_out_f" for l in RES_LANES],
    })
    while inst.reuse_instance():
        # Receive the whole-trace inputs (F_INIT) before sending results (O_F): we can't
        # slice and scatter what we haven't received, and MUSCLE3's submodel operator order
        # (F_INIT -> O_I/S -> O_F) enforces receive-before-send regardless. Inside the loop
        # below it's the opposite -- send scatter, then gather -- to keep W solves in flight.
        traces = {l: inst.receive(f"{l}_in").data for l in FWD_LANES}
        with DBEntry("imas:memory?path=/", "w") as db:
            eq = IDSFactory().new("equilibrium"); eq.deserialize(traces["equilibrium"])
            db.put(eq)
            times = [float(t) for t in db.get("equilibrium").time]
        n = len(times)
        per = {l: _split(traces[l], l, times) for l in FWD_LANES if l not in STATIC}
        w = inst.get_port_length(f"{FWD_LANES[0]}_scatter")
        logger.info("nice_lb: %d slices over %d workers", n, w)

        res = {l: [None] * n for l in RES_LANES}
        started = done = 0
        while done < n:
            while started - done < w and started < n:
                slot, t = started % w, times[started]
                for l in FWD_LANES:
                    data = traces[l] if l in STATIC else per[l][started]
                    inst.send(f"{l}_scatter", Message(t, data=data), slot)
                started += 1
            for l in RES_LANES:
                res[l][done] = inst.receive(f"{l}_gather", done % w).data
            done += 1

        for l in RES_LANES:
            inst.send(f"{l}_out_f", Message(times[0], data=_assemble(res[l], l)))


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
    main()
