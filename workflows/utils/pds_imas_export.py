#!/usr/bin/env python3
"""Build a single IMAS data entry from the outputs of a PDS run.

A PDS run scatters its results over several data entries (one per actor) and
re-uses the scenario input entries for everything the actors did not compute.
This script gathers them into ONE output data entry holding one occurrence
(0) of each IDS, and adds a ``summary`` IDS and a ``pulse_schedule`` IDS
derived from the collected data.

Hierarchy rule
--------------
Several entries can contain an IDS with the same name.  The rule applied here
is that the designated code output wins:

* ``equilibrium``   comes only from the entry given by ``--equilibrium``
  (the equilibrium code, e.g. NICE);
* ``core_profiles`` comes only from the entry given by ``--core-profiles``
  (the transport code, e.g. TORAX);
* every other IDS is taken from the first entry that has it, scanning the
  equilibrium entry, then the core-profiles entry, then the ``--extra``
  entries in the order given (machine description before scenario inputs);
* ``summary`` and ``dataset_description`` are always built here and never
  copied from a source entry;
* ``pulse_schedule`` is copied when a source entry provides one (a code that
  writes its own schedule owns it) and derived here otherwise.

``pf_active`` gets a dedicated merge: the static machine-description IDS
(coil geometry, names, resistances, circuits) is completed with the coil
currents and voltages computed by the run.

2D equilibrium reconstruction
-----------------------------
An equilibrium code that solves on a finite-element mesh (NICE) stores its
solution as GGD node values and leaves ``profiles_2d`` empty.  With
``--equilibrium-2d auto`` (the default) the exporter rebuilds, for every such
time slice, one ``profiles_2d`` entry on a rectangular (R, Z) grid: psi, phi and
j_phi are interpolated linearly from the nodes, B_r and B_z are derived from
grad(psi) and B_phi from f(psi)/R, and ``global_quantities.psi_axis`` and
``magnetic_axis.b_field_phi`` are completed from ``profiles_1d``.  The grid
extent follows the wall limiter outline when a ``wall`` IDS is available.
``--equilibrium-2d off`` leaves the equilibrium untouched.

Derived pulse schedule
----------------------
The PDS is a pulse design simulator: the converged trajectories of a run are
the pulse that was designed.  With ``--pulse-schedule auto`` (the default) and
when no source entry already provides a ``pulse_schedule``, one is built on the
summary time base from the collected results: ``flux_control`` (ip, v_loop,
li_3, beta_tor_norm), ``tf`` (b0 * r0), ``position_control`` (geometric and
magnetic axis, minor radius, elongation, triangularities, the boundary outline
resampled to a fixed number of points and the X points), ``pf_active`` (the
designed coil currents), ``density_control`` and the launched heating powers.
Every waveform is written as an absolute reference (``reference_type`` 1) with
a ``reference_name`` recording its provenance.  ``--pulse-schedule off``
disables the derivation (a ``pulse_schedule`` found in a source entry is still
copied).

Usage example
-------------
    pds_imas_export.py \\
        --output       "imas:hdf5?path=<run>/imas_out" \\
        --equilibrium  "imas:hdf5?path=<run>/out_nice" \\
        --core-profiles "imas:hdf5?path=<run>/out_torax" \\
        --extra "imas:hdf5?path=<scen>/data/in_md" "imas:hdf5?path=<scen>/data/in" \\
        --machine ITER --shot 105073 --workflow inverse_convergence \\
        --equilibrium-2d auto --pulse-schedule auto
"""

import argparse
import datetime
import getpass
import logging
import os
import subprocess
import sys

import numpy as np

import imas
from imas import identifiers

LOGGER = logging.getLogger("pds_imas_export")

# IDSs that this script builds itself and therefore never copies from a source.
BUILT_HERE = ("summary", "dataset_description")

# core_sources identifier indices used below (see core_source_identifier).
SRC_NBI = 2
SRC_EC = 3
SRC_LH = 4
SRC_IC = 5
SRC_FUSION = 6
SRC_OHMIC = 7
SRC_AUXILIARY = 100
SRC_RADIATION_TOTAL = 200
# Radiation components, summed only when the total (200) is absent.
SRC_RADIATION_PARTS = (8, 9, 10, 201, 203)

# Heating and current drive systems: <system> -> (core_sources identifier index,
# summary path, pulse_schedule node).  The aggregated "auxiliary" source (100)
# carries no system of its own; --auxiliary-heating says which one it is.
HCD_SYSTEMS = {
    "ec": (SRC_EC, "heating_current_drive.power_ec"),
    "nbi": (SRC_NBI, "heating_current_drive.power_nbi"),
    "ic": (SRC_IC, "heating_current_drive.power_ic"),
    "lh": (SRC_LH, "heating_current_drive.power_lh"),
}

# Source string of a summary heating power that does not come from a per-system
# core_sources entry but from the aggregated auxiliary source, attributed to one
# system because that is how the workflow labels it (see --auxiliary-heating).
AUXILIARY_ATTRIBUTED = (
    "core_sources auxiliary (identifier %d) attributed to %s: the workflow's "
    "waveform editor labels the imported heating source '%s'")

# summary.volume_average.n_i / line_average.n_i sub-structure per species.
ION_NAME_TO_SUMMARY = {
    "H": "hydrogen",
    "D": "deuterium",
    "T": "tritium",
    "HE3": "helium_3",
    "HE": "helium_4",
    "HE4": "helium_4",
    "BE": "beryllium",
    "LI": "lithium",
    "C": "carbon",
    "N": "nitrogen",
    "NE": "neon",
    "AR": "argon",
    "XE": "xenon",
    "O": "oxygen",
    "W": "tungsten",
    "FE": "iron",
    "KR": "krypton",
}
# Fallback identification by (a, z_n) rounded, for ions with an unusable name.
ION_Z_TO_SUMMARY = {
    1: "hydrogen",
    2: "helium_4",
    4: "beryllium",
    6: "carbon",
    7: "nitrogen",
    8: "oxygen",
    10: "neon",
    18: "argon",
    26: "iron",
    36: "krypton",
    54: "xenon",
    74: "tungsten",
}


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def has(node) -> bool:
    """True when an IDS leaf or structure holds data."""
    try:
        return bool(node.has_value)
    except Exception:
        return False


def arr(node) -> np.ndarray:
    """A float array view of an IDS numeric leaf."""
    return np.asarray(node, dtype=float)


def finite(values) -> bool:
    """True when the array is non-empty and free of NaN/inf."""
    values = np.asarray(values, dtype=float)
    return values.size > 0 and bool(np.all(np.isfinite(values)))


def ids_dd_version(ids) -> str:
    try:
        if has(ids.ids_properties.version_put.data_dictionary):
            return str(ids.ids_properties.version_put.data_dictionary)
    except Exception:
        pass
    return "unknown"


def code_name(ids, fallback: str) -> str:
    try:
        if has(ids.code.name):
            return str(ids.code.name)
    except Exception:
        pass
    return fallback


def git_short_hash(repo: str):
    if not repo:
        return None
    try:
        out = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True)
        return out.stdout.strip() or None
    except Exception:
        return None


def n_time_points(ids) -> int:
    """Number of time points of an IDS, whatever its homogeneous_time."""
    try:
        if has(ids.time):
            return int(np.asarray(ids.time).size)
    except Exception:
        pass
    for aos in ("time_slice", "profiles_1d"):
        try:
            return len(getattr(ids, aos))
        except Exception:
            continue
    return 0


def trapz(y, x):
    """np.trapezoid under either numpy name."""
    integrate = getattr(np, "trapezoid", None) or np.trapz
    return integrate(y, x)


# --------------------------------------------------------------------------
# collection of the source IDSs
# --------------------------------------------------------------------------
def list_ids_names(entry, factory) -> list:
    """Names of the IDSs that hold data in ``entry`` (occurrence 0 only)."""
    present = []
    for name in factory.ids_names():
        try:
            occurrences = entry.list_all_occurrences(name)
        except Exception:
            continue
        if occurrences is not None and len(occurrences) > 0:
            present.append(name)
    return present


def read_ids(entry, name):
    return entry.get(name, autoconvert=False)


def is_static_pf_active(pf) -> bool:
    """True for a machine-description pf_active: coil geometry but no current."""
    for coil in pf.coil:
        if has(coil.current.data):
            return False
    return True


def merge_pf_active(static, dynamic):
    """Machine-description pf_active completed with the run's coil signals.

    The static IDS is modified in place and returned: it keeps coil names,
    geometry, resistances and circuits, and receives ``current``/``voltage``
    plus the time base of the dynamic IDS.
    """
    n_static, n_dynamic = len(static.coil), len(dynamic.coil)
    if n_static != n_dynamic:
        LOGGER.warning(
            "pf_active merge: %d coils in the machine description vs %d in the "
            "run output; merging the first %d by index",
            n_static, n_dynamic, min(n_static, n_dynamic))
    for i in range(min(n_static, n_dynamic)):
        for signal in ("current", "voltage"):
            src = getattr(dynamic.coil[i], signal)
            dst = getattr(static.coil[i], signal)
            if has(src.data):
                dst.data = arr(src.data)
            try:
                if has(src.time):
                    dst.time = arr(src.time)
            except Exception:
                pass
    if has(dynamic.time):
        static.time = arr(dynamic.time)
    static.ids_properties.homogeneous_time = int(
        dynamic.ids_properties.homogeneous_time)
    if has(dynamic.code.name):
        static.code.name = str(dynamic.code.name)
        if has(dynamic.code.version):
            static.code.version = str(dynamic.code.version)
    return static


