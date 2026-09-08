#!/usr/bin/env python3
"""Display the pulse schedule of a PDS run, with its input waveforms overlaid.

The tool is the ``pulse_schedule`` counterpart of the IDStools ``plotscenario``
script: one figure of twelve panels showing the reference (demand) waveforms a PDS
run exported -- flux control, toroidal field, plasma boundary, poloidal field coil
currents and voltages, position and shape, X point, density control and heating --
together with a text panel carrying the provenance of the entry.

Entries given with ``-r/--reference`` are drawn dashed on the same panels.  When
such an entry has a ``pulse_schedule`` IDS it is read directly, otherwise the same
quantities are derived from its ``equilibrium``, ``pf_active``, ``core_sources``
and ``core_profiles`` IDSs; that is what lets the DINA-derived scenario input of a
PDS case, which has no pulse schedule, be compared with what the run produced.

Usage::

    plotpulseschedule -u URI [-r URI ...] [-t TIME] [--save] [--directory DIR]
                      [--rc KEY=VAL] [--dpi N] [-v]
"""

import argparse
import datetime
import getpass
import logging
import os
import socket
import sys
import textwrap

import numpy as np

from ..compute.common import get_nearest_time, has_data
from ..compute.pulse_schedule import PulseScheduleCompute, WaveformsFromIdsCompute
# ..view.common and ..view.pulse_schedule import matplotlib.pyplot at module
# level: deferred to main(), after select_backend() has chosen the backend.

logger = logging.getLogger("module")

TOOL = "plotpulseschedule"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def setup_logger(name="module", level=logging.INFO):
    """A stdout logger, mirroring what the IDStools scripts set up."""
    log = logging.getLogger(name)
    log.setLevel(level)
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
        log.addHandler(handler)
    return log


#: MPLBACKEND names that cannot open a window; anything else is treated as
#: interactive and honoured as-is (compared case-insensitively)
NON_INTERACTIVE_BACKENDS = {"agg", "cairo", "pdf", "pgf", "ps", "svg", "template"}


def select_backend(save):
    """Choose the matplotlib backend once, before pyplot is imported anywhere.

    ``--save`` forces ``Agg``.

    Otherwise, when ``MPLBACKEND`` is set in the environment to an
    *interactive* backend (anything other than ``agg``, ``cairo``, ``pdf``,
    ``pgf``, ``ps``, ``svg`` or ``template``, see ``NON_INTERACTIVE_BACKENDS``)
    it is used as before.

    A *non-interactive* ``MPLBACKEND`` is not honoured for an interactive run,
    though: some module or shell profile exports ``MPLBACKEND=Agg`` so batch
    jobs never try to pop up a window, but that would silently make an
    interactive (no ``--save``) invocation show nothing. So in that case --
    and when ``MPLBACKEND`` is unset altogether -- ``TkAgg``, ``Qt5Agg`` and
    ``QtAgg`` are tried in turn, but only when a display is available
    (``DISPLAY`` set, or on Windows); the log line says the non-interactive
    ``MPLBACKEND`` was overridden when that is what happened. ``Agg`` is the
    last resort, logged clearly since nothing will then be shown.

    ``force=True`` is passed to ``matplotlib.use()`` (matplotlib >= 3.1)
    because ``MPLBACKEND`` may already have been read by the time this runs,
    and a plain ``use()`` can silently no-op once a backend is considered
    fixed; ``pyplot`` must still not be imported anywhere before this
    returns, or the switch would be rejected outright.
    """
    import matplotlib

    if save:
        matplotlib.use("Agg", force=True)
        logger.info("matplotlib backend: Agg (--save)")
        return

    env_backend = os.environ.get("MPLBACKEND")
    if env_backend and env_backend.strip().lower() not in NON_INTERACTIVE_BACKENDS:
        logger.info("matplotlib backend: %s (MPLBACKEND)", env_backend)
        return

    has_display = bool(os.environ.get("DISPLAY")) or sys.platform.startswith("win")
    if has_display:
        for name in ("TkAgg", "Qt5Agg", "QtAgg"):
            try:
                matplotlib.use(name, force=True)
                if env_backend:
                    logger.info(
                        "matplotlib backend: %s (interactive; MPLBACKEND=%s "
                        "from the environment overridden because no --save "
                        "was given)", name, env_backend)
                else:
                    logger.info("matplotlib backend: %s", name)
                return
            except Exception as exc:
                logger.debug("backend %s not available: %s", name, exc)

    matplotlib.use("Agg", force=True)
    if env_backend:
        logger.info(
            "no interactive matplotlib backend available (DISPLAY unset, or "
            "Tk/Qt not importable; MPLBACKEND=%s in the environment): "
            "nothing will be shown, use --save --directory DIR", env_backend)
    else:
        logger.info(
            "no interactive matplotlib backend available (DISPLAY unset, or "
            "Tk/Qt not importable): nothing will be shown, use --save "
            "--directory DIR")


