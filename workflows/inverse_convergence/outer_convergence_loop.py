"""Outer Picard driver as a clean MUSCLE3 submodel: one full-pulse exchange per iteration.

This driver is a Submodel-Execution-Loop component: each Picard iteration it sends a full
whole-trace pulse on its O_I ports, then receives a full whole-trace pulse on its S ports --
no interleaved request/response, so it needs no MMSF sequence-check waiver. The actual
coupling is a pipeline, not a star through this driver:

    loop --target--> we --(+Ip)--> nice (lb) --equilibrium--> torax --evolved--> loop
                                          \--coils------------------------------> loop

The loop emits the designed target (held boundary + evolved profiles), the machine-
description lanes, and the core_profiles; the waveform editor overlays the designed Ip(t)
onto the target in place; the parallel NICE inverse solves it; its equilibrium goes
*directly* to TORAX (with core_profiles from the loop); TORAX evolves the profiles and
returns them to the loop, which restores the prescribed boundary and iterates. Convergence
is the max coil-current change between iterations.

The boundary outline is held from the input IDS until the shape-editor is wired in; Ip is
held by the waveform editor (preparation for variable timestepping).
"""
import logging
import numpy as np
from imas import DBEntry, IDSFactory
from imas.ids_defs import CLOSEST_INTERP
from libmuscle import Instance, Message
from ymmsl import Operator
from imas_muscle3.utils import get_setting_optional

logger = logging.getLogger()
# Machine-description lanes the loop sends straight to the NICE load balancer (the
# equilibrium target goes to `we` instead). pf_active carries the coil-current seed and is
# refreshed from NICE each iteration; the other three are static.
LB_LANES = ["wall", "pf_active", "pf_passive", "iron_core"]
STATIC = {"wall", "pf_passive", "iron_core"}


def _split(trace, name, times):
    with DBEntry("imas:memory?path=/", "w") as db:
        ids = IDSFactory().new(name); ids.deserialize(trace); db.put(ids)
        return [db.get_slice(name, t, CLOSEST_INTERP).serialize() for t in times]


def _assemble(slices, name):
    with DBEntry("imas:memory?path=/", "w") as db:
        for s in slices:
            ids = IDSFactory().new(name); ids.deserialize(s); db.put_slice(ids)
        return db.get(name).serialize()


def _hold_boundary(evolved_ser, ref_ser):
    """Restore the prescribed boundary outline on an evolved slice; keep its profiles.

    Ip is no longer held here -- the waveform editor overlays it on the forward pass.
    """
    ev = IDSFactory().new("equilibrium"); ev.deserialize(evolved_ser)
    rf = IDSFactory().new("equilibrium"); rf.deserialize(ref_ser)
    es, rs = ev.time_slice[0], rf.time_slice[0]
    es.boundary.outline.r = rs.boundary.outline.r
    es.boundary.outline.z = rs.boundary.outline.z
    return ev.serialize()


def _coils(pf_trace):
    pf = IDSFactory().new("pf_active"); pf.deserialize(pf_trace)
    return np.array([[c.current.data[i] for c in pf.coil] for i in range(len(pf.time))])


def main() -> None:
    inst = Instance({
        Operator.O_I: ["target_out"] + [f"{l}_out" for l in LB_LANES] + ["core_profiles_out"],
        Operator.S: ["coils_in", "equilibrium_result_in", "core_profiles_result_in"],
    })
    while inst.reuse_instance():
        src_uri = inst.get_setting("source_uri"); sink_uri = inst.get_setting("sink_uri")
        max_iter = int(get_setting_optional(inst, "max_iterations", 4))
        tol = float(get_setting_optional(inst, "tolerance", 1e3))
        max_slices = int(get_setting_optional(inst, "max_slices", 0))

        with DBEntry(src_uri, "r") as src:
            times = [float(t) for t in src.get("equilibrium").time]
            if max_slices:
                times = times[:max_slices]
            statics = {l: src.get(l).serialize() for l in STATIC}
            boundary = [src.get_slice("equilibrium", t, CLOSEST_INTERP).serialize() for t in times]
            cp = _assemble([src.get_slice("core_profiles", t, CLOSEST_INTERP).serialize() for t in times], "core_profiles")
            pf = _assemble([src.get_slice("pf_active", t, CLOSEST_INTERP).serialize() for t in times], "pf_active")
        t0 = times[0]
        target = _assemble(boundary, "equilibrium")
        prev = None; torax_eq = coilr = None

        for it in range(max_iter):
            # --- O_I: emit the full pulse (no receives yet) ---
            inst.send("target_out", Message(t0, data=target))          # -> we (+Ip) -> nice
            inst.send("pf_active_out", Message(t0, data=pf))           # -> nice (coil seed)
            for l in STATIC:
                inst.send(f"{l}_out", Message(t0, data=statics[l]))    # -> nice
            inst.send("core_profiles_out", Message(t0, data=cp))       # -> torax

            # --- S: receive the full pulse (coils from nice, evolved state from torax) ---
            coilr = inst.receive("coils_in").data
            torax_eq = inst.receive("equilibrium_result_in").data
            torax_cp = inst.receive("core_profiles_result_in").data

            cur = _coils(coilr)
            dI = None if prev is None else float(np.max(np.abs(cur - prev)))
            logger.info("iter %d: NICE+TORAX done (%d slices), max|dI|=%s", it, len(times), dI)
            prev = cur

            # Feedback: next target = TORAX-evolved profiles with the prescribed boundary.
            ev = _split(torax_eq, "equilibrium", times)
            target = _assemble([_hold_boundary(ev[i], boundary[i]) for i in range(len(times))], "equilibrium")
            cp = _assemble(_split(torax_cp, "core_profiles", times), "core_profiles")
            pf = coilr

            if dI is not None and dI < tol:
                logger.info("converged at iteration %d", it); break
            if it == max_iter - 1:
                logger.info("reached max_iterations=%d", max_iter); break

        with DBEntry(sink_uri, "w") as snk:
            for s in _split(torax_eq, "equilibrium", times):
                ids = IDSFactory().new("equilibrium"); ids.deserialize(s); snk.put_slice(ids)
            for s in _split(coilr, "pf_active", times):
                ids = IDSFactory().new("pf_active"); ids.deserialize(s); snk.put_slice(ids)
        logger.info("wrote %d final slices", len(times))


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
    main()
