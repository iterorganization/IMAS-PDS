"""Compute classes producing the waveforms of a pulse schedule.

Two sources are supported and both return exactly the same dictionary, so the
view layer never has to know where the waveforms came from:

* :class:`PulseScheduleCompute` reads a ``pulse_schedule`` IDS -- the references
  (the *demand* waveforms) a PDS run exports;
* :class:`WaveformsFromIdsCompute` derives the same quantities from the physics
  IDSs of a data entry (``equilibrium``, ``pf_active``, ``core_sources``,
  ``core_profiles``).  This is how a scenario input entry, which usually has no
  ``pulse_schedule``, can be overlaid on the pulse schedule a run produced.

Dictionary returned by ``get_waveforms()``
------------------------------------------

======================================  =========================================
key                                     content
======================================  =========================================
``time``                                root time base, shape ``(nt,)``
``time_<block>``                        time base of one block (``flux_control``,
                                        ``tf``, ``position_control``,
                                        ``pf_active``, ``density_control``,
                                        ``ec``, ``nbi``, ``ic``, ``lh``); equal to
                                        ``time`` unless ``homogeneous_time`` is 0
``ip`` ``v_loop`` ``li_3``              flux control waveforms, ``(nt,)``
``beta_tor_norm``
``b0_r0``                               vacuum ``B0.R0`` [T.m], ``(nt,)``
``geometric_axis_r/z``                  position control waveforms, ``(nt,)``
``magnetic_axis_r/z``
``minor_radius`` ``elongation``
``triangularity``
``triangularity_upper/lower``
``boundary_outline_r/z``                boundary points, ``(n_points, nt)``
``x_point_r/z``                         X points, ``(n_x_point, nt)``
``coil_names`` ``coil_names_full``      list of ``n_coil`` strings
``coil_currents`` ``coil_voltages``     ``(n_coil, nt)``; voltages may be empty
``n_e_line`` ``n_e_volume_average``     density control waveforms, ``(nt,)``
``zeff``
``p_ec`` ``p_nbi`` ``p_ic`` ``p_lh``    launched powers [W], ``(nt,)``
``p_ohmic``
``missing``                             list of the references that were absent
``info``                                dictionary of provenance strings
======================================  =========================================
"""

import logging

import numpy as np

from .common import (
    clean,
    get_0d_over_time,
    get_1d,
    get_reference,
    has_data,
    nan_array,
    node_at,
    short_coil_name,
    stack_ragged,
)

logger = logging.getLogger("module")

#: Blocks of pulse_schedule that carry their own time base.
TIME_BLOCKS = ("flux_control", "tf", "position_control", "pf_active",
               "density_control", "ec", "nbi", "ic", "lh")

#: ``core_sources`` identifier indices of the heating and current drive systems.
SOURCE_INDEX = {"p_ec": 3, "p_nbi": 2, "p_ic": 5, "p_lh": 4, "p_ohmic": 7}


def empty_waveforms(ntime=0):
    """A fully NaN waveform dictionary, used as the starting point of both classes."""
    waveforms = {"time": nan_array(ntime)}
    for block in TIME_BLOCKS:
        waveforms["time_" + block] = waveforms["time"]
    for key in ("ip", "v_loop", "li_3", "beta_tor_norm", "b0_r0",
                "geometric_axis_r", "geometric_axis_z",
                "magnetic_axis_r", "magnetic_axis_z",
                "minor_radius", "elongation", "triangularity",
                "triangularity_upper", "triangularity_lower",
                "n_e_line", "n_e_volume_average", "zeff",
                "p_ec", "p_nbi", "p_ic", "p_lh", "p_ohmic"):
        waveforms[key] = nan_array(ntime)
    for key in ("boundary_outline_r", "boundary_outline_z",
                "x_point_r", "x_point_z", "coil_currents", "coil_voltages"):
        waveforms[key] = np.zeros((0, 0), dtype=float)
    waveforms["coil_names"] = []
    waveforms["coil_names_full"] = []
    waveforms["missing"] = []
    waveforms["info"] = {}
    return waveforms


