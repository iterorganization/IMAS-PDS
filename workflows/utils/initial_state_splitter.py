"""
MUSCLE3 actor splitting a per-step IDS stream into an initial message and a
per-step tail.

Some MUSCLE3 actors (e.g. metis4muscle3, driven by imas_muscle3's
source_component conventions) emit their initial state on their O_I ports
right after F_INIT -- before reading any S input -- and then one further
state per step, so their O_I stream carries N+1 messages, the first with
next_timestamp=None. A peer actor with a genuine time loop (e.g.
nice_imas_evo_rd_muscle3's `while(has_t_next)`) instead expects the initial
state on its own F_INIT ports and exactly one message per step on its S
ports, and stops its time loop as soon as an S message arrives without a
next_timestamp -- so wiring the two directly makes the peer consume the
initial message as its first step and exit early.

This actor sits in between: for each connected IDS channel, it forwards the
first message received on `<channel>_in` to `<channel>_init_out` (wire to
the peer's F_INIT), and every following message to `<channel>_out` (wire to
the peer's S), unchanged.
"""

import logging

from libmuscle import Instance, InstanceFlags
from ymmsl import Operator

logger = logging.getLogger()

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


def main() -> None:
    ports = {
        Operator.S: [f"{channel}_in" for channel in CHANNELS],
        Operator.O_I: (
            [f"{channel}_init_out" for channel in CHANNELS]
            + [f"{channel}_out" for channel in CHANNELS]
        ),
    }
    instance = Instance(ports, InstanceFlags.SKIP_MMSF_SEQUENCE_CHECKS)

    active = [c for c in CHANNELS if instance.is_connected(f"{c}_in")]
    for channel in CHANNELS:
        for out_suffix in ("_init_out", "_out"):
            port = f"{channel}{out_suffix}"
            if instance.is_connected(port) and channel not in active:
                raise RuntimeError(
                    f"'{port}' is connected but '{channel}_in' is not -- "
                    "an output channel needs its matching input wired."
                )
    logger.info("active channels: %s", active)

    while instance.reuse_instance():
        logger.info("receiving initial state on: %s", active)
        for channel in active:
            msg = instance.receive(f"{channel}_in")
            if instance.is_connected(f"{channel}_init_out"):
                instance.send(f"{channel}_init_out", msg)

        logger.info("streaming per-step state on: %s", active)
        running = list(active)
        while running:
            for channel in list(running):
                msg = instance.receive(f"{channel}_in")
                if instance.is_connected(f"{channel}_out"):
                    instance.send(f"{channel}_out", msg)
                if msg.next_timestamp is None:
                    running.remove(channel)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    main()