def uri_path(uri):
    """The ``path=`` of an IMAS URI, or the URI itself when it is a plain path."""
    if "path=" in uri:
        return uri.split("path=", 1)[1].split("?")[0].split("#")[0]
    return uri if not uri.startswith("imas:") else ""


def entry_label(uri):
    """Short name of an entry: the basename of its path, else the URI."""
    path = uri_path(uri)
    return os.path.basename(path.rstrip("/")) if path else uri


def sanitised(uri):
    """The URI turned into a file name fragment, as ``idstools`` does."""
    path = uri_path(uri)
    if path:
        return "PATH_" + path.strip("/").replace("/", "_")
    return "URI_" + "".join(c if c.isalnum() else "_" for c in uri)


def figure_name(uri, time_value):
    """``plotpulseschedule_<sanitised uri>_TIME_<t>.png``."""
    return "%s_%s_TIME_%.3f.png" % (TOOL, sanitised(uri), time_value)


def figure_title(uri, time_value=None):
    """The sup title, built the way ``idstools.utils.clihelper.get_title`` is.

    ``plotscenario`` writes "Scenario PATH=<path> TIME:<t>", so this writes
    "Pulse schedule PATH=<path> TIME:<t>", with the path of the entry in full:
    it is the one place the figure says exactly which entry it shows, and a
    shortened path cannot be pasted back into a command.
    """
    path = uri_path(uri)
    title = "Pulse schedule "
    title += "PATH=%s" % path if path else "%s" % uri
    if time_value is not None:
        title += " TIME:%.3f" % time_value
    return title


def provenance_stamp(uri, references=(), time_value=None):
    """The small top left stamp, after ``idstools`` ``get_database_path``.

    ``plotscenario`` stamps "<host>:<entry> #time:<t>" there. The same line is
    written here, with the user who ran the tool, the moment the figure was
    made and the entries overlaid on it -- what one needs to tell two figures of
    the same run apart. The reference entries are named here and not in the
    title, which already carries the path of the main entry.
    """
    try:
        user = os.environ.get("USER") or getpass.getuser()
    except Exception:                                  # pragma: no cover
        user = "?"
    stamp = "%s:%s:%s" % (socket.gethostname(), user, uri)
    if time_value is not None:
        stamp += " #time:%.3f" % time_value
    stamp += "  --  generated %s" % datetime.datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S")
    if references:
        stamp += "  --  references: %s" % ", ".join(references)
    return stamp


def wall_outlines(entry):
    """First wall contours ``[(r, z), ...]`` of the ``wall`` IDS of ``entry``."""
    outlines = []
    try:
        wall = entry.get("wall", lazy=True)
    except Exception as exc:
        logger.info("no wall IDS (%s)", exc)
        return outlines
    try:
        if not len(wall.description_2d):
            return outlines
        for unit in wall.description_2d[0].limiter.unit:
            points_r = np.asarray(unit.outline.r, dtype=float)
            points_z = np.asarray(unit.outline.z, dtype=float)
            if points_r.size and points_r.size == points_z.size:
                outlines.append((points_r, points_z))
    except Exception as exc:
        logger.info("wall description_2d could not be read (%s)", exc)
    return outlines


