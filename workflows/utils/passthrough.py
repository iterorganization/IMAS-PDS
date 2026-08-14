"""
MUSCLE3 actor that forwards IDSs through unchanged.

Declares all four ports -- `<ids_name>_in_f` (F_INIT), `<ids_name>_in_s`
(S), `<ids_name>_out_f` (O_F), `<ids_name>_out_i` (O_I) -- for every IDS
name IMAS knows about, using the same per-channel suffix convention as
the actors in workflows/evolutive_controller/workflow.ymmsl
(e.g. torax's `equilibrium_in_f`/`equilibrium_in_s`/`equilibrium_out_i`,
magnetic_controller's `equilibrium_in_f`/`equilibrium_in_s`). A workflow
can wire up any number of IDSs, on whichever of the four ports it needs,
and this actor forwards each one through unchanged -- timestamp,
next_timestamp, data and settings all included -- to whatever is coupled
on the outgoing side.

For each IDS name, independently:
- if `_in_f` is connected, its one F_INIT message is received first;
- if `_in_s` is connected, messages are received from it in a loop until
  one arrives with no next_timestamp;
- every message received this way is forwarded immediately to `_out_i`
  if that is connected;
- the last message received is forwarded to `_out_f` if that is
  connected (O_F only ever sends once per instance run).

This lets the same actor stand in for a purely stateless F_INIT/O_F
submodel (like nice_inv), a streaming S/O_I coupler (like
temporal_coupler), or a submodel that takes an initial value via F_INIT
and then iterates via S/O_I (like magnetic_controller) -- whichever ports
a given workflow actually wires up. An IDS name with no connected input,
or no connected output, is left alone: there is nothing to receive, or
nowhere to route what was received.

The `forward_f_init` setting (bool, default True) controls whether the
F_INIT message is also forwarded to `_out_i`. Set it False for a
stand-in whose real implementation only emits corrections computed from
its S input, never its initial value verbatim (e.g. magnetic_controller)
-- otherwise a sink/recorder accumulating O_I messages into one time
series can see the F_INIT message's shape (e.g. missing fields the real
per-step messages always set) mixed in as a bogus first slice.
"""

import logging

from imas import IDSFactory
from libmuscle import Instance
from ymmsl.v0_2 import Operator

logger = logging.getLogger()

IDS_NAMES = IDSFactory().ids_names()


def main() -> None:
    instance = Instance({
        Operator.F_INIT: [f"{ids_name}_in_f" for ids_name in IDS_NAMES],
        Operator.S: [f"{ids_name}_in_s" for ids_name in IDS_NAMES],
        Operator.O_F: [f"{ids_name}_out_f" for ids_name in IDS_NAMES],
        Operator.O_I: [f"{ids_name}_out_i" for ids_name in IDS_NAMES],
    })

    while instance.reuse_instance():
        forward_f_init = instance.get_setting("forward_f_init", "bool", default=True)
        in_f = {n for n in IDS_NAMES if instance.is_connected(f"{n}_in_f")}
        in_s = {n for n in IDS_NAMES if instance.is_connected(f"{n}_in_s")}
        out_f = {n for n in IDS_NAMES if instance.is_connected(f"{n}_out_f")}
        out_i = {n for n in IDS_NAMES if instance.is_connected(f"{n}_out_i")}
        active = sorted((in_f | in_s) & (out_f | out_i))
        logger.info("passthrough: forwarding %s", active)

        for name in active:
            last = None
            if name in in_f:
                last = instance.receive(f"{name}_in_f")
                if name in out_i and forward_f_init:
                    instance.send(f"{name}_out_i", last)
            if name in in_s:
                while True:
                    last = instance.receive(f"{name}_in_s")
                    if name in out_i:
                        instance.send(f"{name}_out_i", last)
                    if last.next_timestamp is None:
                        break
            if name in out_f and last is not None:
                instance.send(f"{name}_out_f", last)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    main()
