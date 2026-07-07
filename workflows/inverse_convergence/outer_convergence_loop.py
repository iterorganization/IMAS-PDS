"""Outer Picard driver as a MUSCLE3 submodel: one full-pulse exchange per iteration.

Each iteration sends a whole-trace pulse on the O_I ports (designed target, core_profiles,
coil-current seed) and receives a whole-trace pulse on the S ports (coils from NICE, evolved
equilibrium + core_profiles from TORAX). It then restores the prescribed boundary outline on
the evolved equilibrium and iterates until the max coil-current change between iterations
drops below the tolerance. The driver only paces the iteration; the coupling itself is a
pipeline (loop -> we -> nice/lb -> torax -> loop). The boundary is held from the input IDS
until a shape editor is wired in; Ip is held by the waveform editor. Both the equilibrium
target and core_profiles go to `we` (equilibrium drives its export time base; core_profiles
is a straight port-import, mirrored through unchanged) before reaching TORAX -- there is no
longer a direct loop -> TORAX core_profiles conduit. The static machine-description lanes
(wall, pf_passive, iron_core) never change across the pulse or across iterations, so `we`
re-exports the scenario's reference copy straight to the NICE load balancer; the loop never
sees them at all.
"""
import logging
import numpy as np
from imas import DBEntry, IDSFactory
from imas.ids_defs import CLOSEST_INTERP
from libmuscle import Instance, Message
from ymmsl import Operator
from imas_muscle3.utils import get_setting_optional

logger = logging.getLogger()
IDS_LIST = ['equilibrium', 'core_profiles', 'pf_active']
S_LIST = ['equilibrium', 'core_profiles', 'pf_active']


def _split(trace, name, times):
    # Skip any t whose CLOSEST_INTERP result has a time already in the list; this prevents
    # duplicate timestamps when a downstream solver (e.g. TORAX) produces fewer output
    # slices than the input and the last slice is reused for many requested times.
    with DBEntry("imas:memory?path=/", "w") as db:
        ids = IDSFactory().new(name); ids.deserialize(trace); db.put(ids)
        slices, seen = [], set()
        for t in times:
            s = db.get_slice(name, t, CLOSEST_INTERP)
            actual_t = float(s.time[0])
            if actual_t in seen:
                continue
            seen.add(actual_t)
            slices.append(s.serialize())
        return slices


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
        Operator.F_INIT: [f"{l}_in_f" for l in IDS_LIST],
        Operator.O_I: [f"{l}_out_i" for l in IDS_LIST],
        Operator.S: [f"{l}_in_s" for l in S_LIST],
        Operator.O_F: ["equilibrium_out_f", "pf_active_out_f"],
    })
    while inst.reuse_instance():
        max_iter = int(get_setting_optional(inst, "max_iterations", 4))
        tol = float(get_setting_optional(inst, "tolerance", 1e3))
        max_slices = int(get_setting_optional(inst, "max_slices", 0))
        t_min = get_setting_optional(inst, "t_min")
        t_max = get_setting_optional(inst, "t_max")

        init = {l: inst.receive(f"{l}_in_f").data for l in IDS_LIST}
        eq_ids = IDSFactory().new("equilibrium"); eq_ids.deserialize(init["equilibrium"])
        times = [float(t) for t in eq_ids.time]
        if t_min is not None:
            times = [t for t in times if t >= float(t_min)]
        if t_max is not None:
            times = [t for t in times if t <= float(t_max)]
        if max_slices:
            times = times[:max_slices]
        boundary = _split(init["equilibrium"], "equilibrium", times)
        cp = _assemble(_split(init["core_profiles"], "core_profiles", times), "core_profiles")
        pf = _assemble(_split(init["pf_active"], "pf_active", times), "pf_active")
        t0 = times[0]
        target = _assemble(boundary, "equilibrium")
        prev = None; torax_eq = coilr = None

        for it in range(max_iter):
            # --- O_I: emit the full pulse (no receives yet) ---
            inst.send("equilibrium_out_i", Message(t0, data=target))          # -> we (+Ip) -> nice
            inst.send("pf_active_out_i", Message(t0, data=pf))           # -> nice (coil seed)
            inst.send("core_profiles_out_i", Message(t0, data=cp))       # -> we -> torax

            # --- S: receive the full pulse (coils from nice, evolved state from torax) ---
            coilr = inst.receive("pf_active_in_s").data
            torax_eq = inst.receive("equilibrium_in_s").data
            torax_cp = inst.receive("core_profiles_in_s").data

            cur = _coils(coilr)
            dI = None if prev is None else float(np.max(np.abs(cur - prev)))
            logger.info("iter %d: NICE+TORAX done (%d slices), max|dI|=%s", it, len(times), dI)
            prev = cur

            # Feedback: next target = TORAX-evolved profiles with the prescribed boundary.
            # _split deduplicates CLOSEST_INTERP results, so ev is shorter than boundary
            # when TORAX stops early (SimError). Pad to the full boundary length so the
            # next iteration receives a full target and TORAX runs the full pulse.
            ev = _split(torax_eq, "equilibrium", times)
            if len(ev) < len(boundary):
                logger.info("iter %d: TORAX covered %d/%d slices; padding remaining from boundary", it, len(ev), len(boundary))
                ev = ev + boundary[len(ev):]
            target = _assemble([_hold_boundary(ev[i], boundary[i]) for i in range(len(ev))], "equilibrium")
            cp = _assemble(_split(torax_cp, "core_profiles", times), "core_profiles")
            # pf = coilr

            if dI is not None and dI < tol:
                logger.info("converged at iteration %d", it); break
            if it == max_iter - 1:
                logger.info("reached max_iterations=%d", max_iter); break

        inst.send("equilibrium_out_f", Message(t0, data=torax_eq))
        inst.send("pf_active_out_f", Message(t0, data=coilr))
        logger.info("sent %d final slices", len(times))


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
    main()