def add_coil_voltages(entry, waveforms):
    """Fill ``coil_voltages`` from the ``pf_active`` IDS of ``entry``.

    ``pulse_schedule`` has no coil voltage reference, so the voltages of the
    matching entry are used instead; they are matched on the coil name so that
    the ordering of the two IDSs does not have to agree.
    """
    names = waveforms.get("coil_names_full") or []
    if not names:
        return
    try:
        pf_active = entry.get("pf_active", lazy=True)
    except Exception as exc:
        logger.info("no pf_active IDS for the coil voltages (%s)", exc)
        return
    try:
        ntime = waveforms["time_pf_active"].size
        available = {}
        for index in range(len(pf_active.coil)):
            coil = pf_active.coil[index]
            values = np.asarray(coil.voltage.data, dtype=float)
            if values.size:
                available[str(coil.name)] = values
        if not available:
            logger.info("pf_active holds no coil voltage")
            return
        voltages = np.full((len(names), ntime), np.nan)
        for row, name in enumerate(names):
            values = available.get(name)
            if values is None:
                continue
            length = min(ntime, values.size)
            voltages[row, :length] = values[:length]
        if has_data(voltages):
            waveforms["coil_voltages"] = voltages
    except Exception as exc:
        logger.info("coil voltages could not be read (%s)", exc)


def read_entry(uri, main=False):
    """Waveforms, wall outlines and provenance of one entry.

    Returns:
        dict or None: ``{"uri", "label", "waveforms", "wall"}``.
    """
    import imas

    try:
        entry = imas.DBEntry(uri, "r")
    except Exception as exc:
        logger.critical("cannot open %s: %s", uri, exc)
        return None
    with entry:
        has_pulse_schedule = False
        try:
            has_pulse_schedule = bool(entry.list_all_occurrences("pulse_schedule"))
        except Exception:
            has_pulse_schedule = False
        if has_pulse_schedule:
            ids = entry.get("pulse_schedule")
            waveforms = PulseScheduleCompute(ids).get_waveforms()
            add_coil_voltages(entry, waveforms)
        elif main:
            logger.critical("%s has no pulse_schedule IDS", uri)
            return None
        else:
            logger.info("%s has no pulse_schedule IDS, deriving the waveforms "
                        "from equilibrium/pf_active/core_sources/core_profiles",
                        uri)
            waveforms = WaveformsFromIdsCompute(entry).get_waveforms()
        walls = wall_outlines(entry) if main else []
    return {"uri": uri, "label": "PDS" if main else entry_label(uri),
            "waveforms": waveforms, "wall": walls}


def set_boundary_limits(ax, walls=None, margin=0.06):
    """Frame the poloidal cross-section panel.

    The first wall sets the frame when there is one -- a separatrix taken from an
    equilibrium often runs well past the divertor and would otherwise squeeze the
    machine out of the panel; without a wall, whatever was drawn sets it.
    """
    points_r, points_z = [], []
    for outline_r, outline_z in walls or []:
        points_r.append(np.asarray(outline_r, dtype=float))
        points_z.append(np.asarray(outline_z, dtype=float))
    if not points_r:
        for line in ax.lines:
            points_r.append(np.asarray(line.get_xdata(), dtype=float))
            points_z.append(np.asarray(line.get_ydata(), dtype=float))
    if not points_r:
        return
    points_r = np.concatenate(points_r)
    points_z = np.concatenate(points_z)
    points_r = points_r[np.isfinite(points_r)]
    points_z = points_z[np.isfinite(points_z)]
    if not points_r.size or not points_z.size:
        return
    pad = margin * max(np.ptp(points_r), np.ptp(points_z), 1.0)
    ax.set_xlim(points_r.min() - pad, points_r.max() + pad)
    ax.set_ylim(points_z.min() - pad, points_z.max() + pad)


