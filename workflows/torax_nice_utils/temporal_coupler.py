"""
MUSCLE3 actor performing IDS timeslice accumulation.

This actor can receive timeslices for various IDSs at the same time on the S
port, keeping track of whether or not it was the last timeslice for a given
inner loop. Optionally the 't_next' S port is used to override this behavior
and match with the last timeslice of a specific actor. It then sends out all
the IDSs with all accumulated timeslices on the O_F port.

If no actors are available that pass information for the next_timestep, it
will default to None and this actor will only be able to receive the first
timeslice.

This actor might have difficulty handling other actors with dynamic timesteps
that cannot accurately predict whether their current timeslice will be the
last, possibly leading to deadlocks. It is advised to use predictable or
constant timestepping.
"""

import logging
from typing import Any

from libmuscle import Instance, InstanceFlags, Message
from ymmsl import Operator

logger = logging.getLogger()


def get_port_list(instance: Instance, operator: Operator) -> list[str]:
    """Filter list of ids_names by which ones are actually connected for
    given instance"""
    total_port_list = instance.list_ports().get(operator, [])
    return [port for port in total_port_list if instance.is_connected(port)]


# IDS types the coupler can carry on a role (`a_in`/`a_out`/`b_in`/`b_out`),
# each as a `<role>_<channel>` port (e.g. `a_in_equilibrium`,
# `a_in_core_profiles`) -- every port follows this scheme, there is no
# unsuffixed/bare port. MUSCLE3 requires all ports to be declared upfront,
# so this is the finite universe a given workflow can pick any subset of
# via its conduits -- wiring a channel that isn't in this list still needs
# a one-line addition here, but everything else (labels, matching between
# peers, timing) is fully generic to whatever combination is connected.
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


def role_ports(role: str) -> list[str]:
    """All statically declared port names for one peer role, e.g. 'a_in'."""
    return [f"{role}_{channel}" for channel in CHANNELS]


def channel_ports(instance: Instance, operator: Operator, role: str) -> dict[str, str]:
    """Channel label -> port name, for whichever `<role>_<channel>` ports
    of this role are actually connected in the workflow. The first one
    encountered (in `CHANNELS` order) drives the peer's timing.
    """
    channels: dict[str, str] = {}
    for port in get_port_list(instance, operator):
        if port.startswith(role + "_"):
            channels[port[len(role) + 1 :]] = port
    return channels


class DataCache:
    """Stores data from received messages and interpolates as needed.

    This keeps the data and timestamps from the last two messages
    received from a peer, and interpolates between them to produce data
    for intermediate time points.
    """

    def __init__(self) -> None:
        """Create a DataCache.

        The cache starts out empty.
        """
        self.t_cur: float | None = None
        self.data_cur: Any | None = None
        self.t_next: float | None = None
        self.data_next: Any | None = None

    def add_data(self, t: float, data: Any) -> None:
        """Add new data to the cache.

        If the cache is currently empty, both the current and the next
        data item are set to the new data, at which point we can
        interpolate only for that exact point. As the next message
        arrives, the new data item is saved as the 'next' value, and
        the previous 'next' value becomes the 'cur' value.
        """
        if self.t_cur is None:
            self.t_cur = t
            self.data_cur = data

            self.t_next = t
            self.data_next = data
        else:
            self.t_cur = self.t_next
            self.data_cur = self.data_next

            self.t_next = t
            self.data_next = data

    def get_data(self, t: float) -> tuple[float, Any]:
        """Return a data value for a given time point.

        This function interpolates the stored data to produce an
        intermediate value. In this example, we simply assume that
        each data item is valid until it is replaced by the next item.
        Hence, no calculation is needed, we just return the current
        value. A more advanced, model-specific coupler would interpolate
        here.

        This value is returned with its corresponding time point here,
        because it makes it easier to see what happens in the log file.
        If `t` is returned instead, as should be done when there's an
        actual interpolation, then to the two submodels being connected
        it looks exactly as if they are running in lockstep.

        If one of the models runs for longer than the other model, then
        the shorter-running model will stop producing new data while
        the longer-running model still needs inputs. In this case, `t`
        can be beyond `self.t_next`, and we need to extrapolate. Here
        we do that by returning the `next` data rather than the `cur`
        data. This also covers the corner case of both models hitting
        the exact same timepoint.
        """
        # By the time get_data() is called, add_data() has always populated the
        # cache (directly, or via Peer restoring it from checkpoint state).
        assert self.t_cur is not None and self.t_next is not None
        if self.t_next <= t:
            return self.t_next, self.data_next
        else:
            return self.t_cur, self.data_cur


