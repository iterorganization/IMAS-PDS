"""MUSCLE3 actor overlaying one IDS on top of another.

Two IDSs of the same kind arrive per channel -- a `base` and an `overlay` -- and the
merged result goes out: every node the overlay has a value for is written over the base,
and everything the overlay is silent about keeps the base's value. Nothing is
interpolated, resampled or reconciled; the two must already be on the same time base and
the actor refuses to run if they are not.

It exists because the waveform actor no longer reads MUSCLE ports: a pulse design is a
set of nodes read from disk and evaluated on a time base, with no notion of an incoming
IDS to build on. Where a workflow used to hand the designer an IDS to fill in around
(the evolved state coming back round an iteration loop, say), it now sends that IDS here
as the `base` and the design's output as the `overlay`.

Ports, per IDS channel (see `CHANNELS`), all three connected or none:

    base_<ids>      F_INIT  the IDS to start from
    overlay_<ids>   F_INIT  the IDS to write over it
    <ids>_out       O_F     the result

One instance can carry several channels; each is merged and sent independently, in
`CHANNELS` order. The outgoing message carries the base message's timestamps.

Anything ambiguous is a crash, not a guess -- see `check_time` and `merge`. In a
converged-loop workflow both inputs descend from the same driver message, so a
disagreement means something upstream is wrong rather than merely unusual.
"""

import logging

import numpy as np
from imas import IDSFactory
from imas.ids_defs import IDS_TIME_MODE_HOMOGENEOUS
from imas.ids_struct_array import IDSStructArray
from imas.ids_structure import IDSStructure
from imas_muscle3.utils import get_setting_optional
from libmuscle import Instance, InstanceFlags, Message
from ymmsl import Operator

logger = logging.getLogger()

#: IDSs this actor can carry, i.e. the `<ids>` in its port names. Same list as
#: workflows/utils/temporal_coupler.py; extend both together.
CHANNELS = [
    "equilibrium",
    "core_profiles",
    "pf_active",
    "core_sources",
    "wall",
    "pf_passive",
    "iron_core",
    "plasma_profiles",
    "plasma_sources",
    "pulse_schedule",
    "summary",
]


def base_port(channel: str) -> str:
    return f"base_{channel}"


def overlay_port(channel: str) -> str:
    return f"overlay_{channel}"


def out_port(channel: str) -> str:
    return f"{channel}_out"


def active_channels(instance: Instance) -> list[str]:
    """The channels this instance is wired for, in `CHANNELS` order.

    A channel needs all three of its ports connected. A partially wired one is a
    workflow error: receiving on an unconnected port blocks forever, and merging without
    somewhere to send the result is pointless.
    """
    channels = []
    for channel in CHANNELS:
        ports = [base_port(channel), overlay_port(channel), out_port(channel)]
        connected = [port for port in ports if instance.is_connected(port)]
        if not connected:
            continue
        if len(connected) != len(ports):
            missing = [port for port in ports if port not in connected]
            raise RuntimeError(
                f"channel '{channel}' is only half wired: {', '.join(connected)} "
                f"connected, but {', '.join(missing)} not. Connect all three, or none."
            )
        channels.append(channel)

    if not channels:
        raise RuntimeError(
            "no channel is connected: wire base_<ids>, overlay_<ids> and <ids>_out for "
            f"at least one of {', '.join(CHANNELS)}"
        )
    logger.info("merging %s", ", ".join(channels))
    return channels


def deserialize(data, channel: str, port: str, factory: IDSFactory):
    """The `channel` IDS carried by a message received on `port`."""
    if data is None:
        raise RuntimeError(f"no data received on '{port}': nothing to merge")
    ids = factory.new(channel)
    ids.deserialize(data)
    return ids