def collect(args, factory):
    """Return ({ids_name: ids}, {ids_name: source uri}) following the hierarchy."""
    collected, provenance = {}, {}
    entries = []

    def open_entry(uri):
        LOGGER.info("opening %s", uri)
        return imas.DBEntry(uri, "r")

    def take(entry, uri, name):
        ids = read_ids(entry, name)
        collected[name] = ids
        provenance[name] = uri
        LOGGER.info("  %-22s <- %s", name, uri)

    eq_entry = eq_uri = None
    if args.equilibrium:
        eq_uri = args.equilibrium
        eq_entry = open_entry(eq_uri)
        entries.append(eq_entry)
        for name in list_ids_names(eq_entry, factory):
            if name in BUILT_HERE:
                continue
            take(eq_entry, eq_uri, name)

    if args.core_profiles:
        cp_uri = args.core_profiles
        cp_entry = open_entry(cp_uri)
        entries.append(cp_entry)
        for name in list_ids_names(cp_entry, factory):
            if name in BUILT_HERE:
                continue
            if name == "equilibrium":
                # Hierarchy rule: the equilibrium comes from the equilibrium code.
                LOGGER.info("  %-22s skipped in %s (equilibrium code owns it)",
                            name, cp_uri)
                continue
            if name in collected and name != "core_profiles":
                continue
            take(cp_entry, cp_uri, name)

    for uri in args.extra or []:
        entry = open_entry(uri)
        entries.append(entry)
        for name in list_ids_names(entry, factory):
            if name in BUILT_HERE or name in ("equilibrium", "core_profiles"):
                continue
            if name == "pf_active" and name in collected:
                candidate = read_ids(entry, name)
                if is_static_pf_active(candidate) and not is_static_pf_active(
                        collected[name]):
                    LOGGER.info("  %-22s merged: machine description %s + coil "
                                "signals from %s", name, uri, provenance[name])
                    dynamic_uri = provenance[name]
                    collected[name] = merge_pf_active(candidate, collected[name])
                    provenance[name] = f"{uri} (geometry) + {dynamic_uri} (signals)"
                continue
            if name in collected:
                continue
            take(entry, uri, name)

    return collected, provenance, entries


# --------------------------------------------------------------------------
# 2D equilibrium reconstruction from the GGD nodes
# --------------------------------------------------------------------------
# Some equilibrium codes (NICE) only store their solution on the finite-element
# mesh, as a set of GGD node values, and leave profiles_2d empty.  Most
# post-processing and plotting tools (and every ray-tracing code) expect a
# rectangular (R, Z) map, so the map is rebuilt here from the node values.

# Node values at or above this magnitude are sentinels written by the
# equilibrium code where the quantity is undefined (the toroidal flux outside
# the separatrix, the toroidal field on the machine axis) and must be kept out
# of the interpolation.
GGD_SENTINEL = 1e30

# Margins added around the outline that sets the extent of the rectangular grid.
WALL_MARGIN = 0.2
BOUNDARY_MARGIN = 1.0
# Last-resort box, large enough for an ITER-size plasma.
FALLBACK_BOX = (3.0, 9.0, -6.0, 6.0)

PROFILES_2D_COMMENT = (
    "profiles_2d reconstructed by pds_imas_export from the NICE GGD node values "
    "(psi, phi, j_phi linear interpolation; B_r, B_z from grad psi; "
    "B_phi = f(psi)/R)")


def ggd_values(ggd, name):
    """Node values of a GGD quantity of one time slice, or None."""
    try:
        node = getattr(ggd, name)
    except Exception:
        return None
    try:
        if len(node) == 0 or not has(node[0].values):
            return None
        values = arr(node[0].values)
    except Exception:
        return None
    return values if values.size else None


class GgdInterpolator:
    """Interpolates GGD node values onto a fixed rectangular (R, Z) grid.

    The Delaunay triangulation of the node cloud is built once and shared by
    every quantity and every time slice using the same mesh, which is what
    ``scipy.interpolate.griddata(..., method="linear")`` would rebuild on each
    call.  Sentinel nodes are excluded per quantity; the holes they leave, and
    any point outside the convex hull of the mesh, are filled by nearest
    neighbour.
    """

    def __init__(self, r_nodes, z_nodes, r_mesh, z_mesh):
        from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
        from scipy.spatial import Delaunay
        self._linear = LinearNDInterpolator
        self._nearest = NearestNDInterpolator
        self.points = np.column_stack((r_nodes, z_nodes))
        self.triangulation = Delaunay(self.points)
        self.r_mesh, self.z_mesh = r_mesh, z_mesh

    def matches(self, r_nodes, z_nodes) -> bool:
        """True when the node cloud is the one this interpolator was built on."""
        return (self.points.shape[0] == r_nodes.size
                and np.array_equal(self.points[:, 0], r_nodes)
                and np.array_equal(self.points[:, 1], z_nodes))

    def __call__(self, values):
        """(map on the grid, number of sentinel nodes dropped), or (None, n)."""
        values = np.asarray(values, dtype=float)
        if values.size != self.points.shape[0]:
            return None, 0
        usable = np.isfinite(values) & (np.abs(values) < GGD_SENTINEL)
        dropped = int(values.size - np.count_nonzero(usable))
        if not np.any(usable):
            return None, dropped
        masked = np.where(usable, values, np.nan)
        grid = self._linear(self.triangulation, masked)(self.r_mesh, self.z_mesh)
        holes = ~np.isfinite(grid)
        if np.any(holes):
            fill = self._nearest(self.points[usable], values[usable])
            grid[holes] = fill(self.r_mesh[holes], self.z_mesh[holes])
        return grid, dropped


def outline_extent(outline):
    """(r_min, r_max, z_min, z_max) of an r/z outline, or None."""
    try:
        if not (has(outline.r) and has(outline.z)):
            return None
        r, z = arr(outline.r), arr(outline.z)
    except Exception:
        return None
    if r.size < 2 or r.size != z.size or not (finite(r) and finite(z)):
        return None
    return float(r.min()), float(r.max()), float(z.min()), float(z.max())


def wall_extent(wall):
    """Extent of the first limiter outline of a wall IDS, or None."""
    if wall is None:
        return None
    try:
        return outline_extent(wall.description_2d[0].limiter.unit[0].outline)
    except Exception:
        return None


def plasma_extent(equilibrium):
    """Extent of the plasma boundary over all time slices, or None."""
    extents = []
    for slice_ in equilibrium.time_slice:
        try:
            extent = outline_extent(slice_.boundary.outline)
        except Exception:
            extent = None
        if extent is not None:
            extents.append(extent)
    if not extents:
        return None
    extents = np.asarray(extents, dtype=float)
    return (float(extents[:, 0].min()), float(extents[:, 1].max()),
            float(extents[:, 2].min()), float(extents[:, 3].max()))


def widen(extent, margin):
    r_min, r_max, z_min, z_max = extent
    return (r_min - margin, r_max + margin, z_min - margin, z_max + margin)


def grid_box(equilibrium, wall, log):
    """Rectangular box (r_min, r_max, z_min, z_max) and the label of its source.

    The wall is preferred, the plasma boundary is the fallback and a fixed
    ITER-size box the last resort.  Whatever the source, the box is widened
    when needed so that the plasma boundary of every time slice fits inside it:
    a map that cuts through the separatrix is useless downstream.
    """
    plasma = plasma_extent(equilibrium)
    extent = wall_extent(wall)
    if extent is not None:
        box = widen(extent, WALL_MARGIN)
        label = "wall limiter outline + %.2f m" % WALL_MARGIN
    elif plasma is not None:
        box = widen(plasma, BOUNDARY_MARGIN)
        label = "plasma boundary outline + %.2f m" % BOUNDARY_MARGIN
    else:
        box = FALLBACK_BOX
        label = "fixed fallback box"
    if plasma is not None:
        needed = widen(plasma, WALL_MARGIN)
        wider = (min(box[0], needed[0]), max(box[1], needed[1]),
                 min(box[2], needed[2]), max(box[3], needed[3]))
        if wider != box:
            log.info("equilibrium 2d grid: box from the %s widened from "
                     "R %.3f..%.3f Z %.3f..%.3f to enclose the plasma boundary",
                     label, box[0], box[1], box[2], box[3])
            box = wider
            label += ", widened to enclose the plasma boundary"
    return box, label


def axis_end(slice_):
    """Index (0 or -1) of the magnetic-axis end of profiles_1d, or None."""
    try:
        if not has(slice_.profiles_1d.psi):
            return None
        psi = arr(slice_.profiles_1d.psi)
    except Exception:
        return None
    if psi.size < 2 or not finite(psi):
        return None
    try:
        if has(slice_.global_quantities.psi_boundary):
            psi_boundary = float(slice_.global_quantities.psi_boundary)
            return 0 if (abs(psi[0] - psi_boundary)
                         > abs(psi[-1] - psi_boundary)) else -1
    except Exception:
        pass
    # DD convention: profiles_1d runs from the magnetic axis outwards.
    return 0


def complete_global_quantities(slice_, b0_r0, log):
    """Fill psi_axis and the axis toroidal field when the code left them empty."""
    end = axis_end(slice_)
    if end is None:
        return
    psi_1d = arr(slice_.profiles_1d.psi)
    if not has(slice_.global_quantities.psi_axis):
        slice_.global_quantities.psi_axis = float(psi_1d[end])
    axis = slice_.global_quantities.magnetic_axis
    if has(axis.b_field_phi):
        return
    r_axis = float(axis.r) if has(axis.r) else 0.0
    if r_axis <= 0.0:
        return
    f_axis = 0.0
    try:
        if has(slice_.profiles_1d.f):
            f_1d = arr(slice_.profiles_1d.f)
            if f_1d.size == psi_1d.size:
                f_axis = float(f_1d[end])
    except Exception:
        f_axis = 0.0
    if f_axis != 0.0:
        axis.b_field_phi = f_axis / r_axis
    elif b0_r0 is not None:
        axis.b_field_phi = b0_r0 / r_axis