def coil_colors(names):
    """A stable colour per coil name, shared by every entry of the figure."""
    import matplotlib

    palette = matplotlib.colormaps["tab20"].colors
    return {name: palette[index % len(palette)]
            for index, name in enumerate(names)}


#: size of the monospace font of the provenance panel, in points
INFO_FONTSIZE = 7.0
#: height of one of its lines, as a multiple of the font size
INFO_LINE_SPACING = 1.35
#: width of one of its characters, as a fraction of the font size
INFO_CHAR_WIDTH = 0.62
#: blank characters kept between two entries written side by side
INFO_COLUMN_GAP = 5
#: narrowest column the text is ever folded on
INFO_MIN_WIDTH = 44
#: widest, so that a single entry does not draw one line across the whole figure
INFO_MAX_WIDTH = 130
#: number of lines of the comment that are kept
INFO_COMMENT_LINES = 4


def short_uri(uri, keep=4):
    """The URI cut down to the last ``keep`` components of its path.

    Used by the titles: the full URI, which is far too long for a title, is
    written once in the provenance panel.
    """
    path = uri_path(uri)
    if not path:
        return uri
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) <= keep:
        return path
    return ".../" + "/".join(parts[-keep:])


def without_uris(text):
    """``text`` with every URI and absolute path replaced by its last component.

    A pulse schedule comment quotes the URIs it was built from; they are what
    makes it too long for the panel, and they are already listed above it.
    """
    words = []
    for word in text.split():
        if word.startswith("imas:") or word.startswith("/"):
            words.append(os.path.basename(word.strip("/;,")) or word)
        else:
            words.append(word)
    return " ".join(words)


def wrapped(prefix, text, width):
    """``prefix`` followed by ``text``, folded on ``width`` characters."""
    return textwrap.wrap(str(text), width=max(width, len(prefix) + 8),
                         initial_indent=prefix,
                         subsequent_indent=" " * len(prefix),
                         break_long_words=True, break_on_hyphens=False) \
        or [prefix]


def info_block(dataset, width, keep_uri=None, with_comment=True):
    """The provenance of one entry, as lines of at most ``width`` characters.

    Args:
        dataset (dict): entry, as returned by ``read_entry``.
        width (int): width of the column the lines are folded on.
        keep_uri (int, optional): shorten the URI to that many path components.
        with_comment (bool): keep the comment of the entry.
    """
    waveforms = dataset["waveforms"]
    info = waveforms.get("info") or {}
    uri = dataset["uri"] if keep_uri is None else short_uri(dataset["uri"], keep_uri)
    lines = wrapped("[%s] " % dataset["label"], uri, width)
    lines += wrapped("  from     : ", info.get("source") or "?", width)
    lines += wrapped("  created  : ", "%s   DD %s   homogeneous_time %s"
                     % (info.get("creation_date") or "?",
                        info.get("dd_version") or "?",
                        info.get("homogeneous_time") or "?"), width)
    lines += wrapped("  time     : ", "%s points in [%.2f, %.2f] s; coils: %d "
                     "(%d with a voltage)"
                     % (info.get("n_time", 0), info.get("t_min", float("nan")),
                        info.get("t_max", float("nan")), info.get("n_coil", 0),
                        waveforms["coil_voltages"].shape[0]
                        if waveforms["coil_voltages"].size else 0), width)
    lines += wrapped("  boundary : ", "%d points, %d X point(s)"
                     % (info.get("n_boundary_point", 0),
                        info.get("n_x_point", 0)), width)
    comment = " ".join((info.get("comment") or "").split())
    if comment:
        if not with_comment:
            comment = without_uris(comment)
        folded = wrapped("  comment  : ", comment, width)
        if len(folded) > INFO_COMMENT_LINES:
            folded = folded[:INFO_COMMENT_LINES]
            folded[-1] += " ..."
        lines += folded
    missing = waveforms.get("missing") or []
    if missing:
        short = [name.replace("pulse_schedule.", "").replace(".reference", "")
                 for name in missing]
        lines += wrapped("  missing  : ", "%d reference(s): %s"
                         % (len(short), ", ".join(short)), width)[:3]
    else:
        lines.append("  missing  : none")
    return lines