def check_time(channel: str, base, overlay) -> None:
    """Refuse anything but two IDSs sharing one homogeneous time base.

    The merge writes overlay node onto base node with no regard for time, so it is only
    meaningful if index i means the same instant on both sides. Rather than trust that,
    check it: a heterogeneous IDS has no single root /time to compare, and two time
    arrays that differ mean the two sides were built for different pulses.
    """
    for role, ids, port in (
        ("base", base, base_port(channel)),
        ("overlay", overlay, overlay_port(channel)),
    ):
        if int(ids.ids_properties.homogeneous_time) != IDS_TIME_MODE_HOMOGENEOUS:
            raise RuntimeError(
                f"the {role} '{channel}' on '{port}' is not in homogeneous time mode, "
                "so its root /time is not the time base of its data. This actor merges "
                "homogeneous IDSs only."
            )

    base_time = np.asarray(base.time, dtype=float)
    overlay_time = np.asarray(overlay.time, dtype=float)

    if base_time.size == 0 or overlay_time.size == 0:
        empty = "base" if base_time.size == 0 else "overlay"
        raise RuntimeError(
            f"the {empty} '{channel}' has an empty root /time; there is no time base to "
            "merge on"
        )

    if base_time.shape != overlay_time.shape:
        raise RuntimeError(
            f"'{channel}': base has {base_time.size} time step(s) "
            f"({base_time[0]:g}..{base_time[-1]:g}), overlay has {overlay_time.size} "
            f"({overlay_time[0]:g}..{overlay_time[-1]:g}). Both sides must be evaluated "
            "on the same time base."
        )

    differing = np.flatnonzero(base_time != overlay_time)
    if differing.size:
        i = int(differing[0])
        raise RuntimeError(
            f"'{channel}': the two time bases have {base_time.size} step(s) each but "
            f"differ from step {i} on: base {float(base_time[i])!r} vs overlay "
            f"{float(overlay_time[i])!r} ({differing.size} step(s) differ in total)"
        )


def merge(base, overlay, channel: str, path: str = "") -> None:
    """Write every filled node of `overlay` into `base`, in place.

    Recurses over the overlay rather than the base, so a node the overlay never sets is
    left exactly as the base had it -- that is what lets a pulse design stay a
    description of the nodes it owns instead of a whole IDS.
    """
    for child in overlay:
        if not child.has_value:
            continue
        name = child.metadata.name
        here = f"{path}/{name}" if path else name
        target = base[name]

        if isinstance(child, IDSStructArray):
            if len(child) > len(target):
                raise RuntimeError(
                    f"'{channel}': the overlay's {here} has {len(child)} element(s) but "
                    f"the base's has {len(target)}. Merging would have to invent the "
                    "missing base elements, so it stops here instead: either have the "
                    "base supply them, or take this IDS straight from its producer "
                    "without merging."
                )
            for i, item in enumerate(child):
                merge(target[i], item, channel, f"{here}({i + 1})")
        elif isinstance(child, IDSStructure):
            merge(target, child, channel, here)
        else:
            base[name] = child.value


def main() -> None:
    instance = Instance(
        {
            Operator.F_INIT: [base_port(c) for c in CHANNELS]
            + [overlay_port(c) for c in CHANNELS],
            Operator.O_F: [out_port(c) for c in CHANNELS],
        },
        InstanceFlags.KEEPS_NO_STATE_FOR_NEXT_USE,
    )

    while instance.reuse_instance():
        # Both sides are converted to this DD version on deserialize. Left unset it is
        # whatever the environment's default DD is, which is what the rest of a PDS
        # workflow runs on.
        dd_version = get_setting_optional(instance, "dd_version")
        factory = IDSFactory(dd_version) if dd_version else IDSFactory()

        channels = active_channels(instance)

        # Every F_INIT receive first, then every O_F send -- interleaving them per
        # channel works, but the MMSF validator (rightly) warns about it: a submodel
        # that sends before it has finished receiving can deadlock against a peer that
        # does the same in the opposite order.
        received = {
            channel: (
                instance.receive(base_port(channel)),
                instance.receive(overlay_port(channel)),
            )
            for channel in channels
        }

        for channel in channels:
            base_msg, overlay_msg = received[channel]

            if base_msg.timestamp != overlay_msg.timestamp:
                # Not fatal -- the merge is driven by the IDSs' own time bases, which
                # are checked below -- but the two sides being at different simulated
                # times is worth knowing about.
                logger.warning(
                    "'%s': base is at t=%s but overlay is at t=%s; sending the base's "
                    "timestamp",
                    channel,
                    base_msg.timestamp,
                    overlay_msg.timestamp,
                )

            base = deserialize(base_msg.data, channel, base_port(channel), factory)
            overlay = deserialize(
                overlay_msg.data, channel, overlay_port(channel), factory
            )

            check_time(channel, base, overlay)
            merge(base, overlay, channel)
            logger.info(
                "merged '%s' on %d time step(s)", channel, np.asarray(base.time).size
            )

            instance.send(
                out_port(channel),
                Message(base_msg.timestamp, base_msg.next_timestamp, base.serialize()),
            )


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    main()
