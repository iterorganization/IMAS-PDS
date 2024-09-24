import argparse
import logging
from typing import Optional

from imas.imasdef import CLOSEST_SAMPLE
from imaspy import DBEntry
from libmuscle import Instance, Message
from ymmsl import Operator


def muscled_source() -> None:
    """Muscled data sink"""

    args = parse_args()

    print("Start source")
    instance = Instance(
        {
            Operator.F_INIT: ["ids_data_in"],
            Operator.O_F: ["ids_data_out"],
        }
    )

    if args.all_slices:
        all_slices_source(instance, args)
    else:
        sliced_source(instance, args)

    # FINALIZE THE ACTOR
    print("Source done.")


def sliced_source(instance: Instance, args: argparse.Namespace) -> None:
    dd_version = get_dd_version(instance)
    dbentry = DBEntry(args.db_entry_uri, "r", dd_version=dd_version)
    ids_data = dbentry.get(args.ids_name, args.ids_occ, autoconvert=True)
    t_arr = ids_data.time
    t_max = len(t_arr) - 1
    t_idx = 0
    while instance.reuse_instance():
        if instance.is_connected("ids_data_in"):
            msg_in = instance.receive("ids_data_in")
            t_cur = msg_in.timestamp
        else:
            t_cur = t_arr[t_idx]
            t_idx = min(t_idx + 1, t_max)
        slice_out = dbentry.get_slice(
            ids_name=args.ids_name,
            occurrence=args.ids_occ,
            time_requested=t_cur,
            interpolation_method=CLOSEST_SAMPLE,
        )
        msg_out = Message(t_cur, data=slice_out.serialize())
        logging.info("#sync# Sending ids_data_out")
        instance.send("ids_data_out", msg_out)


def all_slices_source(instance: Instance, args: argparse.Namespace) -> None:
    dd_version = get_dd_version(instance)
    dbentry = DBEntry(args.db_entry_uri, "r", dd_version=dd_version)
    ids_data = dbentry.get(args.ids_name, args.ids_occ, autoconvert=True)
    t_cur = ids_data.time[-1]
    while instance.reuse_instance():
        msg_out = Message(t_cur, data=ids_data.serialize())
        logging.info("#sync# Sending ids_data_out")
        instance.send("ids_data_out", msg_out)


def get_dd_version(instance: Instance) -> Optional[str]:
    try:
        dd_version = instance.get_setting("dd_version", "str")
    except KeyError:
        dd_version = None
    return dd_version


def parse_args() -> argparse.Namespace:
    # Initialize the argument parser
    parser = argparse.ArgumentParser(description="Process some arguments.")

    # Add arguments you want to accept from the command line
    parser.add_argument(
        "--db_entry_uri", type=str, required=True, help="URI for DB_ENTRY"
    )
    parser.add_argument(
        "--ids_name", type=str, required=True, help="Name of IDS to read from"
    )
    parser.add_argument(
        "--ids_occ",
        type=int,
        required=False,
        default=0,
        help="Occurrence number of IDS to read from",
    )
    parser.add_argument(
        "--all_slices",
        type=bool,
        required=False,
        default=False,
        help="Whether to return the full IDS or only a single slice",
    )

    # Parse the command-line arguments
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    muscled_source()