def info_columns(datasets, width, max_lines):
    """One block of provenance lines per entry, short enough for the panel.

    The whole URI and the whole comment are kept as long as the blocks fit in the
    ``max_lines`` the panel holds. When they do not, the URI is cut down to its
    last three components and the URIs quoted by the comment are dropped; only if
    that is still too long is the text truncated, which is then said explicitly.
    """
    width = min(max(int(width), INFO_MIN_WIDTH), INFO_MAX_WIDTH)
    blocks = []
    for keep_uri, with_comment in ((None, True), (3, False)):
        blocks = [info_block(dataset, width, keep_uri, with_comment)
                  for dataset in datasets]
        if max(len(block) for block in blocks) <= max_lines:
            return blocks
    return [block if len(block) <= max_lines
            else block[:max_lines - 1] + ["  ... (%d more lines)"
                                          % (len(block) - max_lines + 1)]
            for block in blocks]


def legend_style_note(datasets, tag_labels):
    """Legend title saying which line style belongs to which entry.

    Each quantity is then named once instead of once per entry.
    """
    if tag_labels or len(datasets) < 2:
        return None
    return "%s solid\n%s dashed" % (datasets[0]["label"], datasets[1]["label"])


# ---------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------
class _HelpFormatter(argparse.ArgumentDefaultsHelpFormatter,
                     argparse.RawDescriptionHelpFormatter):
    """Show the default of every option and keep the epilog as it is written."""