class PulseScheduleCompute:
    """Waveforms of a ``pulse_schedule`` IDS.

    Attributes:
        ids: the ``pulse_schedule`` IDS.
    """

    def __init__(self, ids):
        self.ids = ids

    def _block_time(self, block, root_time, homogeneous):
        """Time base of one block: its own when ``homogeneous_time`` is 0."""
        if homogeneous != 0:
            return root_time
        node = node_at(self.ids, block + ".time")
        if node is None:
            return root_time
        values = np.asarray(node)
        if values.size < 1:
            return root_time
        return clean(values)

    def get_waveforms(self):
        """Read every reference of the IDS into the common dictionary."""
        ids = self.ids
        root_time = clean(np.asarray(ids.time)) if len(ids.time) else np.array([])
        ntime = root_time.size
        waveforms = empty_waveforms(ntime)
        waveforms["time"] = root_time
        missing = waveforms["missing"]

        try:
            homogeneous = int(ids.ids_properties.homogeneous_time)
        except Exception:
            homogeneous = 1
        for block in TIME_BLOCKS:
            waveforms["time_" + block] = self._block_time(block, root_time,
                                                          homogeneous)

        # -- flux control ------------------------------------------------
        nt = waveforms["time_flux_control"].size or ntime
        for key, path in (("ip", "flux_control.ip"),
                          ("li_3", "flux_control.li_3"),
                          ("v_loop", "flux_control.v_loop"),
                          ("beta_tor_norm", "flux_control.beta_tor_norm")):
            waveforms[key] = get_reference(ids, path, nt, missing,
                                           "pulse_schedule." + path + ".reference")

        # -- toroidal field ----------------------------------------------
        nt = waveforms["time_tf"].size or ntime
        waveforms["b0_r0"] = get_reference(
            ids, "tf.b_field_tor_vacuum_r", nt, missing,
            "pulse_schedule.tf.b_field_tor_vacuum_r.reference")

        # -- position control --------------------------------------------
        nt = waveforms["time_position_control"].size or ntime
        for key, path in (("geometric_axis_r", "position_control.geometric_axis.r"),
                          ("geometric_axis_z", "position_control.geometric_axis.z"),
                          ("magnetic_axis_r", "position_control.magnetic_axis.r"),
                          ("magnetic_axis_z", "position_control.magnetic_axis.z"),
                          ("minor_radius", "position_control.minor_radius"),
                          ("elongation", "position_control.elongation"),
                          ("triangularity", "position_control.triangularity"),
                          ("triangularity_upper",
                           "position_control.triangularity_upper"),
                          ("triangularity_lower",
                           "position_control.triangularity_lower")):
            waveforms[key] = get_reference(ids, path, nt, missing,
                                           "pulse_schedule." + path + ".reference")

        waveforms["boundary_outline_r"], waveforms["boundary_outline_z"] = \
            self._points("position_control.boundary_outline", nt, missing)
        waveforms["x_point_r"], waveforms["x_point_z"] = \
            self._points("position_control.x_point", nt, missing, critical=False)

        # -- poloidal field coils ----------------------------------------
        nt = waveforms["time_pf_active"].size or ntime
        coils = node_at(ids, "pf_active.coil")
        names, currents = [], []
        if coils is not None and len(coils):
            for index in range(len(coils)):
                coil = coils[index]
                names.append(str(coil.name))
                currents.append(get_reference(
                    coil, "current", nt, missing,
                    "pulse_schedule.pf_active.coil[%d].current.reference" % index))
        else:
            logger.critical("pulse_schedule.pf_active.coil could not be read")
            missing.append("pulse_schedule.pf_active.coil")
        waveforms["coil_names_full"] = names
        waveforms["coil_names"] = [short_coil_name(name) for name in names]
        waveforms["coil_currents"] = (np.vstack(currents) if currents
                                      else np.zeros((0, 0), dtype=float))
        # pulse_schedule has no coil voltage reference; the view fills them in
        # from the pf_active IDS of the same entry when there is one.
        waveforms["coil_voltages"] = np.zeros((0, 0), dtype=float)

        # -- density control ---------------------------------------------
        nt = waveforms["time_density_control"].size or ntime
        for key, path in (("n_e_line", "density_control.n_e_line"),
                          ("n_e_volume_average",
                           "density_control.n_e_volume_average"),
                          ("zeff", "density_control.zeff")):
            waveforms[key] = get_reference(ids, path, nt, missing,
                                           "pulse_schedule." + path + ".reference")

        # -- heating and current drive ------------------------------------
        # An empty heating reference means that the system is not activated in
        # this scenario, which is a normal state and not a missing reference: it
        # is neither reported as an error nor listed in "missing".
        for key, path in (("p_ec", "ec.power_launched"),
                          ("p_nbi", "nbi.power"),
                          ("p_ic", "ic.power"),
                          ("p_lh", "lh.power")):
            block = path.split(".")[0]
            nt = waveforms["time_" + block].size or ntime
            waveforms[key] = get_reference(
                ids, path, nt, None,
                "pulse_schedule." + path + ".reference", critical=False)

        waveforms["info"] = self._info(waveforms)
        return waveforms

    def _points(self, path, ntime, missing, critical=True):
        """``(r, z)`` arrays of shape ``(n_points, ntime)`` for an AoS of points."""
        nodes = node_at(self.ids, path)
        if nodes is None or not len(nodes):
            if critical:
                logger.critical("pulse_schedule.%s could not be read", path)
                missing.append("pulse_schedule." + path)
            else:
                logger.info("pulse_schedule.%s is empty", path)
            return np.zeros((0, 0), dtype=float), np.zeros((0, 0), dtype=float)
        rows_r, rows_z = [], []
        for index in range(len(nodes)):
            point = nodes[index]
            rows_r.append(get_reference(point, "r", ntime))
            rows_z.append(get_reference(point, "z", ntime))
        return np.vstack(rows_r), np.vstack(rows_z)

    def _info(self, waveforms):
        properties = self.ids.ids_properties
        time = waveforms["time"]
        return {
            "source": "pulse_schedule",
            "comment": str(getattr(properties, "comment", "") or ""),
            "creation_date": str(getattr(properties, "creation_date", "") or ""),
            "provider": str(getattr(properties, "provider", "") or ""),
            "dd_version": str(node_at(properties, "version_put.data_dictionary")
                              or ""),
            "homogeneous_time": str(getattr(properties, "homogeneous_time", "")),
            "n_time": time.size,
            "t_min": float(time[0]) if time.size else float("nan"),
            "t_max": float(time[-1]) if time.size else float("nan"),
            "n_coil": len(waveforms["coil_names"]),
            "n_boundary_point": waveforms["boundary_outline_r"].shape[0],
            "n_x_point": waveforms["x_point_r"].shape[0],
        }


