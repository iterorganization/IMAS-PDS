"""Drives METIS slice-by-slice behind a whole-trace interface.

lib/design's `transport` hole is TORAX-shaped: whole traces in on F_INIT, whole traces out
on O_F, one exchange per Picard iteration. METIS does not work that way -- read from its
sources:

  * get_ids_time_slice.m emits ids_get_slice(..., t_cur, 2), so every output port carries
    ONE slice per reuse iteration.
  * metis4muscle3_make_external_data.m reduces a received core_profiles/core_sources to
    profiles_1d{end}, i.e. the last slice, then accumulates it across iterations. Handing
    it a whole trace silently discards everything but the final slice.
  * metis4muscle3_update_metis_input_on_equilibrium.m is the exception: it loops all
    received equilibrium slices and interpolates to METIS's own time.
  * get_metis_input_from_muscle3.m builds METIS's actual input (cons1t/geo1t/option) from
    the pulse_schedule port, and errors with "No input data available for METIS" if none
    is connected. Equilibrium is not an input source -- it only supplies the time stamp
    and constrains a run that already has input.

So this actor sits between the hole and METIS: it takes the whole traces, splits them per
time, calls METIS once per slice, collects the per-slice replies and reassembles whole
traces. The design graph never learns that METIS is different.

UNLIKE nice_load_balancer, which this is otherwise modelled on, there is no scatter over
workers and no in-flight window. NICE solves each slice independently, so it parallelises;
METIS integrates forward in time and carries state between calls
(manage_external_data_accumulation appends by increasing time, overwrites at equal time,
rewinds on a decreasing one). Slices therefore go out strictly in time order, one at a
time, each awaiting its reply. One METIS peer, never a set.
"""

import logging

from imas import DBEntry, IDSFactory
from imas.ids_defs import CLOSEST_INTERP
from libmuscle import Instance, Message
from ymmsl.v0_2 import Operator

logger = logging.getLogger()

# pulse_schedule is what METIS actually builds its input from
# (get_metis_input_from_muscle3.m). The design hole does not carry one, so it arrives from
# a source inside lib/transport_metis.ymmsl rather than from the hole -- but it still has
# to be re-sent on every call, because METIS re-reads its inputs each reuse iteration.
FWD_LANES = ["equilibrium", "core_profiles", "core_sources", "pulse_schedule"]
RES_LANES = ["equilibrium", "core_profiles"]


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
        Operator.O_I: [f"{l}_call" for l in FWD_LANES],
        Operator.S: [f"{l}_reply" for l in RES_LANES],
        Operator.O_F: [f"{l}_out_f" for l in RES_LANES],
    })
    while inst.reuse_instance():
        traces = {l: inst.receive(f"{l}_in").data for l in FWD_LANES}

        with DBEntry("imas:memory?path=/", "w") as db:
            eq = IDSFactory().new("equilibrium"); eq.deserialize(traces["equilibrium"])
            db.put(eq)
            times = [float(t) for t in db.get("equilibrium").time]
        n = len(times)
        per = {l: _split(traces[l], l, times) for l in FWD_LANES}
        logger.info("metis_driver: %d slices, t=%.4g..%.4g, sequential (METIS is stateful)",
                    n, times[0], times[-1])

        res = {l: [None] * n for l in RES_LANES}
        for k, t in enumerate(times):
            for l in FWD_LANES:
                inst.send(f"{l}_call", Message(t, data=per[l][k]))
            for l in RES_LANES:
                res[l][k] = inst.receive(f"{l}_reply").data

        for l in RES_LANES:
            inst.send(f"{l}_out_f", Message(times[0], data=_assemble(res[l], l)))


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
    main()