def toroidal_field_map(slice_, psi, r_mesh, b0_r0, log):
    """B_phi = f(psi)/R on the grid, or None.

    ``np.interp`` needs an increasing abscissa, so psi/f are sorted; outside the
    plasma the interpolation clamps to the value at the boundary end, i.e. to
    the vacuum f = R0*B0.
    """
    try:
        if not (has(slice_.profiles_1d.psi) and has(slice_.profiles_1d.f)):
            return None
        psi_1d = arr(slice_.profiles_1d.psi)
        f_1d = arr(slice_.profiles_1d.f)
    except Exception:
        return None
    if psi_1d.size < 2 or psi_1d.size != f_1d.size:
        return None
    if not (finite(psi_1d) and finite(f_1d)):
        return None
    order = np.argsort(psi_1d)
    psi_sorted, f_sorted = psi_1d[order], f_1d[order]
    if np.any(np.diff(psi_sorted) <= 0.0):
        keep = np.concatenate(([True], np.diff(psi_sorted) > 0.0))
        psi_sorted, f_sorted = psi_sorted[keep], f_sorted[keep]
        if psi_sorted.size < 2:
            return None
    end = axis_end(slice_)
    f_boundary = float(f_1d[0 if end == -1 else -1])
    if b0_r0 is not None and f_boundary != 0.0 \
            and np.sign(f_boundary) != np.sign(b0_r0):
        log.warning("equilibrium 2d: f at the boundary (%.3f) and "
                    "vacuum_toroidal_field b0*r0 (%.3f) have opposite signs",
                    f_boundary, b0_r0)
    return np.interp(psi, psi_sorted, f_sorted) / r_mesh


def field_cross_check(slice_, ggd, interpolator, fields, r_mesh, z_mesh, log):
    """Compare the reconstructed B with the GGD B nodes inside the plasma."""
    extent = None
    try:
        extent = outline_extent(slice_.boundary.outline)
    except Exception:
        extent = None
    if extent is None:
        inside = np.ones(r_mesh.shape, dtype=bool)
    else:
        inside = ((r_mesh >= extent[0]) & (r_mesh <= extent[1])
                  & (z_mesh >= extent[2]) & (z_mesh <= extent[3]))
    if not np.any(inside):
        return
    reference = {}
    for name in ("b_field_r", "b_field_z", "b_field_phi"):
        nodes = ggd_values(ggd, name)
        if nodes is None:
            continue
        grid, _ = interpolator(nodes)
        if grid is not None:
            reference[name] = grid
    if not reference:
        log.info("equilibrium 2d: no GGD magnetic field to cross-check against")
        return
    poloidal = np.hypot(fields["b_field_r"], fields["b_field_z"])
    for name, expected in reference.items():
        scale = np.abs(expected) if name == "b_field_phi" else poloidal
        good = inside & np.isfinite(expected) & np.isfinite(fields[name]) \
            & (scale > 0.0)
        if not np.any(good):
            continue
        relative = np.abs(fields[name][good] - expected[good]) / scale[good]
        median = float(np.median(relative))
        message = ("equilibrium 2d cross-check: %s median relative difference "
                   "to the GGD nodes %.1f%% (max %.1f%%)")
        if median > 0.10:
            log.warning(message, name, 100.0 * median,
                        100.0 * float(np.max(relative)))
        else:
            log.info(message, name, 100.0 * median,
                     100.0 * float(np.max(relative)))


def interpolator_source(slice_):
    """The GGD structure a slice's node values are read from."""
    return slice_.ggd[0]


def add_profiles_2d(equilibrium, wall=None, nr=129, nz=161, log=LOGGER):
    """Reconstruct equilibrium/time_slice/profiles_2d from the GGD node values.

    Every time slice with an empty ``profiles_2d`` and a ``ggd[0]`` holding r, z
    and psi node values gets one ``profiles_2d`` entry on a rectangular grid
    shared by all slices: psi, phi and j_phi are interpolated linearly from the
    nodes, B_r and B_z are derived from grad(psi) and B_phi from f(psi)/R.
    ``global_quantities.psi_axis`` and ``magnetic_axis.b_field_phi`` are
    completed from profiles_1d when the equilibrium code left them empty.

    Returns the number of time slices for which profiles_2d was written.
    """
    if equilibrium is None or len(equilibrium.time_slice) == 0:
        return 0
    try:
        import scipy  # noqa: F401  - imported for the error message only
    except ImportError:
        log.warning("scipy is not available: profiles_2d not reconstructed")
        return 0

    b0_r0 = None
    try:
        vacuum = equilibrium.vacuum_toroidal_field
        if has(vacuum.b0) and has(vacuum.r0):
            b0 = arr(vacuum.b0)
            if b0.size:
                b0_r0 = float(b0[0]) * float(vacuum.r0)
    except Exception:
        b0_r0 = None

    box, label = grid_box(equilibrium, wall, log)
    r_grid = np.linspace(box[0], box[1], nr)
    z_grid = np.linspace(box[2], box[3], nz)
    r_mesh, z_mesh = np.meshgrid(r_grid, z_grid, indexing="ij")
    dr = float(r_grid[1] - r_grid[0])
    dz = float(z_grid[1] - z_grid[0])
    log.info("equilibrium 2d grid: R %.3f..%.3f (%d points, dR %.3f m), "
             "Z %.3f..%.3f (%d points, dZ %.3f m), extent from the %s",
             box[0], box[1], nr, dr, box[2], box[3], nz, dz, label)

    interpolator = None
    filled = 0
    checked = False
    for index, slice_ in enumerate(equilibrium.time_slice):
        complete_global_quantities(slice_, b0_r0, log)
        if len(slice_.profiles_2d) > 0:
            continue
        if len(slice_.ggd) == 0:
            log.warning("equilibrium 2d: time slice %d has no ggd, skipped",
                        index)
            continue
        ggd = interpolator_source(slice_)
        r_nodes = ggd_values(ggd, "r")
        z_nodes = ggd_values(ggd, "z")
        psi_nodes = ggd_values(ggd, "psi")
        if r_nodes is None or z_nodes is None or psi_nodes is None \
                or not (r_nodes.size == z_nodes.size == psi_nodes.size):
            log.warning("equilibrium 2d: time slice %d has no usable ggd "
                        "r/z/psi node values, skipped", index)
            continue
        if interpolator is None or not interpolator.matches(r_nodes, z_nodes):
            interpolator = GgdInterpolator(r_nodes, z_nodes, r_mesh, z_mesh)
        psi, dropped = interpolator(psi_nodes)
        if psi is None:
            log.warning("equilibrium 2d: time slice %d has no finite psi node "
                        "value, skipped", index)
            continue
        if dropped:
            log.info("equilibrium 2d: time slice %d, %d psi node values were "
                     "sentinels and were interpolated over", index, dropped)

        # COCOS 17 (DD 4): B_z = (1/(2 pi R)) dpsi/dR, B_r = -(1/(2 pi R)) dpsi/dZ.
        two_pi_r = 2.0 * np.pi * r_mesh
        fields = {
            "b_field_z": np.gradient(psi, dr, axis=0, edge_order=1) / two_pi_r,
            "b_field_r": -np.gradient(psi, dz, axis=1, edge_order=1) / two_pi_r,
        }
        toroidal = toroidal_field_map(slice_, psi, r_mesh, b0_r0, log)
        if toroidal is not None:
            fields["b_field_phi"] = toroidal
        elif index == 0:
            log.warning("equilibrium 2d: no profiles_1d psi/f, B_phi not built")

        slice_.profiles_2d.resize(1)
        profiles_2d = slice_.profiles_2d[0]
        profiles_2d.grid_type.index = 1
        profiles_2d.grid_type.name = "rectangular"
        profiles_2d.grid_type.description = (
            "Cylindrical R,Z ascending grid rebuilt in post-processing: psi, "
            "phi and j_phi linearly interpolated from the GGD node values of "
            "the equilibrium code, B_r and B_z from grad(psi), B_phi = f(psi)/R")
        profiles_2d.type.index = 0
        profiles_2d.type.name = "total"
        profiles_2d.type.description = "Total fields"
        profiles_2d.grid.dim1 = r_grid
        profiles_2d.grid.dim2 = z_grid
        profiles_2d.r = r_mesh
        profiles_2d.z = z_mesh
        profiles_2d.psi = psi
        for name, values in fields.items():
            setattr(profiles_2d, name, values)
        for name in ("phi", "j_phi"):
            nodes = ggd_values(ggd, name)
            if nodes is None or nodes.size != r_nodes.size:
                continue
            grid, dropped = interpolator(nodes)
            if grid is None:
                continue
            setattr(profiles_2d, name, grid)
            if dropped and index == 0:
                log.info("equilibrium 2d: %s undefined on %d of %d nodes, "
                         "filled by nearest neighbour", name, dropped,
                         nodes.size)
        filled += 1

        if not checked and "b_field_phi" in fields:
            checked = True
            log.info("equilibrium 2d: cross-checking time slice %d (t = %.3f s)",
                     index, float(slice_.time))
            field_cross_check(slice_, ggd, interpolator, fields, r_mesh,
                              z_mesh, log)

    if filled:
        try:
            comment = str(equilibrium.ids_properties.comment).strip() \
                if has(equilibrium.ids_properties.comment) else ""
        except Exception:
            comment = ""
        if PROFILES_2D_COMMENT not in comment:
            equilibrium.ids_properties.comment = (
                comment + " | " + PROFILES_2D_COMMENT if comment
                else PROFILES_2D_COMMENT)
        log.info("equilibrium 2d: profiles_2d written for %d of %d time slices",
                 filled, len(equilibrium.time_slice))
    else:
        log.info("equilibrium 2d: nothing to reconstruct")
    return filled


