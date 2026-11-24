"""Shared time-slider machinery for the postprocessing plots.

A :class:`SliderFigure` is one matplotlib figure with a title, a full-width time slider
between the title and the plots, and the plots themselves. The same figure is

* shown in a window with ``--interactive`` (drag the slider, or use the arrow keys), or
* saved, by :func:`show_or_save`, as one PNG per slider time plus an HTML page in which
  the slider drawn in the figure can be dragged to scroll through time.

Slider times come from :func:`slider_times`: always the first, middle and last time
slice of every timebase, plus ``--max_slices`` evenly spaced times.

Subclasses draw their content in ``self.fig`` (whose top strip is kept free for the title
and slider), implement :meth:`SliderFigure.draw`, and call ``self.update(0)`` when done.
"""

import argparse
import os
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider


def add_slider_args(parser: argparse.ArgumentParser):
    """Add --output_dir, --max_slices and --interactive to a script's arguments"""
    parser.add_argument(
        "--output_dir",
        type=str,
        default=f"{os.environ['RUN_DIR']}/plots" if os.environ.get("RUN_DIR") else None,
        help="path to directory in which to put plots (default: $RUN_DIR/plots)",
    )
    parser.add_argument(
        "--max_slices",
        type=int,
        default=3,
        help=(
            "Number of evenly spaced times on the time slider (default: 3). The first, "
            "middle and last time slice are always included as well"
        ),
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Open matplotlib windows with a time slider instead of writing files",
    )


def check_slider_args(parser: argparse.ArgumentParser, args: argparse.Namespace):
    """Validate the arguments of add_slider_args and pick the matplotlib backend"""
    if not args.interactive and args.output_dir is None:
        parser.error("--output_dir (or $RUN_DIR) is required unless --interactive is given")
    if not args.interactive:
        matplotlib.use("Agg")


def merge_times(times, tol=1e-6):
    """Sorted times with (near-)duplicates merged"""
    times = np.sort(np.asarray(times, dtype=float))
    keep = np.concatenate([[True], np.diff(times) > tol])
    return times[keep]