class Peer:
    """Tracks state for a peer.

    This is a helper class which for one of the peers keeps track of
    the most recent messages it has sent, at which point in simulated
    time the most recent message was received, when the next message
    needs to be sent, and what the next timepoint of the model is.

    This information can then be used to determine whether the model is
    still running, whether we can receive from it or whether we need to
    send a message to it first. For the latter, it also checks whether
    the necessary data is available.

    Finally, this class does the actual communication with the peer,
    via the instance object.

    A peer can carry more than one data channel (e.g. an equilibrium
    plus a core_profiles IDS from the same submodel, sent together each
    timestep). `in_ports`/`out_ports` map a channel label (e.g.
    'equilibrium', 'core_profiles') to the MUSCLE3 port name for that
    channel. All channels on a peer are assumed to be sent/received
    together by the submodel; the first channel in `in_ports` drives
    the timing (rcvd/to_send/next), the rest are just cached and
    forwarded on the same cadence.
    """

    def __init__(
        self,
        instance: Instance,
        in_ports: dict[str, str],
        out_ports: dict[str, str],
        resume_from_state: Any = None,
    ) -> None:
        """Create a Peer object.

        This also receives an initial message from the peer model, and
        uses the received data to initialise the cache and the state.

        Args:
            instance: The instance to use for communication
            in_ports: Channel label -> port to receive on for this peer.
                The first entry drives this peer's timing.
            out_ports: Channel label -> port to send on for this peer
        """
        self.instance = instance
        self.in_ports = in_ports
        self.out_ports = out_ports
        self.caches: dict[str, DataCache] = {label: DataCache() for label in in_ports}
        self.primary_label = next(iter(in_ports))

        if resume_from_state:
            for label, cache_state in resume_from_state["caches"].items():
                self.caches[label].t_cur = cache_state["t_cur"]
                self.caches[label].data_cur = cache_state["data_cur"]
                self.caches[label].t_next = cache_state["t_next"]
                self.caches[label].data_next = cache_state["data_next"]
            self.rcvd = resume_from_state["rcvd"]
            self.to_send = resume_from_state["to_send"]
            self.next = resume_from_state["next"]
        else:
            for label, port in self.in_ports.items():
                msg = self.instance.receive(port)
                self.caches[label].add_data(msg.timestamp, msg.data)
                if label == self.primary_label:
                    self.rcvd = msg.timestamp
                    self.to_send = msg.timestamp
                    self.next = msg.next_timestamp

    def done(self) -> bool:
        """Return whether we are done commmunicating with this peer."""
        return self.to_send is None

    def can_receive(self) -> bool:
        """Return whether we can receive a message from this peer."""
        return (
            self.next is not None
            and self.to_send is not None
            and self.next <= self.to_send
        )

    def receive(self) -> None:
        """Receive a message from this peer on all its channels, and
        update the caches."""
        for label, port in self.in_ports.items():
            msg = self.instance.receive(port)
            self.caches[label].add_data(msg.timestamp, msg.data)
            if label == self.primary_label:
                self.rcvd = msg.timestamp
                self.next = msg.next_timestamp

    def can_send(self, peer_rcvd: float, peer_next: float | None) -> bool:
        """Return whether we can send to this peer.

        This determines whether our next interaction with the peer
        should be sending a message to it, which depends on whether
        the peer will try to receive again, and on whether we have
        data available to send to it.

        The latter depends on whether we have received the data from
        the other peer that we need to create a message for the time
        point at which this peer expects to receive. That information
        is passed into this function.

        Args:
            peer_recvd: When we last received from the other peer.
            peer_next: If and when the other peer will send again.
        """
        if self.to_send is None:
            return False
        return self.to_send <= peer_rcvd or peer_next is None

    def send(self, peer: "Peer") -> None:
        """Send the next message(s) to this peer.

        For every channel this peer sends out, the corresponding
        channel is drained from `peer`'s cache (interpolated to this
        peer's next send point) and sent out. Marks this send as done.

        Args:
            peer: The other peer, whose caches hold the data to send.
        """
        assert self.to_send is not None
        for label, port in self.out_ports.items():
            t, data = peer.caches[label].get_data(self.to_send)
            self.instance.send(port, Message(t, self.next, data))
        self.to_send = self.next

    def get_state(self) -> dict[str, Any]:
        """Return the current state of this object as a MUSCLE-serializable dict"""
        return {
            "caches": {
                label: {
                    "t_cur": cache.t_cur,
                    "data_cur": cache.data_cur,
                    "t_next": cache.t_next,
                    "data_next": cache.data_next,
                }
                for label, cache in self.caches.items()
            },
            "rcvd": self.rcvd,
            "to_send": self.to_send,
            "next": self.next,
        }