# --------------------------------------------------------------------------
# summary building blocks
# --------------------------------------------------------------------------
class SummaryBuilder:
    """Fills a summary IDS from the collected IDSs."""

    def __init__(self, summary, times, equilibrium, core_profiles, core_sources,
                 auxiliary_heating=None):
        self.s = summary
        self.t = np.asarray(times, dtype=float)
        self.eq = equilibrium
        self.cp = core_profiles
        self.cs = core_sources
        # System the aggregated auxiliary source is attributed to, or None.
        self.auxiliary_heating = (auxiliary_heating
                                  if auxiliary_heating in HCD_SYSTEMS else None)
        self.filled = []
        self.eq_src = "equilibrium (%s)" % code_name(equilibrium, "equilibrium") \
            if equilibrium is not None else "equilibrium"
        self.cp_src = "core_profiles (%s)" % code_name(core_profiles, "transport") \
            if core_profiles is not None else "core_profiles"
        self.cs_src = "core_sources (%s)" % code_name(core_sources, "input") \
            if core_sources is not None else "core_sources"
        self._eq_area = None

    # -- generic setters ---------------------------------------------------
    def set(self, path, values, source):
        """Set <path>.value/.source when the data is usable; return success."""
        values = np.asarray(values, dtype=float)
        if values.size != self.t.size or not finite(values):
            return False
        node = self.s
        for part in path.split("."):
            node = getattr(node, part)
        node.value = values
        node.source = source
        self.filled.append(path)
        return True

    def set_plain(self, path, values):
        """Set a leaf that has no .source companion (e.g. local positions)."""
        values = np.asarray(values, dtype=float)
        if values.size != self.t.size or not finite(values):
            return False
        parts = path.split(".")
        node = self.s
        for part in parts[:-1]:
            node = getattr(node, part)
        setattr(node, parts[-1], values)
        self.filled.append(path)
        return True

    # -- interpolation -----------------------------------------------------
    def to_summary_time(self, source_time, values):
        """Interpolate a time trace onto the summary time base."""
        source_time = np.asarray(source_time, dtype=float)
        values = np.asarray(values, dtype=float)
        if source_time.size != values.size or source_time.size == 0:
            return None
        if source_time.size == 1:
            return None
        return np.interp(self.t, source_time, values)

    # -- equilibrium -------------------------------------------------------
    def eq_slice_trace(self, getter):
        """Per-slice scalar of the equilibrium, already on the summary time."""
        if self.eq is None:
            return None
        out = []
        for slice_ in self.eq.time_slice:
            try:
                value = getter(slice_)
            except Exception:
                return None
            if value is None:
                return None
            out.append(value)
        out = np.asarray(out, dtype=float)
        return out if out.size == self.t.size and finite(out) else None

    def fill_from_equilibrium(self):
        eq = self.eq
        if eq is None:
            return
        src = self.eq_src

        def gq(name):
            return self.eq_slice_trace(
                lambda s, n=name: float(getattr(s.global_quantities, n))
                if has(getattr(s.global_quantities, n)) else None)

        for path, name in (
                ("global_quantities.ip", "ip"),
                ("global_quantities.beta_pol", "beta_pol"),
                ("global_quantities.beta_tor", "beta_tor"),
                ("global_quantities.li_3", "li_3"),
                ("global_quantities.volume", "volume"),
                ("global_quantities.q_95", "q_95"),
                ("global_quantities.energy_mhd", "energy_mhd"),
        ):
            values = gq(name)
            if values is not None:
                self.set(path, values, src)

        # global_quantities.area has no summary field (DD confirmed: there is
        # no summary.global_quantities.area); keep it only as a local trace
        # for the IPB98(y,2) area elongation (kappa_a) in fill_confinement.
        area = gq("area")
        if area is not None:
            self._eq_area = area

        # b0/r0: vacuum_toroidal_field is a root-level array over eq.time.
        try:
            if has(eq.vacuum_toroidal_field.b0):
                b0 = arr(eq.vacuum_toroidal_field.b0)
                if b0.size == self.t.size:
                    self.set("global_quantities.b0", b0, src)
            if has(eq.vacuum_toroidal_field.r0):
                self.s.global_quantities.r0.value = float(
                    eq.vacuum_toroidal_field.r0)
                self.s.global_quantities.r0.source = src
                self.filled.append("global_quantities.r0")
        except Exception:
            pass

        # boundary
        for path, getter in (
                ("boundary.geometric_axis_r",
                 lambda s: float(s.boundary.geometric_axis.r)),
                ("boundary.geometric_axis_z",
                 lambda s: float(s.boundary.geometric_axis.z)),
                ("boundary.minor_radius", lambda s: float(s.boundary.minor_radius)),
                ("boundary.elongation", lambda s: float(s.boundary.elongation)),
                ("boundary.triangularity_upper",
                 lambda s: float(s.boundary.triangularity_upper)),
                ("boundary.triangularity_lower",
                 lambda s: float(s.boundary.triangularity_lower)),
                ("boundary.magnetic_axis_r",
                 lambda s: float(s.global_quantities.magnetic_axis.r)),
                ("boundary.magnetic_axis_z",
                 lambda s: float(s.global_quantities.magnetic_axis.z)),
        ):
            values = self.eq_slice_trace(getter)
            if values is not None:
                self.set(path, values, src)

        # boundary.type is an integer flag in the DD (0 limiter, 1 diverted).
        boundary_type = self.eq_slice_trace(lambda s: float(s.boundary.type)
                                            if has(s.boundary.type) else None)
        if boundary_type is not None:
            self.s.boundary.type.value = np.rint(boundary_type).astype(np.int32)
            self.s.boundary.type.source = src
            self.filled.append("boundary.type")

        # x_point_main is only filled when the equilibrium carries x points;
        # DD 4.0.0 equilibrium/time_slice/boundary has no x_point AoS, so this
        # stays empty unless a later DD version provides one.
        x_r, x_z = [], []
        for slice_ in eq.time_slice:
            try:
                points = slice_.boundary.x_point
            except Exception:
                x_r = []
                break
            if len(points) == 0:
                x_r = []
                break
            x_r.append(float(points[0].r))
            x_z.append(float(points[0].z))
        if x_r:
            if finite(x_r) and len(x_r) == self.t.size:
                self.s.boundary.x_point_main.r = np.asarray(x_r)
                self.s.boundary.x_point_main.z = np.asarray(x_z)
                self.s.boundary.x_point_main.source = src
                self.filled.append("boundary.x_point_main.r")
                self.filled.append("boundary.x_point_main.z")

        # magnetic axis position
        for path, getter in (
                ("local.magnetic_axis.position.r",
                 lambda s: float(s.global_quantities.magnetic_axis.r)),
                ("local.magnetic_axis.position.z",
                 lambda s: float(s.global_quantities.magnetic_axis.z)),
        ):
            values = self.eq_slice_trace(getter)
            if values is not None:
                self.set_plain(path, values)
        psi_axis = self.eq_slice_trace(
            lambda s: float(s.global_quantities.psi_axis)
            if has(s.global_quantities.psi_axis)
            else (float(arr(s.profiles_1d.psi)[0])
                  if has(s.profiles_1d.psi) else None))
        if psi_axis is not None:
            self.set_plain("local.magnetic_axis.position.psi", psi_axis)

    # -- core_profiles -----------------------------------------------------
    def cp_profile_trace(self, func):
        """Scalar per core_profiles slice, interpolated onto the summary time."""
        if self.cp is None or not has(self.cp.time):
            return None
        out = []
        for profile in self.cp.profiles_1d:
            try:
                value = func(profile)
            except Exception:
                return None
            if value is None:
                return None
            out.append(value)
        out = np.asarray(out, dtype=float)
        if out.size != len(self.cp.time) or not finite(out):
            return None
        return self.to_summary_time(arr(self.cp.time), out)

    def cp_global_trace(self, node):
        if not has(node) or self.cp is None or not has(self.cp.time):
            return None
        values = arr(node)
        if values.size != np.asarray(self.cp.time).size:
            return None
        return self.to_summary_time(arr(self.cp.time), values)

    @staticmethod
    def volume_integral(profile, node):
        grid_volume = profile.grid.volume
        if not has(grid_volume) or not has(node):
            return None
        volume = arr(grid_volume)
        values = arr(node)
        if volume.size != values.size or volume.size < 2:
            return None
        return float(trapz(values, volume))

    def volume_average(self, profile, node):
        integral = self.volume_integral(profile, node)
        if integral is None:
            return None
        volume = arr(profile.grid.volume)[-1]
        return integral / volume if volume > 0 else None

    def fill_from_core_profiles(self):
        cp = self.cp
        if cp is None:
            return
        src = self.cp_src
        gq = cp.global_quantities

        for path, node in (
                ("global_quantities.v_loop", gq.v_loop),
                ("global_quantities.current_bootstrap", gq.current_bootstrap),
                ("global_quantities.beta_tor_norm", gq.beta_tor_norm),
        ):
            values = self.cp_global_trace(node)
            if values is not None:
                self.set(path, values, src)

        # non-inductive current: cp value if present, bootstrap otherwise.
        non_inductive = self.cp_global_trace(gq.current_non_inductive)
        non_inductive_src = src
        if non_inductive is None:
            non_inductive = self.cp_global_trace(gq.current_bootstrap)
            non_inductive_src = "derived: bootstrap only (%s)" % src
        if non_inductive is not None:
            self.set("global_quantities.current_non_inductive",
                     non_inductive, non_inductive_src)
            plasma_current = self.cp_global_trace(gq.ip)
            ohm_src = "derived: ip - current_non_inductive (%s)" % src
            if plasma_current is None:
                plasma_current = self.summary_value("global_quantities.ip")
                ohm_src = "derived: ip - current_non_inductive (%s, %s)" % (
                    self.eq_src, src)
            if plasma_current is not None:
                self.set("global_quantities.current_ohm",
                         plasma_current - non_inductive, ohm_src)

        # thermal energies
        for path, node_name, label in (
                ("global_quantities.energy_thermal", "pressure_thermal",
                 "1.5 * int(pressure_thermal) dV"),
                ("global_quantities.energy_electrons_thermal", None,
                 "1.5 * int(electrons.pressure_thermal) dV"),
                ("global_quantities.energy_ion_total_thermal",
                 "pressure_ion_total", "1.5 * int(pressure_ion_total) dV"),
        ):
            if node_name is None:
                func = (lambda p: self.volume_integral(
                    p, p.electrons.pressure_thermal))
            elif node_name == "pressure_thermal":
                def func(p):
                    total = self.volume_integral(p, p.pressure_thermal)
                    if total is not None:
                        return total
                    electrons = self.volume_integral(
                        p, p.electrons.pressure_thermal)
                    ions = self.volume_integral(p, p.pressure_ion_total)
                    if electrons is None or ions is None:
                        return None
                    return electrons + ions
            else:
                func = (lambda p, n=node_name: self.volume_integral(
                    p, getattr(p, n)))
            values = self.cp_profile_trace(func)
            if values is not None:
                self.set(path, 1.5 * values, "derived: %s (%s)" % (label, src))

        # DD: global_quantities.energy_total is W_mhd (volume integral of the
        # total kinetic pressure) -- use the equilibrium's energy_mhd trace
        # when the equilibrium provides it; fall back to energy_thermal only
        # when energy_mhd is absent.
        energy_mhd = self.summary_value("global_quantities.energy_mhd")
        if energy_mhd is not None:
            self.set("global_quantities.energy_total", energy_mhd,
                     "%s energy_mhd" % self.eq_src)
        else:
            energy_thermal = self.summary_value("global_quantities.energy_thermal")
            if energy_thermal is not None:
                self.set("global_quantities.energy_total", energy_thermal,
                         "derived: thermal only (%s)" % src)

        # volume averages
        t_e = self.cp_global_trace(gq.t_e_volume_average)
        if t_e is None:
            t_e = self.cp_profile_trace(
                lambda p: self.volume_average(p, p.electrons.temperature))
        if t_e is not None:
            self.set("volume_average.t_e", t_e, src)
        n_e = self.cp_global_trace(gq.n_e_volume_average)
        if n_e is None:
            n_e = self.cp_profile_trace(
                lambda p: self.volume_average(p, p.electrons.density))
        if n_e is not None:
            self.set("volume_average.n_e", n_e, src)
        for path, node_name in (("volume_average.t_i_average", "t_i_average"),
                                ("volume_average.zeff", "zeff")):
            values = self.cp_profile_trace(
                lambda p, n=node_name: self.volume_average(p, getattr(p, n)))
            if values is not None:
                self.set(path, values, src)

        self._fill_ion_densities(src)
        self._fill_local_axis(src)
        self._fill_line_average(src)

    def summary_value(self, path):
        node = self.s
        for part in path.split("."):
            node = getattr(node, part)
        if has(node.value):
            return arr(node.value)
        return None

    def _ion_species(self):
        """[(summary sub-structure name, index in the ion AoS)] for known ions."""
        if self.cp is None or len(self.cp.profiles_1d) == 0:
            return []
        species = []
        for index, ion in enumerate(self.cp.profiles_1d[0].ion):
            name = str(ion.name).strip() if has(ion.name) else ""
            target = ION_NAME_TO_SUMMARY.get(name.upper())
            if target is None and len(ion.element) > 0:
                try:
                    z_n = int(round(float(ion.element[0].z_n)))
                    a = float(ion.element[0].a)
                except Exception:
                    z_n, a = None, None
                if z_n == 1 and a is not None:
                    target = {1: "hydrogen", 2: "deuterium",
                              3: "tritium"}.get(int(round(a)))
                elif z_n == 2 and a is not None:
                    target = "helium_3" if int(round(a)) == 3 else "helium_4"
                elif z_n is not None:
                    target = ION_Z_TO_SUMMARY.get(z_n)
            if target is None:
                LOGGER.warning("ion %r not mapped to a summary species, skipped",
                               name)
                continue
            species.append((target, index))
        return species

    def _fill_ion_densities(self, src):
        cp = self.cp
        gq = cp.global_quantities
        totals = None
        for target, index in self._ion_species():
            values = None
            if index < len(gq.ion):
                values = self.cp_global_trace(gq.ion[index].n_i_volume_average)
            if values is None:
                values = self.cp_profile_trace(
                    lambda p, i=index: self.volume_average(p, p.ion[i].density))
            if values is None:
                continue
            self.set("volume_average.n_i.%s" % target, values, src)
            totals = values if totals is None else totals + values
        if totals is not None:
            self.set("volume_average.n_i_total", totals,
                     "derived: sum over ion species (%s)" % src)

    def _fill_local_axis(self, src):
        for path, getter in (
                ("local.magnetic_axis.t_e",
                 lambda p: float(arr(p.electrons.temperature)[0])),
                ("local.magnetic_axis.n_e",
                 lambda p: float(arr(p.electrons.density)[0])),
                ("local.magnetic_axis.t_i_average",
                 lambda p: float(arr(p.t_i_average)[0])),
                ("local.magnetic_axis.zeff", lambda p: float(arr(p.zeff)[0])),
                ("local.magnetic_axis.q", lambda p: float(arr(p.q)[0])),
        ):
            values = self.cp_profile_trace(getter)
            if values is not None:
                self.set(path, values, src)

    def _midplane_chord_density(self, profile, eq_slice):
        """Chord-averaged n_e along the outboard/inboard midplane radius."""
        p1 = eq_slice.profiles_1d
        if not (has(p1.r_inboard) and has(p1.r_outboard)):
            return None
        r_inboard, r_outboard = arr(p1.r_inboard), arr(p1.r_outboard)
        if has(p1.rho_tor_norm):
            rho_eq = arr(p1.rho_tor_norm)
        elif has(p1.psi):
            psi = arr(p1.psi)
            span = psi[-1] - psi[0]
            if span == 0:
                return None
            rho_eq = np.sqrt(np.clip((psi - psi[0]) / span, 0.0, 1.0))
        else:
            return None
        if not (rho_eq.size == r_inboard.size == r_outboard.size) or rho_eq.size < 2:
            return None
        if not (has(profile.grid.rho_tor_norm) and has(profile.electrons.density)):
            return None
        rho_cp = arr(profile.grid.rho_tor_norm)
        n_e_cp = arr(profile.electrons.density)
        # Chord from the inboard edge to the outboard edge, through the axis.
        radius = np.concatenate((r_inboard[::-1], r_outboard[1:]))
        rho_chord = np.concatenate((rho_eq[::-1], rho_eq[1:]))
        order = np.argsort(radius)
        radius, rho_chord = radius[order], rho_chord[order]
        length = radius[-1] - radius[0]
        if length <= 0:
            return None
        n_e_chord = np.interp(rho_chord, rho_cp, n_e_cp)
        return float(trapz(n_e_chord, radius) / length)

    def _fill_line_average(self, src):
        if self.eq is None or self.cp is None:
            return
        slices = list(self.eq.time_slice)
        profiles = list(self.cp.profiles_1d)
        if len(slices) != len(profiles):
            LOGGER.info("line_average.n_e skipped: %d equilibrium slices vs %d "
                        "core_profiles slices", len(slices), len(profiles))
            return
        values = []
        for profile, slice_ in zip(profiles, slices):
            value = self._midplane_chord_density(profile, slice_)
            if value is None:
                LOGGER.info("line_average.n_e skipped: midplane mapping "
                            "unavailable")
                return
            values.append(value)
        self.set("line_average.n_e", np.asarray(values),
                 "derived: midplane chord average (%s, %s)" % (src, self.eq_src))

    # -- core_sources ------------------------------------------------------
    def source_power(self, index):
        """Total power of the core_sources entries with this identifier index."""
        if self.cs is None:
            return None
        total = None
        for source in self.cs.source:
            try:
                if int(source.identifier.index) != index:
                    continue
            except Exception:
                continue
            times, powers = [], []
            for slice_ in source.global_quantities:
                if not has(slice_.power):
                    continue
                times.append(float(slice_.time))
                powers.append(float(slice_.power))
            if len(powers) < 2:
                continue
            values = self.to_summary_time(times, powers)
            if values is None:
                continue
            total = values if total is None else total + values
        return total

    def fill_from_core_sources(self):
        if self.cs is None:
            return
        src = self.cs_src

        ohmic = self.source_power(SRC_OHMIC)
        if ohmic is not None:
            self.set("global_quantities.power_ohm", ohmic, src)

        # Radiation: prefer the total radiation source; the components are only
        # summed when no total is stored, to avoid counting them twice.
        radiated = self.source_power(SRC_RADIATION_TOTAL)
        radiated_src = "derived: |radiation| (%s)" % src
        if radiated is None:
            parts = [self.source_power(i) for i in SRC_RADIATION_PARTS]
            parts = [p for p in parts if p is not None]
            if parts:
                radiated = np.sum(parts, axis=0)
                radiated_src = "derived: |sum of radiation components| (%s)" % src
        if radiated is not None:
            self.set("global_quantities.power_radiated", np.abs(radiated),
                     radiated_src)

        # Heating and current drive
        heating = []
        per_system = set()
        for system, (index, path) in HCD_SYSTEMS.items():
            values = self.source_power(index)
            if values is None:
                continue
            self.set(path, values, src)
            heating.append(values)
            per_system.add(system)
        additional_src = "derived: sum of ec/nbi/ic/lh (%s)" % src
        auxiliary = None
        if not heating:
            # The scenario inputs may only carry an aggregated auxiliary source.
            auxiliary = self.source_power(SRC_AUXILIARY)
            if auxiliary is not None:
                heating = [auxiliary]
                additional_src = "derived: auxiliary source (%s)" % src
        if heating:
            self.set("heating_current_drive.power_additional",
                     np.sum(heating, axis=0), additional_src)

        # The aggregated auxiliary source has no heating system of its own; when
        # the caller says which system the workflow means by it, its power is
        # also written as that system's power, so that the heating appears where
        # the consumers of the summary and of the pulse_schedule look for it.
        # power_additional is left as computed above (the same power, once).
        system = self.auxiliary_heating
        if system is not None and system not in per_system:
            if auxiliary is None:
                auxiliary = self.source_power(SRC_AUXILIARY)
            if auxiliary is None:
                LOGGER.info("auxiliary heating attributed to %s: no auxiliary "
                            "source (identifier %d) in %s", system,
                            SRC_AUXILIARY, src)
            else:
                path = HCD_SYSTEMS[system][1]
                self.set(path, auxiliary,
                         AUXILIARY_ATTRIBUTED % (SRC_AUXILIARY, system, system))
                LOGGER.info("auxiliary power (identifier %d) attributed to %s: "
                            "%s filled", SRC_AUXILIARY, system, path)

        fusion = self.source_power(SRC_FUSION)
        if fusion is not None:
            self.set("fusion.power", fusion, src)

    # -- confinement -------------------------------------------------------
    def heating_power(self):
        parts = []
        for path in ("global_quantities.power_ohm",
                     "heating_current_drive.power_additional",
                     "fusion.power"):
            values = self.summary_value(path)
            if values is not None:
                parts.append(values)
        if not parts:
            return None
        return np.sum(parts, axis=0)

    def mean_ion_mass(self):
        """Density-weighted mean ion mass over the core_profiles species."""
        if self.cp is None or len(self.cp.profiles_1d) == 0:
            return None
        weighted, weight = 0.0, 0.0
        gq = self.cp.global_quantities
        for index, ion in enumerate(self.cp.profiles_1d[0].ion):
            if len(ion.element) == 0 or not has(ion.element[0].a):
                continue
            a = float(ion.element[0].a)
            density = None
            if index < len(gq.ion) and has(gq.ion[index].n_i_volume_average):
                values = arr(gq.ion[index].n_i_volume_average)
                if values.size:
                    density = float(np.mean(values))
            if density is None and has(ion.density):
                density = float(np.mean(arr(ion.density)))
            if density is None or density <= 0:
                continue
            weighted += a * density
            weight += density
        return weighted / weight if weight > 0 else None

    def fill_confinement(self):
        energy = self.summary_value("global_quantities.energy_thermal")
        power = self.heating_power()
        if energy is None or power is None:
            return

        # dW_th/dt on the summary time base, for the energy balance loss power.
        dw_dt = np.gradient(energy, self.t)
        self.set("global_quantities.denergy_thermal_dt", dw_dt,
                 "derived: d/dt of energy_thermal")

        loss_power = power - dw_dt
        positive = loss_power > 0
        if not np.any(positive):
            return
        tau = np.where(positive, energy / np.where(positive, loss_power, 1.0), 0.0)
        self.set("global_quantities.tau_energy", tau,
                 "derived: energy_thermal / (ohmic + additional + fusion power "
                 "- dW_th/dt); 0 where that loss power is not positive")

        plasma_current = self.summary_value("global_quantities.ip")
        b0 = self.summary_value("global_quantities.b0")
        r0 = None
        if has(self.s.global_quantities.r0.value):
            r0 = float(self.s.global_quantities.r0.value)
        minor_radius = self.summary_value("boundary.minor_radius")
        # Area elongation kappa_a = S / (pi a^2) when the equilibrium provides
        # the plasma cross-section area; otherwise fall back to the boundary
        # (geometric) elongation.
        area = self._eq_area
        if area is not None and minor_radius is not None:
            elongation = area / (np.pi * minor_radius ** 2)
            elongation_label = "kappa_a = area / (pi * minor_radius^2)"
        else:
            elongation = self.summary_value("boundary.elongation")
            elongation_label = "boundary.elongation"
        density = self.summary_value("line_average.n_e")
        density_label = "line-average"
        if density is None:
            density = self.summary_value("volume_average.n_e")
            density_label = "volume-average"
        mass = self.mean_ion_mass()
        mass_label = "core_profiles ions"
        if mass is None:
            mass, mass_label = 2.5, "default 2.5"

        if all(x is not None for x in (plasma_current, b0, elongation,
                                       minor_radius, density)) and r0:
            ip_ma = np.abs(plasma_current) / 1e6
            b0_t = np.abs(b0)
            n19 = density / 1e19
            p_mw = np.where(positive, loss_power / 1e6, 1.0)
            tau98 = (0.0562 * ip_ma ** 0.93 * b0_t ** 0.15 * n19 ** 0.41
                     * p_mw ** -0.69 * r0 ** 1.97 * elongation ** 0.78
                     * (minor_radius / r0) ** 0.58 * mass ** 0.19)
            good = positive & (tau98 > 0)
            if np.any(good):
                h98 = np.where(good, tau / np.where(good, tau98, 1.0), 0.0)
                self.set("global_quantities.tau_energy_98",
                         np.where(good, tau98, 0.0),
                         "derived: IPB98(y,2) with %s density, %s mean ion "
                         "mass, %s" % (density_label, mass_label,
                                       elongation_label))
                self.set("global_quantities.h_98", h98,
                         "derived: tau_energy / IPB98(y,2)")

        line_density = self.summary_value("line_average.n_e")
        if line_density is not None and plasma_current is not None \
                and minor_radius is not None:
            ip_ma = np.abs(plasma_current) / 1e6
            greenwald = ip_ma / (np.pi * minor_radius ** 2) * 1e20
            good = greenwald > 0
            if np.any(good):
                self.set("global_quantities.greenwald_fraction",
                         np.where(good, line_density
                                  / np.where(good, greenwald, 1.0), 0.0),
                         "derived: line_average.n_e / Greenwald density")


