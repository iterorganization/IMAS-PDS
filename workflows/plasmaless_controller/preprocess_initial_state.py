"""Build plasmaless_controller's initial state once, outside the MUSCLE3 workflow.

Replaces the former in-workflow chain `source` -> `waveform_editor` (run by
preprocess.sh at case creation). It makes exactly the calls those two actors made:

1. what imas_muscle3's source_component (iterative: false) sends, in its port order
   (sorted: equilibrium, pf_active): one IDS per port, read with the source's default
   DD version, `get` if no window is set, else `get_sample(tmin, tmax[, dtime])`
   (imas_muscle3/data_sink_source.py handle_source), serialized as the message payload;
2. what waveform_editor/muscle3.py does with those F_INIT messages (one reuse turn):
   `load_config`, deserialize each `<ids>_in` port into the waveform file's DD version
   with its /time as export time base (the first such port, equilibrium, wins),
   `ConfigurationExporter(config, times, received_idss).to_ids_dict()`.

The resulting equilibrium and pf_active (what waveform_editor sent on its O_F ports) are
written to one IMAS HDF5 entry, which the workflow's `source` then sends as F_INIT data.

The source window (t_min, t_max, dt, interpolation_method) is read from the case's own
settings files, in stacking order, with MUSCLE3's lookup rule (`source.<key>`, then the
bare `<key>`), so it is not duplicated here.
"""

import argparse
import logging
import time
from pathlib import Path

import imas
import numpy as np
import yaml
from imas.ids_defs import (
    CLOSEST_INTERP,
    IDS_TIME_MODE_HOMOGENEOUS,
    LINEAR_INTERP,
    PREVIOUS_INTERP,
)

# Waveform-Editor comes from its own module (loaded by preprocess.sh), not from the
# pds project environment.
from waveform_editor.cli import load_config  # ty: ignore[unresolved-import]
from waveform_editor.configuration import (  # ty: ignore[unresolved-import]
    WaveformConfiguration,
)
from waveform_editor.export.exporter import (  # ty: ignore[unresolved-import]
    ConfigurationExporter,
)

logger = logging.getLogger("preprocess_initial_state")

# source_component's O_I ports in this workflow, in its own (sorted) sending order.
PORTS = ["equilibrium", "pf_active"]
INTERP = {
    "closest": CLOSEST_INTERP,
    "previous": PREVIOUS_INTERP,
    "linear": LINEAR_INTERP,
}


def source_settings(settings_files):
    """Effective `source` settings from the stacked case settings files."""
    merged = {}
    for path in settings_files:
        if Path(path).is_file():
            merged.update(
                (yaml.safe_load(Path(path).read_text()) or {}).get("settings") or {}
            )

    def get(key, default=None):
        return merged.get(f"source.{key}", merged.get(key, default))

    return get("t_min"), get("t_max"), get("dt"), get("interpolation_method", "closest")


def source_messages(uri, t_min, t_max, dt, interp):
    """Payloads the source_component sends (non-iterative branch of handle_source)."""
    messages = {}
    with imas.DBEntry(uri, "r") as entry:
        for name in PORTS:
            if t_min is None and t_max is None:
                ids = entry.get(name)
            elif dt is not None:
                ids = entry.get_sample(
                    name,
                    tmin=-1e20 if t_min is None else t_min,
                    tmax=1e20 if t_max is None else t_max,
                    dtime=dt,
                    interpolation_method=INTERP.get(interp, CLOSEST_INTERP),
                )
            else:
                ids = entry.get_sample(
                    name,
                    tmin=-1e20 if t_min is None else t_min,
                    tmax=1e20 if t_max is None else t_max,
                )
            messages[name] = ids.serialize()
    return messages


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-uri", required=True, help="former source.source_uri")
    ap.add_argument("--waveforms", required=True, type=Path, help="waveforms.yaml")
    ap.add_argument("--out", required=True, type=Path, help="output entry directory")
    ap.add_argument("settings", nargs="*", help="case settings files, stacking order")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    t_min, t_max, dt, interp = source_settings(args.settings)
    logger.info("source window t_min=%s t_max=%s dt=%s", t_min, t_max, dt)

    t0 = time.perf_counter()
    messages = source_messages(args.source_uri, t_min, t_max, dt, interp)

    config = WaveformConfiguration()
    load_config(config, args.waveforms.resolve())
    dd_version = config.globals.dd_version
    times, received = None, {}
    for name in PORTS:
        ids = imas.IDSFactory(dd_version).new(name)
        ids.deserialize(messages[name])
        if int(ids.ids_properties.homogeneous_time) != IDS_TIME_MODE_HOMOGENEOUS:
            logger.warning("received '%s' IDS is not in homogeneous time mode", name)
        if times is None:
            times = np.asarray(ids.time, dtype=float)
        received[f"{name}_in"] = ids
    if times is None or times.size == 0:
        raise RuntimeError("source window holds no equilibrium time slice")
    logger.info(
        "%d slices [%.6f, %.6f] read in %.1f s",
        times.size,
        times[0],
        times[-1],
        time.perf_counter() - t0,
    )

    t0 = time.perf_counter()
    idss = ConfigurationExporter(config, times, received_idss=received).to_ids_dict()
    logger.info("Waveform-Editor export in %.1f s", time.perf_counter() - t0)

    args.out.mkdir(parents=True, exist_ok=True)
    with imas.DBEntry(
        f"imas:hdf5?path={args.out.resolve()}", "w", dd_version=dd_version
    ) as dst:
        for name in PORTS:
            dst.put(idss[name])
    logger.info("wrote %s to %s", ", ".join(PORTS), args.out)


if __name__ == "__main__":
    main()
