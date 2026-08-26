"""Drives METIS slice-by-slice behind a whole-trace interface.

lib/design's `transport` hole is TORAX-shaped: whole traces in on F_INIT, whole traces out
on O_F, one exchange per Picard iteration. METIS instead works per reuse iteration:

  * every output port carries ONE slice per iteration;
  * a received core_profiles/core_sources is reduced to its LAST slice and accumulated
    across iterations, so a whole trace silently loses everything else;
  * the equilibrium is the exception -- all received slices are interpolated to METIS's
    own time;
  * METIS builds its actual input from the pulse_schedule port and fails without one. The
    equilibrium only supplies the timestamp and constrains a run that has input already.

So this actor splits the whole traces, calls METIS once per slice, and reassembles the
replies. The design graph never learns that METIS is different.

Unlike nice_load_balancer, which this is otherwise modelled on, there is no scatter over
workers: NICE solves slices independently, but METIS integrates forward and carries state
between calls, so slices go out strictly in time order, one at a time, each awaiting its
reply. One METIS peer, never a set.
"""

import logging

from imas import DBEntry, IDSFactory
from imas.ids_defs import CLOSEST_INTERP
from libmuscle import Instance, Message
from ymmsl.v0_2 import Operator

logger = logging.getLogger()

# The design graph carries no pulse_schedule, so it comes from a source inside the
# `transport_metis` model (workflows/metis_convergence/workflow.ymmsl) -- and must be
# re-sent every call, since METIS re-reads its inputs each reuse iteration.
FWD_LANES = ["equilibrium", "core_profiles", "core_sources", "pulse_schedule"]
RES_LANES = ["equilibrium", "core_profiles"]


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


def main() -> None:
    inst = Instance(
        {
            Operator.F_INIT: [f"{lane}_in" for lane in FWD_LANES],
            Operator.O_I: [f"{lane}_call" for lane in FWD_LANES],
            Operator.S: [f"{lane}_reply" for lane in RES_LANES],
            Operator.O_F: [f"{lane}_out_f" for lane in RES_LANES],
        }
    )
    # Only the lanes actually wired to METIS. The coupling METIS is known to work in does
    # not feed it an equilibrium at all -- it computes its own -- so lib/transport_metis can
    # leave that conduit out, and this keeps the driver working either way.
    fwd = [lane for lane in FWD_LANES if inst.is_connected(f"{lane}_call")]
    res_lanes = [lane for lane in RES_LANES if inst.is_connected(f"{lane}_reply")]

    while inst.reuse_instance():
        traces = {
            lane: inst.receive(f"{lane}_in").data
            for lane in FWD_LANES
            if inst.is_connected(f"{lane}_in")
        }

        # `traces` is keyed by which `_in` ports are wired, `fwd` by which `_call` ports
        # are. They are allowed to differ, so neither can be indexed by the other's keys
        # without checking -- a rewiring would otherwise surface as a bare KeyError with
        # nothing naming the port that is missing.
        if "equilibrium" not in traces:
            raise RuntimeError(
                "metis_driver: equilibrium_in is not connected, and the slice times are"
                " taken from it. Wire it, or teach the driver another time source."
            )

        with DBEntry("imas:memory?path=/", "w") as db:
            eq = IDSFactory().new("equilibrium")
            eq.deserialize(traces["equilibrium"])
            db.put(eq)
            times = [float(t) for t in db.get("equilibrium").time]
        n = len(times)
        if missing := [lane for lane in fwd if lane not in traces]:
            logger.warning(
                "metis_driver: %s wired for _call but not _in; not forwarding",
                ",".join(missing),
            )
            fwd = [lane for lane in fwd if lane in traces]
        per = {lane: _split(traces[lane], lane, times) for lane in fwd}
        logger.info(
            "metis_driver: %d slices, t=%.4g..%.4g, sequential (METIS is stateful);"
            " forwarding %s, expecting %s",
            n,
            times[0],
            times[-1],
            ",".join(fwd),
            ",".join(res_lanes),
        )

        # Every call needs a finite next_timestamp, including the last one of the pass.
        # METIS latches metis_exit the moment it sees a non-finite t_next
        # (metis4muscle3.m:975) and nothing ever clears it -- not even a reuse_instance()
        # that returns True -- so telling it "no next slice" at the end of a pass shuts it
        # down for good, and the following Picard pass finds no peer. The last slice gets
        # an extrapolated stamp instead; METIS's reuse loop is ended by its ports closing
        # when this actor shuts down, which is how MUSCLE3 expects it to end.
        step = (times[-1] - times[0]) / (n - 1) if n > 1 else 1.0

        res = {lane: [None] * n for lane in res_lanes}
        for k, t in enumerate(times):
            nxt = times[k + 1] if k + 1 < n else times[-1] + step
            for lane in fwd:
                inst.send(f"{lane}_call", Message(t, nxt, per[lane][k]))
            for lane in res_lanes:
                res[lane][k] = inst.receive(f"{lane}_reply").data

        for lane in RES_LANES:
            if not inst.is_connected(f"{lane}_out_f"):
                continue
            # A lane METIS was not asked for is echoed back unchanged, so the design loop
            # still sees the whole trace it expects on that port.
            data = _assemble(res[lane], lane) if lane in res_lanes else traces.get(lane)
            if data is not None:
                inst.send(f"{lane}_out_f", Message(times[0], data=data))


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    main()