def build_summary(factory, collected, provenance, args, dd_version):
    """Assemble the summary IDS on the equilibrium time base."""
    equilibrium = collected.get("equilibrium")
    if equilibrium is None:
        LOGGER.warning("no equilibrium IDS collected: summary not built")
        return None, []

    if int(equilibrium.ids_properties.homogeneous_time) == 1 \
            and has(equilibrium.time):
        times = arr(equilibrium.time)
    else:
        times = np.asarray([float(s.time) for s in equilibrium.time_slice])
    if times.size == 0:
        LOGGER.warning("equilibrium has no time base: summary not built")
        return None, []

    summary = factory.summary()
    summary.ids_properties.homogeneous_time = 1
    summary.time = times

    builder = SummaryBuilder(summary, times, equilibrium,
                             collected.get("core_profiles"),
                             collected.get("core_sources"),
                             auxiliary_heating=getattr(
                                 args, "auxiliary_heating", "none"))
    builder.fill_from_equilibrium()
    builder.fill_from_core_profiles()
    builder.fill_from_core_sources()
    builder.fill_confinement()

    lines = ["%s from %s" % (name, uri) for name, uri in sorted(provenance.items())]
    auto_comment = "PDS export: " + "; ".join(lines)
    comment = args.comment.strip() if args.comment else ""
    summary.ids_properties.comment = (comment + " | " + auto_comment
                                      if comment else auto_comment)
    summary.ids_properties.provider = args.provider
    summary.ids_properties.creation_date = utc_now()
    summary.code.name = "pds_imas_export"
    version = git_short_hash(os.environ.get("PDS_REPO", ""))
    if version:
        summary.code.version = version
    summary.code.repository = "https://github.com/iterorganization/IMAS-PDS"
    return summary, builder.filled


