"""
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

import imas
from imas.imasdef import CLOSEST_SAMPLE
from imaspy import DBEntry
from libmuscle import Instance, Message
from ymmsl import SettingValue, Operator

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
    # TODO: handle sanity checks for timestamps
    # TODO: enable having S input but no O_I output

    print("Start source")
    instance = Instance()
    sliced_source(instance)
    print("Source done.")


def sliced_source(instance: Instance) -> None:
    first_run = True
    sink_db_entry = None
    source_db_entry = None
    t_idx = 0
    while instance.reuse_instance():
        if first_run:
            dd_version = get_setting_optional(instance, "dd_version")
            sink_uri = get_setting_optional(instance, "sink_uri")
            source_uri = get_setting_optional(instance, "source_uri")
            sanity_check_ports(instance)

            if sink_uri is not None:
                sink_db_entry = DBEntry(sink_uri, "w", dd_version=dd_version)
            if source_uri is not None:
                source_db_entry = DBEntry(source_uri, "r", dd_version=dd_version)
                # get outer loop t_array for the case that t_cur cannot be obtained from incoming message
                only_out_outer = len(instance.list_ports()[Operator.O_F]) > 0 and len(instance.list_ports()[Operator.F_INIT]) == 0
                # (for now) always get inner loop t_array from output data
                only_out_inner = len(instance.list_ports()[Operator.O_I]) > 0
                if sink_uri is None or only_out_outer:
                    ids_name = instance.list_ports()[Operator.O_F][0].replace(
                        "_out", ""
                    )
                    t_array_outer: List[float] = source_db_entry.get(ids_name).time
                if only_out_inner:
                    ids_name = instance.list_ports()[Operator.O_I][0].replace(
                        "_out", ""
                    )
                    t_array_inner: List[float] = source_db_entry.get(ids_name).time
            first_run = False

        # F_INIT
        t_cur = handle_sink(
            instance, sink_db_entry, instance.list_ports()[Operator.F_INIT]
        )
        if t_cur is None:
            t_cur = t_array_outer[t_idx]
        for t_inner in t_array_inner:
            # S
            handle_sink(instance, source_db_entry, instance.list_ports()[Operator.S])
            # O_I
            handle_source(
                instance, source_db_entry, instance.list_ports()[Operator.O_I], t_inner
            )
        t_idx += 1
        # O_F
        handle_source(
            instance, source_db_entry, instance.list_ports()[Operator.O_F], t_cur
        )

    for db_entry in [source_db_entry, sink_db_entry]:
        if db_entry is not None:
            db_entry.close()


def handle_source(
    instance: Instance,
    db_entry: Optional[DBEntry],
    port_list: List[str],
    t_cur: float,
) -> None:
    if db_entry is None:
        return

    for port_name in port_list:
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


def sanity_check_ports(instance: Instance) -> None:
    # check port name
    for operator, ports in instance.list_ports().items():
        for port_name in ports:
            if not (
                (port_name.endswith("_in") and operator.name not in ["F_INIT", "S"])
                or (port_name.endswith("_out") and operator.name in ["O_I", "O_F"])
            ):
                raise Warning("your port name sucks and you should feel bad")
    # check whether uri is provided if component acts as source
    no_source_uri = get_setting_optional(instance, "source_uri") is None
    no_source_ports = (
        len(instance.list_ports()[Operator.O_I] + instance.list_ports()[Operator.O_F])
        == 0
    )
    if no_source_uri != no_source_ports:
        raise Warning("needs uri to act as source")


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    muscled_sink_source()
