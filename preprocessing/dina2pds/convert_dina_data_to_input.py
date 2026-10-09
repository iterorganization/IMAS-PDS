"""
Script to build valid inputs for the PDS couplings from DINA output data.
"""

import argparse
import logging
from contextlib import ExitStack
from urllib.parse import urlsplit

from imas import DBEntry
from preprocess_dina import write_dina_data
from preprocess_machine_description import write_machine_description_data


def handle_args():
    # make some of these optional when we get cases where they are not needed
    parser = argparse.ArgumentParser(
        description="Get preprocessed input data for NICE from DINA"
    )
    parser.add_argument(
        "--source_uri", type=str, help="URI to load DINA output data from"
    )
    parser.add_argument(
        "--summary_uri", type=str, help="URI to load DINA summary data from"
    )
    parser.add_argument(
        "--md_pf_active_uri",
        type=str,
        help="URI to load machine description data for pf_active",
    )
    parser.add_argument(
        "--md_pf_passive_uri",
        type=str,
        help="URI to load machine description data for pf_passive",
    )
    parser.add_argument(
        "--md_wall_uri", type=str, help="URI to load machine description data for wall"
    )
    parser.add_argument(
        "--md_iron_core_uri",
        type=str,
        default="empty",
        help="URI to load machine description data for iron_core, or 'empty' "
        "(default; also an empty string) for a machine without an iron core such as "
        "ITER: an empty static iron_core IDS is then created. A URI whose path ends "
        "in 'iron_core_empty' (legacy source.env files point at "
        "$TOOLS/md/iron_core_empty, no longer shipped) is treated as 'empty' too.",
    )
    parser.add_argument(
        "--sink_uri", type=str, help="URI to write the DINA-derived input data to"
    )
    parser.add_argument(
        "--md_sink_uri",
        type=str,
        default=None,
        help="URI to write the machine-description reference data to "
        "(defaults to --sink_uri, i.e. the same file as the DINA-derived data)",
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--n_timeslices",
        type=int,
        help="Number of timeslices, uniform over the viable time range",
    )
    selection.add_argument(
        "--dt_step",
        type=float,
        help="Time step [s] between selected timeslices: the first viable time, "
        "+DT, +2 DT, ... up to the last viable time, each mapped to the nearest "
        "viable raw sample",
    )
    parser.add_argument(
        "--report_window",
        type=float,
        nargs=2,
        metavar=("T_START", "T_END"),
        default=None,
        help="Only for the log: also report how many selected slices fall inside "
        "[T_START, T_END] and their spacing there",
    )
    args = parser.parse_args()
    if args.n_timeslices is not None and args.n_timeslices < 2:
        parser.error("--n_timeslices must be >= 2")
    if args.dt_step is not None and not args.dt_step > 0:
        parser.error("--dt_step must be > 0")
    if args.md_sink_uri is None:
        args.md_sink_uri = args.sink_uri
    return args


def is_empty_iron_core(uri):
    """True when --md_iron_core_uri asks for an empty iron_core IDS.

    Accepts "empty", an empty string, or -- for legacy source.env files written
    before the empty reference entry was removed from the repository -- a URI whose
    path's last component is "iron_core_empty" (e.g.
    imas:hdf5?path=$TOOLS/md/iron_core_empty). That entry never held more than
    ids_properties, so it is recreated in memory instead of being read.
    """
    if uri is None or uri.strip() in ("", "empty"):
        return True
    query = urlsplit(uri).query
    path = next(
        (v for k, _, v in (p.partition("=") for p in query.split("&")) if k == "path"),
        uri,
    )
    return path.rstrip("/").rsplit("/", 1)[-1] == "iron_core_empty"


def main():
    """
    convert to DDV4
    find interesting timeslices
    convert boundary_separatrix to boundary
    """
    args = handle_args()

    with ExitStack() as stack:
        db_in = stack.enter_context(DBEntry(args.source_uri, "r"))
        db_sum = stack.enter_context(DBEntry(args.summary_uri, "r"))
        db_md_pf_active = stack.enter_context(DBEntry(args.md_pf_active_uri, "r"))
        db_md_pf_passive = stack.enter_context(DBEntry(args.md_pf_passive_uri, "r"))
        db_md_wall = stack.enter_context(DBEntry(args.md_wall_uri, "r"))
        # None: preprocess_iron_core creates an empty static iron_core (ITER).
        db_md_iron_core = (
            None
            if is_empty_iron_core(args.md_iron_core_uri)
            else stack.enter_context(DBEntry(args.md_iron_core_uri, "r"))
        )
        db_out = stack.enter_context(DBEntry(args.sink_uri, "w"))
        db_md_out = (
            db_out
            if args.md_sink_uri == args.sink_uri
            else stack.enter_context(DBEntry(args.md_sink_uri, "w"))
        )

        write_dina_data(
            db_out,
            db_in,
            db_sum,
            db_md_pf_active,
            n_timeslices=args.n_timeslices,
            dt_step=args.dt_step,
            report_window=args.report_window,
        )
        write_machine_description_data(
            db_md_out,
            db_md_wall,
            db_md_iron_core,
            db_md_pf_passive,
            db_md_pf_active,
            write_pf_active=db_md_out is not db_out,
        )


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.WARNING,
    )
    main()