# --------------------------------------------------------------------------
# pulse_schedule building blocks
# --------------------------------------------------------------------------
# The PDS is a pulse design simulator: the converged trajectories a run
# produces (plasma current, toroidal field, boundary shape, coil currents,
# densities, heating) ARE the pulse schedule that was designed.  They are
# therefore re-exported as the reference waveforms of a pulse_schedule IDS,
# on the time base of the summary, so that a pulse design can be handed over
# to the pulse schedule consumers without a separate translation step.

# Number of points of the resampled boundary outline: the equilibrium code
# writes a different number of contour points at every time slice, the
# pulse_schedule needs one reference waveform per (fixed) point.
OUTLINE_POINTS = 96

# DD 4.0.0, pulse_schedule .../reference_type: "0:relative (don't use for the
# moment, to be defined later when segments are introduced in the IDS
# structure); 1: absolute: the reference time trace is provided in the
# reference/data node".  Everything written here is an absolute waveform.
REFERENCE_ABSOLUTE = 1
# DD 4.0.0, pulse_schedule .../envelope_type: "0:relative: means that the
# envelope upper and lower bound values are defined respectively as
# reference.data * reference.data_error_upper and reference.data *
# reference.data_error_lower. 1: absolute: [...] given respectively by
# reference/data_error_upper and reference/data_error_lower".  The DD has no
# dedicated "no envelope" value; no error bar is written here, so no envelope
# is defined and the neutral 0 is used.
ENVELOPE_NONE = 0

# DD 4.0.0, equilibrium/time_slice/contour_tree/node/critical_type:
# "0-minimum, 1-saddle, 2-maximum".  An X point is a saddle point of psi.
CRITICAL_TYPE_SADDLE = 1


def resample_closed_outline(r, z, n_points=OUTLINE_POINTS):
    """``n_points`` samples of a closed (R, Z) contour, equal in arc length.

    Returns ``(r, z)`` arrays of ``n_points`` elements, or None when the
    contour is unusable.  The last point is dropped when it repeats the first,
    the contour is closed explicitly and sampled at ``n_points`` equally
    spaced cumulative arc lengths (the closing point itself excluded, so the
    samples are distinct).
    """
    r = np.asarray(r, dtype=float)
    z = np.asarray(z, dtype=float)
    if r.size != z.size or r.size < 3 or not finite(r) or not finite(z):
        return None
    if np.isclose(r[0], r[-1]) and np.isclose(z[0], z[-1]):
        r, z = r[:-1], z[:-1]
        if r.size < 3:
            return None
    closed_r = np.concatenate([r, r[:1]])
    closed_z = np.concatenate([z, z[:1]])
    steps = np.hypot(np.diff(closed_r), np.diff(closed_z))
    length = np.concatenate([[0.0], np.cumsum(steps)])
    if length[-1] <= 0.0:
        return None
    target = np.linspace(0.0, length[-1], n_points, endpoint=False)
    return np.interp(target, length, closed_r), np.interp(target, length, closed_z)


