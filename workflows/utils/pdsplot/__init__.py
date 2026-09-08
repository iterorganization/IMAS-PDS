"""Plotting tools for PDS results, built on IMAS-Python, numpy and matplotlib.

The package is deliberately laid out like ``idstools`` -- a ``compute`` layer that
turns IDSs into plain dictionaries of numpy arrays, and a ``view`` layer that only
knows about those dictionaries -- so that a tool written here can be moved into
``idstools`` with little more than a rename of the top-level package.  ``pdsplot``
is therefore a placeholder name: the intended destination of
``pdsplot.compute.pulse_schedule`` / ``pdsplot.view.pulse_schedule`` /
``pdsplot.scripts.plotpulseschedule`` is ``idstools.*``.

It is kept self-contained on purpose: IDStools is built with a different toolchain
than the PDS Python stack and cannot be imported from a PDS run, so nothing here
imports it.  The only dependencies are numpy, matplotlib and imas (IMAS-Python).
"""

__all__ = ["compute", "view", "scripts"]