def main() -> None:
    """Model component connecting two scale-overlapping submodels.

    This component sits in between two scale-overlapping submodels
    running at different (and potentially variable) timesteps and
    ensures that each of these peers receives a message whenever it
    expects one, and can send a message whenever it expects to do so.

    This function extends :func:`temporal_coupler` with checkpointing
    capabilities.
    """
    instance = Instance(
        {
            Operator.O_I: role_ports("a_out") + role_ports("b_out"),
            Operator.S: role_ports("a_in") + role_ports("b_in"),
        },
        InstanceFlags.USES_CHECKPOINT_API | InstanceFlags.SKIP_MMSF_SEQUENCE_CHECKS,
    )

    while instance.reuse_instance():
        a_in_ports = channel_ports(instance, Operator.S, "a_in")
        a_out_ports = channel_ports(instance, Operator.O_I, "a_out")
        b_in_ports = channel_ports(instance, Operator.S, "b_in")
        b_out_ports = channel_ports(instance, Operator.O_I, "b_out")

        # if instance.resuming():
        #     state = instance.load_snapshot().data
        #     if state is not None:
        #         a = Peer(instance, a_in_ports, a_out_ports, state['a'])
        #         b = Peer(instance, b_in_ports, b_out_ports, state['b'])
        # if instance.should_init():
        #     # Receive initial messages and initialise state
        #     a = Peer(instance, a_in_ports, a_out_ports)
        #     b = Peer(instance, b_in_ports, b_out_ports)
        a = Peer(instance, a_in_ports, a_out_ports)
        b = Peer(instance, b_in_ports, b_out_ports)

        # Send and receive as needed
        while not a.done() or not b.done():
            if a.can_receive():
                print("receive a", a.rcvd, a.to_send, a.next, b.rcvd, b.to_send, b.next)
                a.receive()
            elif b.can_receive():
                print("receive b", a.rcvd, a.to_send, a.next, b.rcvd, b.to_send, b.next)
                b.receive()
            elif a.can_send(b.rcvd, b.next):
                print("send a", a.rcvd, a.to_send, a.next, b.rcvd, b.to_send, b.next)
                a.send(b)
            elif b.can_send(a.rcvd, a.next):
                print("send b", a.rcvd, a.to_send, a.next, b.rcvd, b.to_send, b.next)
                b.send(a)

            # t_cur = min(a.rcvd, b.rcvd)
            # if instance.should_save_snapshot(t_cur):
            #     instance.save_snapshot(Message(
            #             t_cur, data={'a': a.get_state(), 'b': b.get_state()}))

        # t_cur = min(a.rcvd, b.rcvd)
        # if instance.should_save_final_snapshot():
        #     instance.save_final_snapshot(Message(t_cur))


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    main()
