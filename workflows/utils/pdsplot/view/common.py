"""Figure and axes helpers, laid out like ``idstools.view.common``.

Only matplotlib is used: the module offers a ``PlotCanvas`` grid of axes with
``save``/``show``, and a ``BasePlot`` base class carrying the small annotations
every panel shares.

The grid is a ``GridSpec`` driven by matplotlib's *constrained* layout engine:
the engine measures the decorations of every panel -- titles, tick labels, the
label of a twin (right hand) axis and the legends placed *outside* the axes --
and gives each of them the room it needs, so that nothing is written on top of
anything else whatever the figure size.

The matplotlib backend is chosen once, by ``scripts.plotpulseschedule.main()``
(see ``select_backend()`` there), before this module -- and therefore
``matplotlib.pyplot`` -- is ever imported. This module must not be imported
before that choice has been made.
"""

import logging
import os
import sys

import matplotlib
import matplotlib.pyplot as plt

logger = logging.getLogger("module")

#: share of the screen width the interactive window may use
WINDOW_WIDTH_FRACTION = 0.92

#: share of the screen height it may use. The rest is what the window manager
#: frame, the matplotlib toolbar and the task bar or panels need: ask for more
#: and the window manager shrinks the window, which squeezes the figure.
WINDOW_HEIGHT_FRACTION = 0.80

#: environment variable overriding ``WINDOW_HEIGHT_FRACTION``, so that a screen
#: with unusually tall panels can be accommodated without touching the code
HEIGHT_FRACTION_ENV = "PDSPLOT_WINDOW_HEIGHT_FRACTION"

#: how many times the window is fitted again after the window manager has had
#: its say on the geometry
MAX_FIT_ATTEMPTS = 3

#: how much the height fraction is lowered at each of those attempts
FIT_ATTEMPT_STEP = 0.07

#: relative change of the width/height ratio above which the figure is taken to
#: have been squeezed rather than merely rounded
ASPECT_TOLERANCE = 0.02

# Spacing of the panels, for the constrained layout engine. The pads are in
# inches and are kept around the *decorations* of a panel, so the room a title,
# an x label or an outside legend needs is measured and reserved on top of them:
# they only have to be the small breathing space between two panels that are
# already fully drawn, not a guess at how tall a label is. A row carries an x
# label at its bottom and the title of the row below at its top, so the gap
# between two rows of panels is 2 * PANEL_H_PAD, measured at 0.20 in with the
# values below -- enough to read them apart, and no more.
#: room kept above and below the decorations of a panel, in inches
PANEL_H_PAD = 0.10
#: same, left and right, in inches
PANEL_W_PAD = 0.08
#: extra space between two rows, as a fraction of the figure height. It is a
#: floor only: it is not what sets the gap here, the pads are.
PANEL_HSPACE = 0.06
#: same between two columns. Kept small: the outside legends already separate
#: the columns, and the engine has reserved the room they need.
PANEL_WSPACE = 0.02

# The header occupies two strips at the very top of the figure, which the
# layout engine is kept out of (``rect``): the provenance stamp of ``set_text``
# is a figure text, and the engine reserves room for the sup title alone --
# left to itself it pins the title at the top edge, straight through the stamp.
#: height, in inches, of the strip of the stamp, the "host:user:entry" line
#: ``idstools`` writes in the top left corner. It leaves the stamp the
#: ``y=0.985`` baseline it has in ``plotscenario`` on a 12.5 in figure.
TOP_STAMP_RESERVE = 0.28
#: height, in inches, of the strip of the sup title, just under the stamp
SUP_TITLE_RESERVE = 0.30
#: what the two of them take from the panels
TOP_RESERVE = TOP_STAMP_RESERVE + SUP_TITLE_RESERVE


def window_height_fraction(default=WINDOW_HEIGHT_FRACTION):
    """Share of the screen height the interactive window may use.

    ``PDSPLOT_WINDOW_HEIGHT_FRACTION`` overrides the default; a value outside
    ``[0.2, 1.0]``, or one that is not a number, is ignored with a warning.
    """
    raw = os.environ.get(HEIGHT_FRACTION_ENV)
    if not raw:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning("%s='%s' is not a number, using %.2f",
                       HEIGHT_FRACTION_ENV, raw, default)
        return default
    if not 0.2 <= value <= 1.0:
        logger.warning("%s=%.2f is outside [0.2, 1.0], using %.2f",
                       HEIGHT_FRACTION_ENV, value, default)
        return default
    return value