#: how the interactive window can be tuned, shown at the end of ``--help``
EPILOG = textwrap.dedent("""\
    environment:
      PDSPLOT_WINDOW_HEIGHT_FRACTION
                            share of the screen height the interactive window may
                            use (default 0.80). The rest is left to the window
                            manager frame, the matplotlib toolbar and the desktop
                            panels: ask for more and the window manager shrinks
                            the window, which squeezes the panels. Lower it (e.g.
                            0.70) if the window is still too tall, raise it (e.g.
                            0.88) on a screen with no panels to get a bigger
                            figure. Has no effect with --save.
""")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog=TOOL,
        description="Display the pulse schedule of a PDS run (references of the "
                    "pulse_schedule IDS), with input or reference entries "
                    "overlaid dashed.",
        epilog=EPILOG,
        formatter_class=_HelpFormatter)
    parser.add_argument("-u", "--uri", required=True,
                        help="URI of the data entry holding the pulse_schedule "
                             "(e.g. imas:hdf5?path=./imas_out)")
    parser.add_argument("-r", "--reference", action="append", default=[],
                        metavar="URI",
                        help="URI of an entry to overlay dashed; repeatable. Its "
                             "pulse_schedule is used when it has one, otherwise "
                             "the waveforms are derived from its physics IDSs")
    parser.add_argument("-t", "--time", type=float, default=-99.0,
                        help="time of the boundary snapshot; the nearest sample "
                             "is used, the default is the middle of the time base")
    parser.add_argument("--save", action="store_true",
                        help="save the figure instead of showing it")
    parser.add_argument("--directory", default=None,
                        help="directory the figure is saved into (created if "
                             "needed)")
    parser.add_argument("--rc", type=str, default="",
                        help="semicolon separated matplotlib rcParams, e.g. "
                             "'lines.linewidth=2;axes.titlesize=14'")
    parser.add_argument("--dpi", type=int, default=110,
                        help="resolution of the saved figure")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="verbose logging")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    setup_logger("module", logging.DEBUG if args.verbose else logging.INFO)
    select_backend(args.save)
    from ..view.common import PlotCanvas, TOP_RESERVE
    from ..view.pulse_schedule import PulseScheduleView

    main_dataset = read_entry(args.uri, main=True)
    if main_dataset is None:
        logger.critical("----> Aborted.")
        return 1
    datasets = [main_dataset]
    for uri in args.reference:
        dataset = read_entry(uri)
        if dataset is not None:
            datasets.append(dataset)

    time_array = main_dataset["waveforms"]["time"]
    if not len(time_array):
        logger.critical("the pulse_schedule of %s has an empty time base",
                        args.uri)
        return 1
    _, time_value = get_nearest_time(time_array, args.time)

    # 4 rows of panels and a provenance strip; the poloidal cross-section keeps
    # an equal aspect, so it is given the height of two rows to be wide enough to
    # be read. The constrained layout engine (see view.common.PlotCanvas) then
    # reserves the room the outside legends and the twin axis labels need. The
    # spacing left between the panels on top of that is the one place it is
    # tuned, view.common.PANEL_H_PAD and its neighbours, so it is not repeated
    # here: the panels are made as large as the decorations allow.
    canvas = PlotCanvas(5, 3, figsize=(20, 12.5),
                        height_ratios=[1.0, 1.0, 1.0, 1.0, 0.8],
                        top_reserve=TOP_RESERVE)
    canvas.update_style(args.rc)

    ax_flux = canvas.add_axes(row=0, col=0)
    ax_field = canvas.add_axes(row=0, col=1)
    ax_boundary = canvas.add_axes(row=0, col=2, rowspan=2)
    ax_cs = canvas.add_axes(row=1, col=0)
    ax_pf = canvas.add_axes(row=1, col=1)
    ax_volt = canvas.add_axes(row=2, col=0)
    ax_position = canvas.add_axes(row=2, col=1)
    ax_shape = canvas.add_axes(row=2, col=2)
    ax_xpoint = canvas.add_axes(row=3, col=0)
    ax_density = canvas.add_axes(row=3, col=1)
    ax_hcd = canvas.add_axes(row=3, col=2)
    ax_info = canvas.add_axes(row=4, col=0, colspan=3)

    ax_flux_right = ax_flux.twinx()
    ax_field_right = ax_field.twinx()
    ax_shape_right = ax_shape.twinx()
    ax_density_right = ax_density.twinx()

    colors = coil_colors(main_dataset["waveforms"].get("coil_names_full") or [])
    # two entries are told apart by their line style, more than two cannot be:
    # the entry name is then appended to every legend entry again
    tag_labels = len(datasets) > 2
    views = [PulseScheduleView(dataset["waveforms"], label=dataset["label"],
                               linestyle="-" if position == 0 else "--",
                               alpha=1.0 if position == 0 else 0.75,
                               tag_labels=tag_labels)
             for position, dataset in enumerate(datasets)]

    PulseScheduleView.view_wall(ax_boundary, main_dataset["wall"])
    x_point_drawn, hcd_drawn = False, False
    for view in views:
        view.view_flux_control_waveforms(ax_flux, ax_flux_right)
        view.view_field_stability_waveforms(ax_field, ax_field_right)
        view.view_boundary(ax_boundary, time_value)
        view.view_coil_currents(ax_cs, groups=("CS",), colors=colors)
        view.view_coil_currents(ax_pf, groups=("PF", "other"), colors=colors)
        view.view_coil_voltages(ax_volt, colors=colors)
        view.view_position_waveforms(ax_position)
        view.view_shape_waveforms(ax_shape, ax_shape_right)
        x_point_drawn |= bool(view.view_x_point_waveforms(ax_xpoint))
        view.view_density_waveforms(ax_density, ax_density_right)
        hcd_drawn |= bool(view.view_hcd_waveforms(ax_hcd))

    set_boundary_limits(ax_boundary, main_dataset["wall"])
    ax_cs.set_title("CS coil currents")
    ax_pf.set_title("PF / VS coil currents")
    ax_volt.set_title("Coil voltages")

    base = views[0]
    if not x_point_drawn:
        ax_xpoint.set_title("X point")
        base.empty_panel(ax_xpoint, "no X-point reference")
    if not hcd_drawn:
        # No EC/NBI/IC/LH power anywhere: the scenario simply activates none of
        # them, which is a statement about the pulse, not about missing data.
        base.empty_panel(ax_hcd, "no H&CD system activated")
    if not ax_volt.lines:
        base.empty_panel(ax_volt, "no coil voltage available")

    # the snapshot time on every waveform panel
    for ax in (ax_flux, ax_field, ax_cs, ax_pf, ax_volt, ax_position, ax_shape,
               ax_xpoint, ax_density, ax_hcd):
        if ax.lines:
            base.view_time_line(ax, time_value)

    # every legend beside its panel, never on top of the curves; the twin axis
    # entries are merged into the legend of the panel they belong to
    style_note = legend_style_note(datasets, tag_labels)
    for ax, twin, ncol in ((ax_flux, ax_flux_right, 1),
                           (ax_field, ax_field_right, 1),
                           (ax_boundary, None, 1),
                           (ax_cs, None, 2), (ax_pf, None, 2), (ax_volt, None, 2),
                           (ax_position, None, 1),
                           (ax_shape, ax_shape_right, 1),
                           (ax_xpoint, None, 1),
                           (ax_density, ax_density_right, 1),
                           (ax_hcd, None, 1)):
        base.outside_legend(ax, twin=twin, ncol=ncol, title=style_note)
    for ax in (ax_flux, ax_field, ax_cs, ax_pf, ax_volt, ax_position, ax_shape,
               ax_xpoint, ax_density, ax_hcd, ax_boundary):
        ax.grid(True, alpha=0.3)

    # the header of plotscenario: the sup title naming the entry and the time,
    # and the small stamp of the top left corner saying where, by whom and when
    # the figure was made. The stamp lives in the strip TOP_STAMP_RESERVE keeps
    # free above the layout, so it can collide with nothing.
    canvas.set_text(text=provenance_stamp(args.uri, args.reference, time_value))
    canvas.set_sup_title(figure_title(args.uri, time_value))
    try:
        canvas.get_current_fig_manager().set_window_title(TOOL)
    except Exception:
        pass

    # the provenance panel: one column per entry, folded on the width the panel
    # really has, which is only known once the layout engine has run
    ax_info.axis("off")
    ax_info.set_title("Entries  --  time slice: %.3f s" % time_value)
    canvas.layout()
    info_width_pt, info_height_pt = canvas.axes_size_in_points(ax_info)
    ncol_info = max(len(datasets), 1)
    columns = info_columns(
        datasets,
        info_width_pt / ncol_info / (INFO_CHAR_WIDTH * INFO_FONTSIZE)
        - INFO_COLUMN_GAP,
        max(4, int(info_height_pt / (INFO_LINE_SPACING * INFO_FONTSIZE))))
    for position, lines in enumerate(columns):
        ax_info.text(float(position) / ncol_info, 1.0, "\n".join(lines),
                     transform=ax_info.transAxes, ha="left", va="top",
                     fontsize=INFO_FONTSIZE, family="monospace",
                     linespacing=INFO_LINE_SPACING)

    if args.save:
        fname = figure_name(args.uri, time_value)
        if args.directory:
            os.makedirs(args.directory, exist_ok=True)
            fname = os.path.join(args.directory, fname)
        canvas.save(fname, dpi=args.dpi)
        print("Figure saved to %s" % os.path.abspath(fname))
    else:
        canvas.show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
