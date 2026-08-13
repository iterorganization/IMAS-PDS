"""
Script to build valid inputs for the PDS couplings from DINA output data.
"""

import argparse
import logging
import time
from contextlib import ExitStack

from imas import DBEntry
from preprocess_dina import write_dina_data
from preprocess_machine_description import write_machine_description_data

logger = logging.getLogger(__name__)

DBENTRY_OPEN_ATTEMPTS = 5
DBENTRY_OPEN_RETRY_DELAY_S = 2


def open_dbentry_with_retry(uri, mode):
    """Open a DBEntry, retrying on transient backend errors (e.g. flaky NFS opens)."""
    for attempt in range(1, DBENTRY_OPEN_ATTEMPTS + 1):
        try:
            return DBEntry(uri, mode)
        except Exception:
            if attempt == DBENTRY_OPEN_ATTEMPTS:
                raise
            delay = DBENTRY_OPEN_RETRY_DELAY_S * attempt
            logger.warning(
                "Failed to open DBEntry %s (attempt %d/%d), retrying in %ds",
                uri,
                attempt,
                DBENTRY_OPEN_ATTEMPTS,
                delay,
                exc_info=True,
            )
            time.sleep(delay)


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
        help="URI to load machine description data for iron_core",
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
    parser.add_argument(
        "--n_timeslices", type=int, default=51, help="Number of timeslices"
    )
    args = parser.parse_args()
    if args.md_sink_uri is None:
        args.md_sink_uri = args.sink_uri
    return args


def main():
    """
    convert to DDV4
    find interesting timeslices
    convert boundary_separatrix to boundary
    """
    args = handle_args()

    with ExitStack() as stack:
        db_in = stack.enter_context(open_dbentry_with_retry(args.source_uri, "r"))
        db_sum = stack.enter_context(open_dbentry_with_retry(args.summary_uri, "r"))
        db_md_pf_active = stack.enter_context(
            open_dbentry_with_retry(args.md_pf_active_uri, "r")
        )
        db_md_pf_passive = stack.enter_context(
            open_dbentry_with_retry(args.md_pf_passive_uri, "r")
        )
        db_md_wall = stack.enter_context(open_dbentry_with_retry(args.md_wall_uri, "r"))
        db_md_iron_core = stack.enter_context(
            open_dbentry_with_retry(args.md_iron_core_uri, "r")
        )
        db_out = stack.enter_context(DBEntry(args.sink_uri, "w"))
        db_md_out = (
            db_out
            if args.md_sink_uri == args.sink_uri
            else stack.enter_context(DBEntry(args.md_sink_uri, "w"))
        )

        write_dina_data(db_out, db_in, db_sum, db_md_pf_active, args.n_timeslices)
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