class PlotCanvas:
    """A grid of axes on a single figure.

    Args:
        nrows (int): number of rows of the grid.
        ncols (int): number of columns of the grid.
        height_ratios (list, optional): relative height of each row.
        width_ratios (list, optional): relative width of each column.
        constrained (bool): let the constrained layout engine place the panels,
            so that the outside legends and the twin axis labels are given room
            instead of being drawn over the neighbouring panel.
        wspace (float): horizontal space between panels. With ``constrained`` it
            is the fraction of the figure width left between two columns, on top
            of the room the decorations and the outside legends were given.
        hspace (float): vertical space between panels, likewise. What keeps the
            "time [s]" label of a row away from the title of the row below it is
            the measured ``h_pad``, not this floor.
        h_pad (float): room kept above and below the decorations of a panel, in
            inches; the gap between two rows is twice that.
        w_pad (float): same, left and right of a panel.
        top_reserve (float): height, in inches, of the header strip kept free at
            the very top of the figure, outside the layout: the panels are laid
            out below it. The provenance stamp of ``set_text``, which the layout
            engine cannot see, and the sup title, which it would pin to the top
            edge, are placed in it by hand; see ``TOP_RESERVE``.
        args, kwargs: passed to ``matplotlib.pyplot.figure`` (``figsize`` ...).
    """

    def __init__(self, nrows=1, ncols=1, *args, height_ratios=None,
                 width_ratios=None, constrained=True, wspace=PANEL_WSPACE,
                 hspace=PANEL_HSPACE, h_pad=PANEL_H_PAD, w_pad=PANEL_W_PAD,
                 top_reserve=0.0, **kwargs):
        self.nrows = nrows
        self.ncols = ncols
        self.constrained = constrained
        self.top_reserve = top_reserve
        self.fig = plt.figure(*args, **kwargs)
        if constrained:
            # The pads are in inches and sit *outside* the decorations the
            # engine has already measured, so they are only the breathing space
            # between two finished panels: see PANEL_H_PAD above. ``rect`` is
            # the part of the figure the engine may use, so the panels stay
            # under the header strip; the stamp and the sup title are placed in
            # that strip by ``set_text`` and ``set_sup_title``.
            height = self.fig.get_size_inches()[1]
            top = 1.0 - (top_reserve / height if height > 0 else 0.0)
            self.fig.set_layout_engine("constrained", w_pad=w_pad, h_pad=h_pad,
                                       wspace=wspace, hspace=hspace,
                                       rect=(0.0, 0.0, 1.0, top))
        self.grid = self.fig.add_gridspec(nrows, ncols,
                                          height_ratios=height_ratios,
                                          width_ratios=width_ratios)
        if not constrained:
            self.fig.subplots_adjust(hspace=0.5, wspace=0.6)

    def add_axes(self, title=None, xlabel=None, ylabel=None, row=0, col=0,
                 rowspan=1, colspan=1, **kwargs):
        """Add a subplot at ``(row, col)``, optionally spanning several cells."""
        ax = self.fig.add_subplot(
            self.grid[row:row + rowspan, col:col + colspan], **kwargs)
        if title is not None:
            ax.set_title(title)
        if xlabel is not None:
            ax.set_xlabel(xlabel)
        if ylabel is not None:
            ax.set_ylabel(ylabel)
        return ax

    def layout(self):
        """Run the layout engine, so that the panel positions can be read back."""
        try:
            self.fig.draw_without_rendering()
        except Exception as exc:  # pragma: no cover - backend dependent
            logger.debug("could not pre-render the figure: %s", exc)

    def axes_size_in_points(self, ax):
        """Width and height of ``ax``, in typographic points."""
        position = ax.get_position()
        width, height = self.fig.get_size_inches()
        return position.width * width * 72.0, position.height * height * 72.0

    def save(self, fname, width=None, height=None, dpi="figure"):
        """Save the figure, printing the path the way ``idstools`` does.

        The size set at construction time is kept unless ``width``/``height`` are
        given. Nothing is cropped: the constrained layout engine has already
        fitted the outside legends inside the figure.
        """
        if width is not None and height is not None:
            self.fig.set_size_inches(width, height)
        try:
            self.fig.savefig(fname, dpi=dpi)
            print("----> Figure saved to %s" % fname, file=sys.stderr)
            return True
        except Exception as exc:
            logger.critical("could not save %s: %s", fname, exc)
            return False

    def set_text(self, x=0.001, y=0.985, text="", ha="left", fontsize=7):
        """Add a small annotation in figure coordinates.

        The defaults are those of ``idstools.view.common.PlotCanvas.set_text``,
        so that the provenance stamp of a PDS figure sits where ``plotscenario``
        puts it: top left corner, 7 points, the default colour. Pass
        ``top_reserve=TOP_STAMP_RESERVE`` at construction time to keep that
        corner clear of the sup title.
        """
        self.fig.text(x, y, text, ha=ha, fontsize=fontsize)

    def set_sup_title(self, text="", *args, **kwargs):
        """Set the title spanning all the panels.

        With a header strip (``top_reserve``), the title is placed in it,
        immediately under the provenance stamp: left to itself the layout engine
        pins the title to the top edge of the figure, which is where the stamp
        is. Giving it a ``y`` is what tells matplotlib to leave it where it is
        put; the strip is what keeps the panels out of it.
        """
        if self.top_reserve and "y" not in kwargs:
            height = self.fig.get_size_inches()[1]
            if height > 0:
                kwargs["y"] = 1.0 - min(TOP_STAMP_RESERVE,
                                        self.top_reserve) / height
                kwargs.setdefault("va", "top")
        self.fig.suptitle(text, *args, **kwargs)

    def show(self, *args, **kwargs):
        """Display the figure, or explain why not when there is no display.

        Skips ``plt.show()`` -- and the ``UserWarning`` it raises -- when the
        current backend is the non-interactive ``Agg``. This is an exact match
        on the backend name ("agg"), not a suffix check: backends such as
        ``TkAgg`` or ``QtAgg`` also end in "agg" but are interactive.

        The window is resized *before* being shown so that the layout engine,
        which runs at draw time, lays the panels out for the size they will
        really have. The figure is wider and taller than a usual screen, so its
        resolution is lowered until the whole of it fits: shown at its nominal
        dpi it would be cropped by the window, and the panels would overlap what
        the layout engine had carefully kept apart.

        Lowering the resolution is not enough on its own, though: the window
        manager frame, the toolbar and the screen panels are added *around* the
        canvas, and a window that no longer fits is shrunk by the window
        manager. The Tk resize callback then reduces the figure *height* in
        inches, keeping its width, and the layout engine is handed a flattened
        figure. So the window is mapped, the geometry read back, and the fit
        repeated at a lower resolution until the 20 x 12.5 aspect survives; see
        ``fit_to_screen``.
        """
        if matplotlib.get_backend().lower() == "agg":
            logger.info("no interactive matplotlib backend available (DISPLAY "
                        "unset or Tk/Qt not importable): nothing will be shown, "
                        "use --save --directory DIR")
            return
        manager, window, screen = None, None, None
        try:
            manager = plt.get_current_fig_manager()
            window = manager.window
            screen = (float(window.winfo_screenwidth()),
                      float(window.winfo_screenheight()))
        except Exception:
            logger.debug("screen size not available from the current backend")
        if screen:
            self.fit_to_screen(*screen, manager=manager, window=window)
        plt.show(*args, **kwargs)

    def _apply_geometry(self, dpi, width, height, manager=None):
        """Give the figure ``dpi`` at ``width`` x ``height`` inches, and resize."""
        self.fig.set_dpi(dpi)
        self.fig.set_size_inches(width, height, forward=True)
        if manager is not None:
            try:
                manager.resize(int(round(width * dpi)), int(round(height * dpi)))
            except Exception:
                logger.debug("window resizing not supported by the current "
                             "backend")

    def fit_to_screen(self, screen_width, screen_height,
                      width_fraction=WINDOW_WIDTH_FRACTION,
                      height_fraction=None, manager=None, window=None):
        """Lower the resolution until the *whole window* fits on the screen.

        The figure size in inches is what the layout engine works with and is
        kept: only the number of pixels an inch is worth is reduced, so the
        window shrinks while every panel keeps the room it was given, and the
        panels keep the proportions of the saved figure.

        The canvas is aimed at ``min(width_fraction * screen_width,
        height_fraction * screen_height * aspect)`` pixels wide, that is, at
        whichever of the two screen dimensions is the binding one, the other
        following from the aspect of the figure. The height fraction is
        deliberately well under one: the window manager frame, the matplotlib
        toolbar and the screen panels all sit outside the canvas.

        When ``manager``/``window`` are given, the window is then mapped and its
        geometry read back. Should the window manager have shrunk it -- the Tk
        resize callback answers that by cutting the figure *height* in inches,
        which is exactly what flattens the panels -- the intended inches are
        applied again at a lower resolution, up to ``MAX_FIT_ATTEMPTS`` times,
        lowering the height fraction by ``FIT_ATTEMPT_STEP`` each time.

        One shrink is not the window manager's doing and does not cost such a
        step: Tk multiplies the resolution of the figure by the pixel ratio of
        the screen the first time the window is mapped (1.425 on a NoMachine
        session at 137 dpi), so the canvas asks for that many pixels more than
        was computed here and overflows the screen. The ratio is then part of
        the resolution that is read back, so simply fitting once more at the
        same fraction lands on the intended size.

        Args:
            screen_width (float): screen width, in pixels.
            screen_height (float): screen height, in pixels.
            width_fraction (float): share of the screen width the window may use.
            height_fraction (float): same for the height; the default comes from
                ``window_height_fraction()``, i.e. from
                ``PDSPLOT_WINDOW_HEIGHT_FRACTION`` when it is set.
            manager: figure manager, resized along with the figure.
            window: its toolkit window, mapped to check the geometry really
                obtained. Without it the fit is applied once, blind.

        Returns:
            float: the resolution the figure ends up with, in dots per inch.
        """
        width, height = self.fig.get_size_inches()
        if not (width > 0 and height > 0 and screen_width > 0
                and screen_height > 0):
            return self.fig.get_dpi()
        aspect = width / height
        if height_fraction is None:
            height_fraction = window_height_fraction()
        fraction = height_fraction

        attempt, attempts, rescaled_once = 0, MAX_FIT_ATTEMPTS, False
        while attempt < attempts:
            attempt += 1
            target_width = min(screen_width * width_fraction,
                               screen_height * fraction * aspect)
            target_height = target_width / aspect
            dpi = target_height / height
            self._apply_geometry(dpi, width, height, manager)
            if window is None:
                break
            try:
                # Map the window: the frame and the toolbar are added here, and
                # the window manager shrinks what no longer fits. The window is
                # withdrawn until the manager shows it, and a withdrawn window
                # is given no geometry, so it has to be shown now rather than by
                # the ``plt.show()`` that follows -- which then merely enters the
                # event loop of an already mapped window.
                if manager is not None:
                    manager.show()
                window.update()
                mapped_width, mapped_height = self.fig.get_size_inches()
                geometry = window.winfo_geometry()
            except Exception:
                logger.debug("window geometry not readable from the current "
                             "backend")
                break
            mapped_aspect = (mapped_width / mapped_height
                             if mapped_height > 0 else aspect)
            if abs(mapped_aspect - aspect) <= ASPECT_TOLERANCE * aspect:
                logger.info("interactive window %s: figure %.1f x %.1f in at "
                            "%.0f dpi, canvas %d x %d px, using %.0f%% of the "
                            "height of a %d x %d screen (%s=%.2f)", geometry,
                            mapped_width, mapped_height, self.fig.get_dpi(),
                            *self.fig.canvas.get_width_height(), 100.0 * fraction,
                            int(screen_width), int(screen_height),
                            HEIGHT_FRACTION_ENV, height_fraction)
                return self.fig.get_dpi()
            if not rescaled_once and abs(self.fig.get_dpi() - dpi) > 0.01 * dpi:
                # the toolkit, not the window manager: the resolution asked for
                # was multiplied by the pixel ratio of the screen when the window
                # was mapped, so the same fraction fits once that is known
                rescaled_once = True
                attempts += 1
                logger.debug("attempt %d: the toolkit rescaled the figure from "
                             "%.1f to %.1f dpi when mapping the window (screen "
                             "pixel ratio); fitting again at the same %.2f "
                             "height fraction", attempt, dpi, self.fig.get_dpi(),
                             fraction)
                continue
            logger.debug("attempt %d: the window manager shrank the window to "
                         "%s, the figure to %.2f x %.2f in (aspect %.3f instead "
                         "of %.3f); fitting again at a %.2f height fraction",
                         attempt, geometry, mapped_width, mapped_height,
                         mapped_aspect, aspect,
                         max(0.2, fraction - FIT_ATTEMPT_STEP))
            fraction = max(0.2, fraction - FIT_ATTEMPT_STEP)

        # Whatever the window manager did, the layout engine must see the
        # nominal aspect: a figure squeezed in height writes the x labels of a
        # row over the title of the row below it.
        if tuple(self.fig.get_size_inches()) != (width, height):
            self.fig.set_size_inches(width, height, forward=False)
            logger.info("the window manager keeps shrinking the window; the "
                        "figure is kept at %.1f x %.1f in (%.0f dpi) so the "
                        "panels stay readable -- lower %s (currently %.2f) if "
                        "the window is still too tall", width, height,
                        self.fig.get_dpi(), HEIGHT_FRACTION_ENV, height_fraction)
        return self.fig.get_dpi()

    def get_current_fig_manager(self):
        """The matplotlib figure manager of the current figure."""
        return plt.get_current_fig_manager()

    def update_style(self, param_string=""):
        """Apply a semicolon separated ``key=value`` list of matplotlib rcParams."""
        for item in (param_string or "").split(";"):
            if not item.strip():
                continue
            try:
                key, value = item.split("=", 1)
                matplotlib.rcParams[key.strip()] = eval(value.strip(), {}, {})
            except Exception as exc:
                logger.warning("could not apply rcParam '%s': %s", item, exc)