class PulseScheduleBuilder:
    """Fills a pulse_schedule IDS with the design trajectories of the run."""

    def __init__(self, pulse_schedule, times, collected, summary, workflow):
        self.ps = pulse_schedule
        self.t = np.asarray(times, dtype=float)
        self.eq = collected.get("equilibrium")
        self.cp = collected.get("core_profiles")
        self.pf = collected.get("pf_active")
        self.filled = []
        # The summary builder is reused read-only, for its time helpers
        # (per-slice equilibrium traces, interpolation onto the summary time
        # base, summary look-up); nothing is written into the summary here.
        self.traces = SummaryBuilder(summary, times, self.eq, self.cp, None)
        self.tag = "PDS %s: " % workflow if workflow else "PDS: "
        self.eq_src = self.provenance(self.eq, "equilibrium")
        self.cp_src = self.provenance(self.cp, "core_profiles")
        self.pf_src = self.provenance(self.pf, "pf_active")
        self.sum_src = self.tag + "summary (pds_imas_export)"

    def provenance(self, ids, name):
        """"PDS <workflow>: <ids> (<code>)", the reference_name of a signal."""
        if ids is None:
            return ""
        code = code_name(ids, "")
        return self.tag + (("%s (%s)" % (name, code)) if code else name)

    # -- generic setter ----------------------------------------------------
    def signal(self, node, values, source, label):
        """Write one reference waveform; skip silently when unusable."""
        if values is None or not source:
            return False
        values = np.asarray(values, dtype=float)
        if values.size != self.t.size or not finite(values):
            return False
        node.reference = values
        node.reference_name = source
        node.reference_type = REFERENCE_ABSOLUTE
        node.envelope_type = ENVELOPE_NONE
        if label:
            self.filled.append(label)
        return True

    # -- traces ------------------------------------------------------------
    def equilibrium_time(self):
        if self.eq is None:
            return None
        if has(self.eq.time):
            return arr(self.eq.time)
        return np.asarray([float(s.time) for s in self.eq.time_slice])

    def eq_global(self, name):
        """Per-slice equilibrium global quantity on the summary time base."""
        return self.traces.eq_slice_trace(
            lambda s, n=name: float(getattr(s.global_quantities, n))
            if has(getattr(s.global_quantities, n)) else None)

    def cp_global(self, name):
        """core_profiles global quantity interpolated onto the summary time."""
        if self.cp is None:
            return None
        return self.traces.cp_global_trace(getattr(self.cp.global_quantities, name))

    def summary_trace(self, path):
        return self.traces.summary_value(path)

    # -- blocks ------------------------------------------------------------
    def fill_flux_control(self):
        flux = self.ps.flux_control
        # ip keeps the sign convention of the equilibrium (the COCOS of the
        # exported data), it is not re-oriented here.
        self.signal(flux.ip, self.eq_global("ip"), self.eq_src, "flux_control.ip")
        self.signal(flux.li_3, self.eq_global("li_3"), self.eq_src,
                    "flux_control.li_3")
        self.signal(flux.v_loop, self.cp_global("v_loop"), self.cp_src,
                    "flux_control.v_loop")
        self.signal(flux.beta_tor_norm, self.cp_global("beta_tor_norm"),
                    self.cp_src, "flux_control.beta_tor_norm")

    def fill_tf(self):
        """b_field_tor_vacuum_r = b0 * r0 (T.m) from the equilibrium."""
        if self.eq is None:
            return
        vacuum = self.eq.vacuum_toroidal_field
        if not has(vacuum.b0) or not has(vacuum.r0):
            return
        b0 = arr(vacuum.b0)
        if b0.size != self.t.size:
            b0 = self.traces.to_summary_time(self.equilibrium_time(), b0)
            if b0 is None:
                return
        self.signal(self.ps.tf.b_field_tor_vacuum_r, b0 * float(vacuum.r0),
                    self.eq_src, "tf.b_field_tor_vacuum_r")

    def fill_position_control(self):
        if self.eq is None:
            return
        position = self.ps.position_control
        for node, getter, label in (
                (position.geometric_axis.r,
                 lambda s: float(s.boundary.geometric_axis.r)
                 if has(s.boundary.geometric_axis.r) else None,
                 "position_control.geometric_axis.r"),
                (position.geometric_axis.z,
                 lambda s: float(s.boundary.geometric_axis.z)
                 if has(s.boundary.geometric_axis.z) else None,
                 "position_control.geometric_axis.z"),
                (position.minor_radius,
                 lambda s: float(s.boundary.minor_radius)
                 if has(s.boundary.minor_radius) else None,
                 "position_control.minor_radius"),
                (position.elongation,
                 lambda s: float(s.boundary.elongation)
                 if has(s.boundary.elongation) else None,
                 "position_control.elongation"),
                (position.triangularity,
                 lambda s: float(s.boundary.triangularity)
                 if has(s.boundary.triangularity) else None,
                 "position_control.triangularity"),
                (position.triangularity_upper,
                 lambda s: float(s.boundary.triangularity_upper)
                 if has(s.boundary.triangularity_upper) else None,
                 "position_control.triangularity_upper"),
                (position.triangularity_lower,
                 lambda s: float(s.boundary.triangularity_lower)
                 if has(s.boundary.triangularity_lower) else None,
                 "position_control.triangularity_lower"),
                (position.magnetic_axis.r,
                 lambda s: float(s.global_quantities.magnetic_axis.r)
                 if has(s.global_quantities.magnetic_axis.r) else None,
                 "position_control.magnetic_axis.r"),
                (position.magnetic_axis.z,
                 lambda s: float(s.global_quantities.magnetic_axis.z)
                 if has(s.global_quantities.magnetic_axis.z) else None,
                 "position_control.magnetic_axis.z"),
        ):
            self.signal(node, self.traces.eq_slice_trace(getter), self.eq_src,
                        label)
        self.fill_boundary_outline()
        self.fill_x_points()

    def fill_boundary_outline(self):
        """The plasma boundary, as one reference waveform per outline point.

        DD 4.0.0 stores the outline as an array of structures over the points
        (position_control/boundary_outline(i)), each holding a 1D reference
        over ``position_control/time`` for r and one for z -- the coordinate
        of the reference is the time, and the point index is the AoS index,
        so there is no 2D array to fill.  Every slice is resampled to the same
        OUTLINE_POINTS positions so that point i means the same thing at every
        time.
        """
        r_slices, z_slices = [], []
        for slice_ in self.eq.time_slice:
            outline = slice_.boundary.outline
            if not has(outline.r) or not has(outline.z):
                return
            sampled = resample_closed_outline(arr(outline.r), arr(outline.z))
            if sampled is None:
                return
            r_slices.append(sampled[0])
            z_slices.append(sampled[1])
        if len(r_slices) != self.t.size:
            return
        r_all = np.asarray(r_slices)          # (n_time, OUTLINE_POINTS)
        z_all = np.asarray(z_slices)
        if not finite(r_all) or not finite(z_all):
            return
        outlines = self.ps.position_control.boundary_outline
        outlines.resize(OUTLINE_POINTS)
        for k in range(OUTLINE_POINTS):
            self.signal(outlines[k].r, r_all[:, k], self.eq_src, None)
            self.signal(outlines[k].z, z_all[:, k], self.eq_src, None)
        self.filled.append("position_control.boundary_outline.r (%d points)"
                           % OUTLINE_POINTS)
        self.filled.append("position_control.boundary_outline.z (%d points)"
                           % OUTLINE_POINTS)

    def fill_x_points(self):
        """X points, taken from the saddle nodes of the equilibrium contour tree.

        DD 4.0.0 equilibrium/time_slice has neither boundary_separatrix nor
        boundary/x_point; the critical points are in contour_tree/node, where
        critical_type 1 (saddle) is an X point.  The block is skipped as soon
        as one slice has none, so that no waveform has to be padded.
        """
        per_slice = []
        for slice_ in self.eq.time_slice:
            try:
                nodes = slice_.contour_tree.node
            except Exception:
                return
            points = []
            for index in range(len(nodes)):
                node = nodes[index]
                if not has(node.critical_type) \
                        or int(node.critical_type) != CRITICAL_TYPE_SADDLE:
                    continue
                if has(node.r) and has(node.z):
                    points.append((float(node.r), float(node.z)))
            if not points:
                return
            per_slice.append(points)
        if len(per_slice) != self.t.size:
            return
        n_points = min(len(points) for points in per_slice)
        x_points = self.ps.position_control.x_point
        x_points.resize(n_points)
        for k in range(n_points):
            self.signal(x_points[k].r,
                        np.asarray([points[k][0] for points in per_slice]),
                        self.eq_src, "position_control.x_point[%d].r" % k)
            self.signal(x_points[k].z,
                        np.asarray([points[k][1] for points in per_slice]),
                        self.eq_src, "position_control.x_point[%d].z" % k)

    def fill_pf_active(self):
        """The designed coil currents, interpolated onto the summary time."""
        if self.pf is None:
            return
        traces = []
        for coil in self.pf.coil:
            if not has(coil.current.data):
                continue
            if has(coil.current.time):
                source_time = arr(coil.current.time)
            elif has(self.pf.time):
                source_time = arr(self.pf.time)
            else:
                continue
            values = self.traces.to_summary_time(source_time,
                                                 arr(coil.current.data))
            if values is None or not finite(values):
                continue
            traces.append((str(coil.name) if has(coil.name) else "", values))
        if not traces:
            return
        coils = self.ps.pf_active.coil
        coils.resize(len(traces))
        for k, (name, values) in enumerate(traces):
            if name:
                coils[k].name = name
            self.signal(coils[k].current, values, self.pf_src,
                        "pf_active.coil[%d].current (%s)" % (k, name or "?"))

    def fill_density_control(self):
        density = self.ps.density_control
        for node, path, label in (
                (density.n_e_line, "line_average.n_e",
                 "density_control.n_e_line"),
                (density.n_e_volume_average, "volume_average.n_e",
                 "density_control.n_e_volume_average"),
                (density.zeff, "volume_average.zeff", "density_control.zeff"),
        ):
            self.signal(node, self.summary_trace(path), self.sum_src, label)

    def fill_heating(self):
        # Whatever the summary holds as a system power becomes that system's
        # reference waveform -- including a power the summary builder attributed
        # to a system from the aggregated auxiliary source (--auxiliary-heating).
        for node, path, label in (
                (self.ps.ec.power_launched, HCD_SYSTEMS["ec"][1],
                 "ec.power_launched"),
                (self.ps.nbi.power, HCD_SYSTEMS["nbi"][1], "nbi.power"),
                (self.ps.ic.power, HCD_SYSTEMS["ic"][1], "ic.power"),
                (self.ps.lh.power, HCD_SYSTEMS["lh"][1], "lh.power"),
        ):
            self.signal(node, self.summary_trace(path), self.sum_src, label)