def slider_times(timebases, max_slices: int):
    """Slider times for one or more timebases.

    Always the first, middle and last time slice of every timebase, plus ``max_slices``
    evenly spaced times over their combined range (skipping those within 1% of that range
    of an always-included slice, so no near-identical frames).
    """
    required = []
    for t in timebases:
        t = np.asarray(t)
        required += [t[0], t[len(t) // 2], t[-1]]
    required = np.asarray(required, dtype=float)
    evenly = np.linspace(required.min(), required.max(), max_slices)
    close = 0.01 * (required.max() - required.min())
    evenly = [t for t in evenly if np.min(np.abs(required - t)) > close]
    return merge_times(np.concatenate([required, evenly]))


def nearest_index(times, t) -> int:
    """Index of the time in ``times`` closest to ``t``"""
    return int(np.argmin(np.abs(np.asarray(times) - t)))


def data_limits(values, margin=0.05):
    """Padded (min, max) over all finite values in a list of arrays"""
    if len(values) == 0:
        return -1, 1
    flat = np.concatenate([np.ravel(v) for v in values])
    flat = flat[np.isfinite(flat)]
    if flat.size == 0:
        return -1, 1
    lo, hi = flat.min(), flat.max()
    pad = (hi - lo) * margin or abs(hi) * margin or 1
    return lo - pad, hi + pad


class SliderFigure:
    """A figure with a title and a full-width time slider above its plots.

    The slider steps over the slider times (evenly spaced in slider position, so the HTML
    slider can be laid exactly over it) and shows the selected time. Moving it, by mouse,
    arrow keys or :meth:`update`, calls :meth:`draw` with the frame number.
    """

    # Top strip for the (two-line) title and the slider, in inches so it looks the same
    # whatever the figure height
    TOP_STRIP = 1.0
    SLIDER_TOP = 0.9  # slider centre, below the top edge
    SLIDER_HEIGHT = 0.3

    def __init__(self, frame_times, figsize=(18, 10)):
        self.frame_times = list(frame_times)
        self.fig = plt.figure(figsize=figsize, layout="constrained")
        height = figsize[1]
        self.fig.get_layout_engine().set(rect=(0, 0, 1, 1 - self.TOP_STRIP / height))
        self.suptitle = self.fig.suptitle("")

        # Full width, between title and plots, as (left, bottom, width, height)
        self.slider_rect = (
            0.06,
            1 - (self.SLIDER_TOP + self.SLIDER_HEIGHT / 2) / height,
            0.86,
            self.SLIDER_HEIGHT / height,
        )
        self.ax_slider = self.fig.add_axes(self.slider_rect)
        self.slider = Slider(
            self.ax_slider,
            "time [s]",
            0,
            max(len(self.frame_times) - 1, 1),
            valinit=0,
            valstep=1,
        )
        self.slider.on_changed(lambda value: self._redraw(int(value)))
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)

    def draw(self, frame: int):
        """Update the plots for slider time ``self.frame_times[frame]``"""
        raise NotImplementedError

    def title(self, frame: int) -> str:
        """Figure title at slider time ``self.frame_times[frame]``"""
        return ""

    def update(self, frame: int):
        """Move the slider to ``frame`` and redraw; returns the figure's artists"""
        if int(self.slider.val) == frame:
            self._redraw(frame)  # set_val only calls back on a change
        else:
            self.slider.set_val(frame)
        return self.fig.get_children()

    def _redraw(self, frame: int):
        frame = min(frame, len(self.frame_times) - 1)
        self.draw(frame)
        self.suptitle.set_text(self.title(frame))
        self.slider.valtext.set_text(f"{self.frame_times[frame]:.3f}")
        self.fig.canvas.draw_idle()

    def _on_key(self, event):
        """Left/right arrow keys step one slider time"""
        frame = int(self.slider.val)
        if event.key == "right":
            self.update(min(frame + 1, len(self.frame_times) - 1))
        elif event.key == "left":
            self.update(max(frame - 1, 0))

    def save(self, output_dir, name: str, title: str):
        """Write ``<name>_t=<time>.png`` per slider time and a scrollable ``<name>.html``"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for frame, t in enumerate(self.frame_times):
            self.update(frame)
            path = output_dir / f"{name}_t={t:.3f}.png"
            print(f"Writing {path}")
            self.fig.savefig(path)

        matplotlib.rcParams["animation.embed_limit"] = 500  # MB
        anim = FuncAnimation(
            self.fig, self.update, frames=len(self.frame_times), blit=False
        )
        path = output_dir / f"{name}.html"
        print(f"Writing {path} ({len(self.frame_times)} times)")
        html = anim.to_jshtml(fps=5, default_mode="once")

        # The frames already show the figure's own slider. Lay matplotlib's HTML range
        # input invisibly over it, so dragging the slider in the image scrolls through
        # time. Both map frame numbers linearly onto the same rectangle.
        x0, y0, w, h = self.slider_rect
        style = f"""<style>
.animation {{ display: block; width: 100%; }}
.slider-figure {{ position: relative; }}
.slider-figure img {{ display: block; width: 100%; height: auto; }}
.slider-figure input[type=range].anim-slider {{
  position: absolute; margin: 0; opacity: 0; cursor: pointer;
  left: {x0 * 100}%; top: {(1 - y0 - h) * 100}%; width: {w * 100}%; height: {h * 100}%;
}}
</style>"""
        script = """<script>
document.querySelectorAll(".animation").forEach(function (anim) {
  var img = anim.querySelector("img");
  var wrap = document.createElement("div");
  wrap.className = "slider-figure";
  img.parentNode.insertBefore(wrap, img);
  wrap.appendChild(img);
  wrap.appendChild(anim.querySelector("input.anim-slider"));
});
</script>"""
        # style must come after html: matplotlib's own <style> would otherwise override it
        path.write_text(f"<!doctype html><title>{title}</title>{html}{style}{script}")


def show_or_save(figures, args: argparse.Namespace):
    """Show the slider figures (--interactive), or save each as PNGs + HTML.

    ``figures`` is a list of (SliderFigure, file name, HTML page title).
    """
    if args.interactive:
        plt.show()
    else:
        for figure, name, title in figures:
            figure.save(args.output_dir, name, title)
    for figure, _, _ in figures:
        plt.close(figure.fig)