class BasePlot:
    """Annotations shared by every panel of a waveform figure."""

    #: styling of the vertical line marking the snapshot time
    time_line_style = {"color": "gray", "linestyle": "--", "linewidth": 1.0}

    #: left edge of an outside legend, in axes coordinates
    legend_x = 1.02
    #: same, for a panel carrying a twin axis whose ticks and label sit there
    legend_x_twin = 1.20

    def view_time_line(self, ax, time):
        """Draw a vertical dashed line at ``time`` without changing the y range."""
        if time is None:
            return
        ymin, ymax = ax.get_ylim()
        ax.axvline(time, **self.time_line_style)
        ax.set_ylim(ymin, ymax)

    def show_info_on_plot(self, ax, info="", location="right"):
        """Write a small provenance string beside an axes."""
        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
        if location == "top":
            ax.text(xmin, ymax, info, horizontalalignment="left",
                    verticalalignment="bottom", fontsize=6)
        else:
            ax.text(xmax + 0.01 * abs(xmax), ymin + 0.01 * abs(ymax - ymin), info,
                    horizontalalignment="left", verticalalignment="center",
                    rotation="vertical", fontsize=6)

    @staticmethod
    def empty_panel(ax, message):
        """Replace an empty panel by a centred message."""
        ax.text(0.5, 0.5, message, transform=ax.transAxes, ha="center",
                va="center", fontsize=9, color="dimgray")
        ax.set_xticks([])
        ax.set_yticks([])

    @staticmethod
    def outside_legend(ax, twin=None, ncol=1, fontsize=7, title=None):
        """Draw the legend of a panel beside it, never on top of the curves.

        The entries of the twin (right hand) axis, when there is one, are merged
        into that single legend, and the legend is then anchored further right so
        that it clears the ticks and the label of the twin axis. The constrained
        layout engine reserves the room the legend needs, so the panels shrink
        instead of the legend covering its neighbour.

        Args:
            ax: axes whose curves are listed.
            twin: twin axes whose curves are listed too, or None.
            ncol (int): number of columns of the legend.
            fontsize (float): size of the entries, and of ``title``.
            title (str): heading of the legend, e.g. what the line styles mean.

        Returns:
            The legend, or None when the panel holds no labelled curve.
        """
        handles, labels = ax.get_legend_handles_labels()
        if twin is not None:
            twin_handles, twin_labels = twin.get_legend_handles_labels()
            handles = handles + twin_handles
            labels = labels + twin_labels
        if not handles:
            return None
        holder = twin if twin is not None else ax
        anchor = BasePlot.legend_x_twin if twin is not None else BasePlot.legend_x
        return holder.legend(handles, labels, loc="upper left",
                             bbox_to_anchor=(anchor, 1.0), fontsize=fontsize,
                             ncol=ncol, framealpha=0.85, handlelength=1.5,
                             labelspacing=0.28, columnspacing=1.0, borderpad=0.35,
                             title=title, title_fontsize=fontsize,
                             borderaxespad=0.0)