def build_pulse_schedule(factory, collected, summary, provenance, args, dd_version):
    """Assemble the pulse_schedule IDS from the converged design trajectories."""
    if summary is None:
        LOGGER.warning("no summary IDS: pulse_schedule not built")
        return None, []
    times = arr(summary.time)
    if times.size == 0:
        LOGGER.warning("summary has no time base: pulse_schedule not built")
        return None, []

    pulse_schedule = factory.pulse_schedule()
    pulse_schedule.ids_properties.homogeneous_time = 1
    # With homogeneous_time = 1 every dynamic node follows the root time, so
    # the per-block time arrays (flux_control/time, position_control/time,
    # pf_active/time, ...) are deliberately left empty.
    pulse_schedule.time = times

    builder = PulseScheduleBuilder(pulse_schedule, times, collected, summary,
                                   args.workflow)
    builder.fill_flux_control()
    builder.fill_tf()
    builder.fill_position_control()
    builder.fill_pf_active()
    builder.fill_density_control()
    builder.fill_heating()
    if not builder.filled:
        LOGGER.warning("no reference waveform could be derived: "
                       "pulse_schedule not built")
        return None, []

    sources = ["%s from %s" % (name, provenance.get(name, "?"))
               for name in ("equilibrium", "core_profiles", "pf_active")
               if name in collected]
    sources.append("summary built by pds_imas_export")
    pulse_schedule.ids_properties.comment = (
        "Pulse schedule derived by pds_imas_export from the PDS results (the "
        "converged design trajectories are exported as references); sources: "
        + "; ".join(sources))
    pulse_schedule.ids_properties.provider = args.provider
    pulse_schedule.ids_properties.creation_date = utc_now()
    pulse_schedule.code.name = "pds_imas_export"
    version = git_short_hash(os.environ.get("PDS_REPO", ""))
    if version:
        pulse_schedule.code.version = version
    pulse_schedule.code.repository = "https://github.com/iterorganization/IMAS-PDS"
    return pulse_schedule, builder.filled

def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")


def build_dataset_description(factory, args, times):
    dsd = factory.dataset_description()
    # dataset_description is a static IDS: the DD only accepts
    # IDS_TIME_MODE_INDEPENDENT (2) here.
    dsd.ids_properties.homogeneous_time = 2
    dsd.ids_properties.comment = args.comment or ""
    dsd.ids_properties.provider = args.provider
    dsd.ids_properties.creation_date = utc_now()
    dsd.uri = args.output
    if args.machine:
        dsd.machine = args.machine
    if args.shot is not None:
        dsd.pulse = int(args.shot)
    try:
        dsd.type.index = 2
        dsd.type.name = "simulation"
    except Exception:
        LOGGER.debug("dataset_description.type not settable in this DD version")
    if times is not None and len(times):
        dsd.simulation.time_begin = float(times[0])
        dsd.simulation.time_end = float(times[-1])
    if args.workflow:
        dsd.simulation.workflow = args.workflow
    if args.comment:
        dsd.simulation.comment_before = args.comment
    dsd.code.name = "pds_imas_export"
    version = git_short_hash(os.environ.get("PDS_REPO", ""))
    if version:
        dsd.code.version = version
    dsd.code.repository = "https://github.com/iterorganization/IMAS-PDS"
    return dsd


def tag_provenance(ids, source_uri):
    """Record the origin of an IDS in ids_properties.provenance (best effort)."""
    try:
        ids.ids_properties.provenance.node.resize(1)
        ids.ids_properties.provenance.node[0].path = ""
        ids.ids_properties.provenance.node[0].reference.resize(1)
        ids.ids_properties.provenance.node[0].reference[0].name = source_uri
    except Exception as exc:
        LOGGER.debug("provenance not recorded for %s: %s", ids.metadata.name, exc)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Build one IMAS data entry (with a summary IDS) from a PDS run.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--output", required=True,
                        help="output data entry URI, opened in write mode")
    parser.add_argument("--equilibrium",
                        help="data entry of the equilibrium code; its equilibrium "
                             "IDS is the equilibrium of the export")
    parser.add_argument("--core-profiles", dest="core_profiles",
                        help="data entry of the transport code; its core_profiles "
                             "IDS is the core_profiles of the export")
    parser.add_argument("--extra", nargs="+", default=[],
                        help="further data entries, scanned in order (machine "
                             "description first, then scenario inputs)")
    parser.add_argument("--dd-version", dest="dd_version", default="4.0.0",
                        help="data dictionary version of the output")
    parser.add_argument("--machine", default="ITER")
    parser.add_argument("--shot", type=int)
    parser.add_argument("--workflow", default="")
    parser.add_argument("--comment", default="")
    parser.add_argument("--provider",
                        default=os.environ.get("USER") or getpass.getuser())
    parser.add_argument("--equilibrium-2d", dest="equilibrium_2d",
                        choices=("auto", "off"), default="auto",
                        help="auto: rebuild equilibrium/time_slice/profiles_2d "
                             "on a rectangular (R,Z) grid from the GGD node "
                             "values for every slice that has none (psi, phi, "
                             "j_phi interpolated, B_r/B_z from grad psi, "
                             "B_phi from f(psi)/R); off: leave the equilibrium "
                             "as the equilibrium code wrote it")
    parser.add_argument("--pulse-schedule", dest="pulse_schedule",
                        choices=("auto", "off"), default="auto",
                        help="auto: derive a pulse_schedule IDS from the "
                             "converged PDS trajectories (equilibrium, "
                             "core_profiles, pf_active and the summary just "
                             "built), on the summary time base, unless a "
                             "source entry already provides a pulse_schedule "
                             "-- the PDS designs the pulse, so its results are "
                             "the schedule; off: do not derive it (a "
                             "pulse_schedule found in a source entry is still "
                             "copied)")
    parser.add_argument("--auxiliary-heating", dest="auxiliary_heating",
                        choices=("none", "ec", "nbi", "ic", "lh"),
                        default="none",
                        help="system to which the aggregated 'auxiliary' "
                             "core_sources power (identifier 100) is attributed "
                             "when the input carries no per-system power; the "
                             "PDS post-processing sets it from the waveform-"
                             "editor configuration")
    parser.add_argument("--no-summary", dest="no_summary", action="store_true",
                        help="skip the summary IDS (and therefore the derived "
                             "pulse_schedule, which is built on its time base)")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)-7s %(message)s")

    factory = imas.IDSFactory(args.dd_version)
    collected, provenance, entries = collect(args, factory)
    if not collected:
        raise RuntimeError("no IDS found in the given data entries")

    LOGGER.info("provenance table:")
    for name in sorted(provenance):
        LOGGER.info("  %-22s %s", name, provenance[name])

    # Done before anything is written and before the summary is built, so that
    # the summary sees the psi_axis completed here.
    if args.equilibrium_2d != "off" and "equilibrium" in collected:
        add_profiles_2d(collected["equilibrium"], collected.get("wall"))

    report = []
    # An IDS a source entry left inconsistent (a profile without its coordinate,
    # say) is refused by the AL validation on put. That is one IDS worth of data
    # lost, not a reason to lose the whole export, so it is skipped with a loud
    # warning and reported at the end.
    skipped = []
    output = imas.DBEntry(args.output, "w", dd_version=args.dd_version)
    try:
        for name in sorted(collected):
            ids = collected[name]
            stored = ids_dd_version(ids)
            if stored != args.dd_version:
                LOGGER.info("converting %s from DD %s to %s", name, stored,
                            args.dd_version)
                ids = imas.convert_ids(ids, args.dd_version)
                collected[name] = ids
            tag_provenance(ids, provenance[name])
            try:
                output.put(ids)
            except Exception as exc:
                LOGGER.error("%s from %s could not be written and is left out "
                             "of the export: %s", name, provenance[name], exc)
                skipped.append((name, provenance[name], str(exc)))
                continue
            report.append((name, provenance[name], args.dd_version,
                           n_time_points(ids)))

        summary_filled = []
        pulse_filled = []
        summary = None
        times = None
        if not args.no_summary:
            summary, summary_filled = build_summary(
                factory, collected, provenance, args, args.dd_version)
            if summary is not None:
                times = arr(summary.time)
                output.put(summary)
                report.append(("summary", "built by pds_imas_export",
                               args.dd_version, int(times.size)))

        # Role rule: a pulse_schedule produced by a code wins over a derived
        # one, and is simply copied above with the other collected IDSs.
        if args.pulse_schedule == "off":
            LOGGER.info("pulse_schedule derivation disabled (--pulse-schedule off)")
        elif "pulse_schedule" in collected:
            LOGGER.info("pulse_schedule taken from %s: not derived",
                        provenance["pulse_schedule"])
        elif summary is None:
            LOGGER.info("no summary IDS: pulse_schedule not derived")
        else:
            pulse_schedule, pulse_filled = build_pulse_schedule(
                factory, collected, summary, provenance, args, args.dd_version)
            if pulse_schedule is not None:
                try:
                    output.put(pulse_schedule)
                except Exception as exc:
                    LOGGER.error("the derived pulse_schedule could not be "
                                 "written and is left out of the export: %s", exc)
                    pulse_filled = []
                    skipped.append(("pulse_schedule", "built by pds_imas_export",
                                    str(exc)))
                else:
                    report.append(("pulse_schedule", "built by pds_imas_export",
                                   args.dd_version, n_time_points(pulse_schedule)))
        if times is None and "equilibrium" in collected:
            equilibrium = collected["equilibrium"]
            times = (arr(equilibrium.time) if has(equilibrium.time)
                     else np.asarray([float(s.time)
                                      for s in equilibrium.time_slice]))

        dsd = build_dataset_description(factory, args, times)
        output.put(dsd)
        report.append(("dataset_description", "built by pds_imas_export",
                       args.dd_version, 0))
    finally:
        output.close()
        for entry in entries:
            try:
                entry.close()
            except Exception:
                pass

    print()
    print("=" * 78)
    print("IMAS export report -- %s" % args.output)
    print("=" * 78)
    print("%-22s %-11s %6s  %s" % ("IDS", "DD", "ntime", "source"))
    for name, source, dd_version, ntime in report:
        print("%-22s %-11s %6d  %s" % (name, dd_version, ntime, source))
    if skipped:
        print()
        print("IDSs left out (rejected on write, see the log above):")
        for name, source, message in skipped:
            print("  %-22s %s" % (name, source))
            print("  %-22s %s" % ("", message))
    if summary_filled:
        print()
        print("summary quantities filled (%d):" % len(summary_filled))
        for path in summary_filled:
            print("  %s" % path)
    elif not args.no_summary:
        print()
        print("summary: no quantity could be filled")
    if pulse_filled:
        print()
        print("pulse_schedule references filled (%d):" % len(pulse_filled))
        for path in pulse_filled:
            print("  %s" % path)
    print("=" * 78)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - report and fail the shell step
        LOGGER.error("IMAS export failed: %s", exc, exc_info=True)
        sys.exit(1)
