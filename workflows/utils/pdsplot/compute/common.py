"""Helpers shared by the compute classes.

The conventions follow ``idstools.compute.common``: a missing leaf never raises,
it is replaced by an array of NaN and reported with ``logger.critical`` so that a
plot is still produced and the gap is visible both on the figure and in the log.
"""

import logging

import numpy as np

logger = logging.getLogger("module")

#: Value the Access Layer writes for an unset FLT_0D/FLT_1D.
EMPTY_DOUBLE = -9e40


def get_nearest_time(time_array, requested_time):
    """Index and value of the sample of ``time_array`` nearest ``requested_time``.

    A negative ``requested_time`` (the default of the command line tools) selects
    the middle of the time base, as ``idstools`` does.

    Args:
        time_array (np.ndarray): time base.
        requested_time (float): requested time, negative for "middle of the base".

    Returns:
        tuple: ``(time_index, time_value)``.
    """
    time_array = np.asarray(time_array, dtype=float)
    ntime = len(time_array)
    if ntime < 1:
        logger.critical("empty time base, cannot select a time slice")
        return 0, 0.0
    if requested_time is not None and requested_time >= 0:
        time_index = int(np.abs(time_array - requested_time).argmin())
    else:
        time_index = ntime // 2
    time_value = float(time_array[time_index])
    if ntime > 1:
        logger.info("Time  = %.3f s in range [%.2f, %.2f] s",
                    time_value, time_array[0], time_array[-1])
        logger.info("Index = %d", time_index)
    else:
        logger.info("Time  = %.3f s", time_value)
    return time_index, time_value


def clean(values):
    """Return ``values`` as a float numpy array with EMPTY_DOUBLE turned into NaN."""
    array = np.array(values, dtype=float, copy=True)
    array[array <= EMPTY_DOUBLE / 2.0] = np.nan
    return array


def nan_array(ntime):
    """An array of ``ntime`` NaN."""
    return np.full(int(ntime), np.nan, dtype=float)


def node_at(root, path):
    """Follow a dotted ``path`` from ``root``, or None when a step does not exist."""
    node = root
    for part in path.split("."):
        try:
            node = getattr(node, part)
        except AttributeError:
            return None
    return node


def get_1d(root, path, ntime, missing=None, label=None, critical=True):
    """A 1-D float array read at ``path``, NaN-filled and reported when absent.

    Args:
        root: IDS node to start from.
        path (str): dotted path relative to ``root``.
        ntime (int): length of the NaN array returned when the leaf is empty.
        missing (list, optional): list the reported label is appended to.
        label (str, optional): name used in the log and in ``missing``;
            defaults to ``path``.
        critical (bool): whether an absent leaf is worth reporting. False for a
            quantity whose absence is a legitimate state of the scenario rather
            than a data problem (a heating system that is not activated, say):
            it is then only logged at debug level and never listed as missing.

    Returns:
        np.ndarray: the values, or ``ntime`` NaN.
    """
    label = label or path
    node = node_at(root, path)
    values = None
    if node is not None:
        try:
            values = np.asarray(node)
        except Exception:                                   # pragma: no cover
            values = None
    if values is None or values.size < 1:
        if critical:
            logger.critical("%s could not be read", label)
            if missing is not None:
                missing.append(label)
        else:
            logger.debug("%s is empty", label)
        return nan_array(ntime)
    return clean(values)


def get_reference(root, path, ntime, missing=None, label=None, critical=True):
    """Same as :func:`get_1d` for a ``<path>.reference`` waveform of pulse_schedule."""
    return get_1d(root, path + ".reference", ntime, missing=missing,
                  label=label or (path + ".reference"), critical=critical)


def get_0d_over_time(nodes, path, missing=None, label=None, critical=True):
    """A time trace built from a scalar read at ``path`` in every element of ``nodes``.

    Used for the array-of-structure-over-time IDSs (``equilibrium.time_slice``,
    ``core_sources.source[:].global_quantities``).
    """
    label = label or path
    values = []
    for element in nodes:
        leaf = node_at(element, path)
        values.append(np.nan if leaf is None else float(leaf))
    array = clean(values) if values else np.array([], dtype=float)
    if array.size < 1 or np.all(np.isnan(array)):
        if critical:
            logger.critical("%s could not be read", label)
            if missing is not None:
                missing.append(label)
        else:
            logger.debug("%s is empty", label)
    return array


def stack_ragged(rows):
    """Stack 1-D arrays of different lengths into one ``(max_length, n_rows)`` array.

    Shorter rows are padded with NaN, so the result can be indexed by time column
    whatever the source of the outlines.
    """
    rows = [np.asarray(row, dtype=float) for row in rows]
    if not rows:
        return np.zeros((0, 0), dtype=float)
    width = max(row.size for row in rows)
    out = np.full((width, len(rows)), np.nan, dtype=float)
    for column, row in enumerate(rows):
        out[: row.size, column] = row
    return out


def short_coil_name(name):
    """``Central Solenoid 3U (CS3U)`` -> ``CS3U``; anything else is returned as is."""
    name = str(name or "")
    if "(" in name and name.rstrip().endswith(")"):
        return name[name.rindex("(") + 1: name.rindex(")")]
    return name


def coil_group(name):
    """``CS``, ``PF`` or ``other`` for a coil name."""
    upper = short_coil_name(name).upper() or str(name).upper()
    if "CS" in upper:
        return "CS"
    if "PF" in upper:
        return "PF"
    return "other"


def has_data(array):
    """True when ``array`` holds at least one finite value."""
    array = np.asarray(array, dtype=float)
    return array.size > 0 and bool(np.any(np.isfinite(array)))
