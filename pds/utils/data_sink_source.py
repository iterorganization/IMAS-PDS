import logging
from typing import Dict, List, Optional

import imas
from imas.imasdef import CLOSEST_SAMPLE
from imaspy import DBEntry
from libmuscle import Instance, Message
from ymmsl import SettingValue

PORT_LIST = Dict[str, List[str]]


def muscled_sink_source() -> None:
    """
    Muscled data sink and/or source actor.
    Assumes that the port names for the conduits going out and in have
    the format "*ids_name*_in" and "*ids_name*_out", will fail otherwise.
    Set sink_uri and/or source_uri in the settings to determine which DBEntry
    is used as data sink and/or source.
    You can set the occurrence number per port with the optional setting
    "*ids_name*_out_occ"
    """

    # TODO: enable specifying time range
    # TODO: setting for full ids instead of separate time_slices

    print("Start source")
    instance = Instance()
    sliced_source(instance)
    print("Source done.")


def sliced_source(instance: Instance) -> None:
    first_run = True
    t_idx = 0
    while instance.reuse_instance():
        if first_run:
            dd_version = get_setting_optional(instance, "dd_version")
            sink_uri = get_setting_optional(instance, "sink_uri")
            source_uri = get_setting_optional(instance, "source_uri")
            listed_ports = build_port_list(instance)

            if (source_uri is None) != len(listed_ports["O_F"]) == 0:
                raise Warning("needs uri to act as source")

            if sink_uri is not None:
                sink_db_entry = DBEntry(sink_uri, "w", dd_version=dd_version)
            if source_uri is not None:
                source_db_entry = DBEntry(source_uri, "r", dd_version=dd_version)
                if sink_uri is None:
                    ids_name = listed_ports["O_F"][0].replace("_out", "")
                    t_array: List[float] = source_db_entry.get(ids_name).time
            first_run = False

        t_cur = handle_sink(instance, sink_db_entry, listed_ports)
        if t_cur is None:
            t_cur = t_array[t_idx]
        handle_source(instance, sink_db_entry, listed_ports, t_cur)
        t_idx += 1


def handle_source(
    instance: Instance,
    db_entry: Optional[DBEntry],
    listed_ports: PORT_LIST,
    t_cur: float,
) -> None:
    for port_name in listed_ports["O_F"]:
        occ = get_setting_optional(instance, f"{port_name}_occ", default=0)
        slice_out = db_entry.get_slice(
            ids_name=port_name,
            occurrence=occ,
            time_requested=t_cur,
            interpolation_method=CLOSEST_SAMPLE,
        )
        msg_out = Message(t_cur, data=slice_out.serialize())
        logging.info(f"#sync# Sending {port_name}")
        instance.send(port_name, msg_out)


def handle_sink(
    instance: Instance, db_entry: Optional[DBEntry], listed_ports: PORT_LIST
) -> Optional[float]:
    t_cur = None
    for port_name in listed_ports["F_INIT"]:
        ids_name = port_name.replace("_in", "")
        occ = get_setting_optional(instance, f"{port_name}_occ", default=0)
        logging.info(f"#sync# Receiving {port_name}")
        msg_in = instance.receive(port_name)
        t_cur = msg_in.timestamp
        if db_entry is not None:
            ids_data = imas.get(ids_name)()
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


def build_port_list(instance: Instance) -> PORT_LIST:
    listed_ports: PORT_LIST = {"O_F": [], "F_INIT": []}
    for _, ports in instance.list_ports().items():
        for port_name in ports:
            if port_name.endswith("_out"):
                listed_ports["O_F"].append(port_name)
            elif port_name.endswith("_in"):
                listed_ports["F_INIT"].append(port_name)
            else:
                raise Warning("your port name sucks and you should feel bad")
    return listed_ports


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    muscled_sink_source()
