"""
Muscled data sink and/or source actor.
Assumes that the port names for the conduits going out and in have
the format "*ids_name*_in" and "*ids_name*_out", will fail otherwise.
Set sink_uri and/or source_uri in the settings to determine which DBEntry
is used as data sink and/or source.
You can set the occurrence number per port with the optional setting
"*ids_name*_out_occ"

How to use in ymmsl file:
model:
  name: test_model
  components:
    macro:
      implementation: sink_source
      ports:
      o_i: [core_profiles_out]
    micro:
      implementation: sink_source
      ports:
      f_init: [core_profiles_in]
  conduits:
    macro.core_profiles_out: micro.core_profiles_in
settings:
  macro.source_uri: source_uri
  micro.sink_uri: sink_uri
implementations:
  sink_source:
    executable: python
    args: -u -m pds.utils.data_sink_source

"""

import logging
from typing import Dict, List, Optional

from imas.imasdef import CLOSEST_SAMPLE
from imaspy import DBEntry, IDSFactory
from libmuscle import Instance, Message
from ymmsl import Operator, SettingValue

PORT_LIST = Dict[str, List[str]]

# TODO: enable specifying time range
# TODO: setting for full ids instead of separate time_slices
# TODO: handle sanity checks for timestamps
# TODO: make fully flexible single component


def muscled_sink() -> None:
    instance = Instance(
        {
            Operator.F_INIT: [
                f"{ids_name}_in" for ids_name in IDSFactory().ids_names()
            ],
        }
    )
    first_run = True
    while instance.reuse_instance():
        if first_run:
            dd_version = get_setting_optional(instance, "dd_version")
            sink_uri = get_setting_optional(instance, "sink_uri")
            sink_db_entry = DBEntry(sink_uri, "w", dd_version=dd_version)
            port_list_in = get_port_list(instance, Operator.F_INIT)
            sanity_check_ports(instance)
            first_run = False

        # F_INIT
        handle_sink(instance, sink_db_entry, port_list_in)
    sink_db_entry.close()


def muscled_source() -> None:
    instance = Instance(
        {
            Operator.O_I: [f"{ids_name}_out" for ids_name in IDSFactory().ids_names()],
        }
    )
    first_run = True
    while instance.reuse_instance():
        if first_run:
            dd_version = get_setting_optional(instance, "dd_version")
            source_uri = get_setting_optional(instance, "source_uri")
            source_db_entry = DBEntry(source_uri, "r", dd_version=dd_version)
            port_list_out = get_port_list(instance, Operator.O_I)
            t_array: List[float] = source_db_entry.get(
                port_list_out[0].replace("_out", "")
            ).time
            sanity_check_ports(instance)
            first_run = False

        for t_inner in t_array:
            # O_I
            handle_source(instance, source_db_entry, port_list_out, t_inner)
    source_db_entry.close()


def muscled_sink_source() -> None:
    instance = Instance(
        {
            Operator.F_INIT: [
                f"{ids_name}_in" for ids_name in IDSFactory().ids_names()
            ],
            Operator.O_F: [f"{ids_name}_out" for ids_name in IDSFactory().ids_names()],
        }
    )
    first_run = True
    while instance.reuse_instance():
        if first_run:
            dd_version = get_setting_optional(instance, "dd_version")
            sink_uri = get_setting_optional(instance, "sink_uri")
            source_uri = get_setting_optional(instance, "source_uri")
            sink_db_entry = DBEntry(sink_uri, "w", dd_version=dd_version)
            source_db_entry = DBEntry(source_uri, "r", dd_version=dd_version)
            port_list_in = get_port_list(instance, Operator.F_INIT)
            port_list_out = get_port_list(instance, Operator.O_F)
            sanity_check_ports(instance)
            first_run = False

        # F_INIT
        t_cur = handle_sink(instance, sink_db_entry, port_list_in) or 0
        # O_F
        handle_source(instance, source_db_entry, port_list_out, t_cur)

    sink_db_entry.close()
    source_db_entry.close()


def get_port_list(instance: Instance, operator: Operator) -> List[str]:
    total_port_list = instance.list_ports().get(operator, [])
    port_list = [port for port in total_port_list if instance.is_connected(port)]
    return port_list


def handle_source(
    instance: Instance,
    db_entry: Optional[DBEntry],
    port_list: List[str],
    t_cur: float,
) -> None:
    if db_entry is None:
        return

    for port_name in port_list:
        ids_name = port_name.replace("_out", "")
        occ = get_setting_optional(instance, f"{port_name}_occ", default=0)
        slice_out = db_entry.get_slice(
            ids_name=ids_name,
            occurrence=occ,
            time_requested=t_cur,
            interpolation_method=CLOSEST_SAMPLE,
        )
        msg_out = Message(t_cur, data=slice_out.serialize())
        logging.info(f"#sync# Sending {port_name}")
        instance.send(port_name, msg_out)


def handle_sink(
    instance: Instance,
    db_entry: Optional[DBEntry],
    port_list: List[str],
) -> Optional[float]:
    t_cur = None
    for port_name in port_list:
        ids_name = port_name.replace("_in", "")
        occ = get_setting_optional(instance, f"{port_name}_occ", default=0)
        logging.info(f"#sync# Receiving {port_name}")
        msg_in = instance.receive(port_name)
        t_cur = msg_in.timestamp
        if db_entry is not None:
            # ids_data = getattr(imas, ids_name)()
            ids_data = getattr(IDSFactory(), ids_name)()
            ids_data.deserialize(msg_in.data)
            db_entry.put_slice(ids_data, occurrence=occ)
    return t_cur


def get_setting_optional(
    instance: Instance, setting_name: str, default: Optional[SettingValue] = None
) -> Optional[SettingValue]:
    setting: Optional[SettingValue]
    try:
        setting = instance.get_setting(setting_name)
    except KeyError:
        setting = default
    return setting


def sanity_check_ports(instance: Instance) -> None:
    # check port name
    for operator, ports in instance.list_ports().items():
        for port_name in ports:
            if not (
                (port_name.endswith("_in") and operator.name in ["F_INIT", "S"])
                or (port_name.endswith("_out") and operator.name in ["O_I", "O_F"])
            ):
                raise Warning("your port name sucks and you should feel bad")
    # check whether uri is provided if component acts as source
    no_source_uri = get_setting_optional(instance, "source_uri") is None
    no_source_ports = (
        len(
            instance.list_ports().get(Operator.O_I, [])
            + instance.list_ports().get(Operator.O_F, [])
        )
        == 0
    )
    if no_source_uri != no_source_ports:
        raise Warning("needs uri to act as source")
    # check no duplicate ports in F_INIT/S or O_I/O_F
    overlap_out = len(
        set(instance.list_ports().get(Operator.O_I, []))
        & set(instance.list_ports().get(Operator.O_F, []))
    )
    overlap_in = len(
        set(instance.list_ports().get(Operator.F_INIT, []))
        & set(instance.list_ports().get(Operator.S, []))
    )
    if overlap_in or overlap_out:
        raise Warning("cannot use the same port name for different ports")


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    muscled_sink_source()