class WaveformsFromIdsCompute:
    """The same waveforms, derived from the physics IDSs of a data entry.

    Args:
        entry: an open ``imas.DBEntry``.
    """

    def __init__(self, entry):
        self.entry = entry

    def _get(self, name):
        try:
            return self.entry.get(name, lazy=True)
        except Exception as exc:
            logger.info("%s could not be read (%s)", name, exc)
            return None

    def get_waveforms(self):
        waveforms = empty_waveforms(0)
        missing = waveforms["missing"]
        self._equilibrium(waveforms, missing)
        self._pf_active(waveforms, missing)
        self._core_sources(waveforms, missing)
        self._core_profiles(waveforms, missing)
        waveforms["info"] = self._info(waveforms)
        return waveforms

    # -- equilibrium -----------------------------------------------------
    def _equilibrium(self, waveforms, missing):
        equilibrium = self._get("equilibrium")
        if equilibrium is None or not len(equilibrium.time):
            logger.critical("equilibrium IDS could not be read")
            missing.append("equilibrium")
            return
        time = clean(np.asarray(equilibrium.time))
        waveforms["time"] = time
        for block in ("flux_control", "tf", "position_control"):
            waveforms["time_" + block] = time
        slices = equilibrium.time_slice

        waveforms["ip"] = get_0d_over_time(slices, "global_quantities.ip",
                                           missing, "equilibrium ip")
        waveforms["li_3"] = get_0d_over_time(slices, "global_quantities.li_3",
                                             missing, "equilibrium li_3")
        waveforms["beta_tor_norm"] = get_0d_over_time(
            slices, "global_quantities.beta_tor_norm", missing,
            "equilibrium beta_tor_norm")
        waveforms["magnetic_axis_r"] = get_0d_over_time(
            slices, "global_quantities.magnetic_axis.r", missing,
            "equilibrium magnetic_axis.r")
        waveforms["magnetic_axis_z"] = get_0d_over_time(
            slices, "global_quantities.magnetic_axis.z", missing,
            "equilibrium magnetic_axis.z")
        for key, path in (("geometric_axis_r", "boundary.geometric_axis.r"),
                          ("geometric_axis_z", "boundary.geometric_axis.z"),
                          ("minor_radius", "boundary.minor_radius"),
                          ("elongation", "boundary.elongation"),
                          ("triangularity", "boundary.triangularity"),
                          ("triangularity_upper", "boundary.triangularity_upper"),
                          ("triangularity_lower", "boundary.triangularity_lower")):
            waveforms[key] = get_0d_over_time(slices, path, missing,
                                              "equilibrium " + path)

        # B0.R0 of the vacuum toroidal field
        b0 = get_1d(equilibrium, "vacuum_toroidal_field.b0", time.size, missing,
                    "equilibrium vacuum_toroidal_field.b0")
        r0 = node_at(equilibrium, "vacuum_toroidal_field.r0")
        waveforms["b0_r0"] = b0 * float(r0) if r0 is not None else b0

        # boundary outline, one column per time slice (ragged, NaN padded)
        rows_r, rows_z = [], []
        for index in range(len(slices)):
            outline = node_at(slices[index], "boundary.outline")
            if outline is None:
                rows_r.append(np.array([]))
                rows_z.append(np.array([]))
                continue
            rows_r.append(clean(np.asarray(outline.r)))
            rows_z.append(clean(np.asarray(outline.z)))
        waveforms["boundary_outline_r"] = stack_ragged(rows_r)
        waveforms["boundary_outline_z"] = stack_ragged(rows_z)

        # X points: only some data dictionary versions describe them in the
        # equilibrium boundary; when absent the panel simply stays empty.
        waveforms["x_point_r"], waveforms["x_point_z"] = self._x_points(slices)

    @staticmethod
    def _x_points(slices):
        for path in ("boundary.x_point", "boundary_separatrix.x_point"):
            rows_r, rows_z, found = [], [], False
            for index in range(len(slices)):
                nodes = node_at(slices[index], path)
                if nodes is None:
                    break
                found = True
                rows_r.append([float(nodes[i].r) for i in range(len(nodes))])
                rows_z.append([float(nodes[i].z) for i in range(len(nodes))])
            if found and any(len(row) for row in rows_r):
                width = max(len(row) for row in rows_r)
                out_r = np.full((width, len(rows_r)), np.nan)
                out_z = np.full((width, len(rows_z)), np.nan)
                for column, (row_r, row_z) in enumerate(zip(rows_r, rows_z)):
                    out_r[: len(row_r), column] = clean(row_r)
                    out_z[: len(row_z), column] = clean(row_z)
                return out_r, out_z
        logger.info("no X point described in the equilibrium IDS")
        return np.zeros((0, 0), dtype=float), np.zeros((0, 0), dtype=float)

    # -- pf_active -------------------------------------------------------
    def _pf_active(self, waveforms, missing):
        pf_active = self._get("pf_active")
        if pf_active is None or not len(pf_active.coil):
            logger.critical("pf_active IDS could not be read")
            missing.append("pf_active")
            return
        time = clean(np.asarray(pf_active.time)) if len(pf_active.time) \
            else waveforms["time"]
        waveforms["time_pf_active"] = time
        names, currents, voltages = [], [], []
        for index in range(len(pf_active.coil)):
            coil = pf_active.coil[index]
            names.append(str(coil.name))
            currents.append(get_1d(coil, "current.data", time.size))
            voltages.append(get_1d(coil, "voltage.data", time.size))
        waveforms["coil_names_full"] = names
        waveforms["coil_names"] = [short_coil_name(name) for name in names]
        waveforms["coil_currents"] = np.vstack(currents) if currents \
            else np.zeros((0, 0))
        stacked = np.vstack(voltages) if voltages else np.zeros((0, 0))
        waveforms["coil_voltages"] = stacked if has_data(stacked) \
            else np.zeros((0, 0))

    # -- core_sources ----------------------------------------------------
    def _core_sources(self, waveforms, missing):
        core_sources = self._get("core_sources")
        if core_sources is None or not len(core_sources.source):
            logger.info("core_sources IDS could not be read, no H&CD waveform")
            return
        time = clean(np.asarray(core_sources.time)) if len(core_sources.time) \
            else waveforms["time"]
        for block in ("ec", "nbi", "ic", "lh"):
            waveforms["time_" + block] = time
        wanted = {index: key for key, index in SOURCE_INDEX.items()}
        totals = {}
        for position in range(len(core_sources.source)):
            source = core_sources.source[position]
            try:
                index = int(source.identifier.index)
            except Exception:
                continue
            key = wanted.get(index)
            if key is None:
                continue
            quantities = source.global_quantities
            if not len(quantities):
                continue
            # A source without a global power is a system that is not
            # activated (or that only carries profiles): not an error.
            power = get_0d_over_time(quantities, "power", critical=False,
                                     label="core_sources %s power" % key)
            if power.size != time.size:
                power = np.resize(power, time.size)
            totals[key] = totals.get(key, np.zeros(time.size)) + np.nan_to_num(power)
        for key in SOURCE_INDEX:
            if key in totals:
                waveforms[key] = totals[key]

    # -- core_profiles ---------------------------------------------------
    def _core_profiles(self, waveforms, missing):
        core_profiles = self._get("core_profiles")
        if core_profiles is None or not len(core_profiles.time):
            logger.info("core_profiles IDS could not be read, no v_loop waveform")
            return
        time = clean(np.asarray(core_profiles.time))
        ntime = time.size
        v_loop = get_1d(core_profiles, "global_quantities.v_loop", ntime)
        density = get_1d(core_profiles, "global_quantities.n_e_volume_average",
                         ntime)
        # Interpolate onto the equilibrium time base when they differ, so that a
        # single time array per block stays valid.
        reference = waveforms["time_flux_control"]
        if reference.size and not np.array_equal(reference, time):
            v_loop = np.interp(reference, time, v_loop, left=np.nan, right=np.nan)
            density = np.interp(reference, time, density, left=np.nan,
                                right=np.nan)
        if has_data(v_loop):
            waveforms["v_loop"] = v_loop
        if has_data(density):
            waveforms["n_e_volume_average"] = density
            waveforms["time_density_control"] = waveforms["time_flux_control"]
        # a line averaged density and zeff are not available from core_profiles

    def _info(self, waveforms):
        time = waveforms["time"]
        info = {
            "source": "equilibrium, pf_active, core_sources, core_profiles",
            "comment": "", "creation_date": "", "provider": "", "dd_version": "",
            "homogeneous_time": "",
            "n_time": time.size,
            "t_min": float(time[0]) if time.size else float("nan"),
            "t_max": float(time[-1]) if time.size else float("nan"),
            "n_coil": len(waveforms["coil_names"]),
            "n_boundary_point": waveforms["boundary_outline_r"].shape[0],
            "n_x_point": waveforms["x_point_r"].shape[0],
        }
        equilibrium = self._get("equilibrium")
        if equilibrium is not None:
            properties = equilibrium.ids_properties
            info["comment"] = str(getattr(properties, "comment", "") or "")
            info["creation_date"] = str(getattr(properties, "creation_date", "")
                                        or "")
            info["provider"] = str(getattr(properties, "provider", "") or "")
            info["dd_version"] = str(
                node_at(properties, "version_put.data_dictionary") or "")
        return info
