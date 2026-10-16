"""Piecewise-linear EC power tendencies from a DINA pulse's summary IDS.

PDS no longer copies DINA's ``core_sources`` into the pulse design and relabels its
``source(1)`` ("total" = additional + ohmic - radiation) as ``ec``: TORAX computes the
ohmic heating and the radiation itself (``workflows/<wf>/config_torax.py``: ``ohmic``,
``bremsstrahlung`` and Mavrin ``impurity_radiation`` on, ``ecrh`` gaussian deposition),
and the EC heating is a designed waveform whose total power reproduces DINA's
``summary/heating_current_drive/power_additional`` -- the only additional power DINA
fills (``power_ec``, ``power_nbi``, ``power_ic`` and ``power_lh`` are empty in every DINA
entry PDS uses; this script checks and reports it).

This script reads that trace with imas-python, fits a piecewise-linear tendency within a
tolerance (Douglas-Peucker on the power error, ``--tol`` in MW, default 0.1 MW) and
writes the Waveform-Editor entries, in one of two forms (``--ids``):

``core_sources`` (default; inverse_convergence and evolutive_controller, whose
``waveform_editor`` sends ``core_sources`` to the TORAX actor)::

  targets:
    core_sources/source(1)/identifier/name:
      - {value: ec}
    core_sources/source(1)/identifier/index:
      - {value: 3, start: 0, end: 300}
    core_sources/source(1)/global_quantities/power:
      - {time: [0, 4, 8, ...], value: [0, 0, 2.0e6, ...]}

``identifier/index`` is a constant tendency, which only covers its own interval (a
tendency evaluates to 0 outside every interval), hence the explicit ``start``/``end``
spanning the pulse. ``global_quantities/power`` is a piecewise tendency (linear
interpolation between the knots). The TORAX actor reads that power into
``sources.ecrh.P_total`` of its config and keeps the config's deposition model:
TORAX-MUSCLE3 ``torax_muscle3/torax_actor.py`` ``power_only_sources()`` -- **a local
change of ``local_installs/TORAX-MUSCLE3`` (diff: ``docs/torax_actor_power_only_sources.diff``
of the PDS notes) that still has to be upstreamed to
https://github.com/iterorganization/TORAX-MUSCLE3; the TORAX module of
``workflows/lib/easybuild_programs.ymmsl`` does not have it yet.**

``pulse_schedule`` (METIS-type workflows, which read ``ec/power_launched/reference``)::

  pulse_schedule/ec/power_launched/reference:
    - {time: [...], value: [...]}

Usage (``bin/pds-tendencies``)::

  pds-tendencies 105073                       # print the core_sources entries
  pds-tendencies 105073 --ids pulse_schedule  # METIS form
  pds-tendencies 105073 --tol 0.05            # tighter fit
  pds-tendencies --uri imas:hdf5?path=/work/imas/shared/imasdb/ITER/3/105033/1
  pds-tendencies 105073 --write cases/pulses/files/inverse_convergence_105073_waveforms.yaml
  pds-tendencies 105033 --write cases/pulses/files/inverse_convergence_105033_waveforms.yaml \\
                        --from workflows/inverse_convergence/waveforms.yaml
  pds-tendencies 105073 --check cases/pulses/files/inverse_convergence_105073_waveforms.yaml

The pulse is resolved like ``bin/pds-create-case`` resolves a case: ``cases/pulses/<case>.yaml``
(``prepare.summary``, else ``prepare.source``) when that pulse file exists, else
``$SCENARIOS_REPO/<shot>/source.env`` (``SUMMARY_URI``, else ``SOURCE_URI``;
``SCENARIOS_REPO`` defaults to ``$PDS_REPO/scenarios``). ``--uri`` bypasses both. The
raw DINA entries are DD 3 (HDF5 or MDSplus): the summary is read with
``autoconvert=False`` so that no DD conversion is attempted (the paths used here are the
same in DD 3 and DD 4).

``--write FILE`` replaces the EC entries (every ``core_sources/...`` key, or every
``pulse_schedule/ec/...`` key, of the ``targets:`` section) of an existing waveform yaml
with the fitted ones and keeps everything else (comments included: the file is edited
line by line, not re-serialised). With ``--from GENERIC`` a missing FILE is first created
as a copy of GENERIC (a workflow's generic ``waveforms.yaml``): that is how the per-pulse
files ``cases/pulses/files/<wf>_<case>_waveforms.yaml`` are made, which the pulse file then
references through ``settings.<wf>.waveform_editor.waveforms``. ``--check FILE`` reads
the EC tendency of FILE and prints its maximum deviation from the data (no fit, no write).
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import yaml

logger = logging.getLogger("pds-tendencies")

POWER_KEY = "core_sources/source(1)/global_quantities/power"
NAME_KEY = "core_sources/source(1)/identifier/name"
INDEX_KEY = "core_sources/source(1)/identifier/index"
PS_KEY = "pulse_schedule/ec/power_launched/reference"
EC_INDEX = 3  # DD core_source identifier: "ec" = 3 (electron cyclotron)
KEY_PREFIX = {"core_sources": "core_sources/", "pulse_schedule": "pulse_schedule/ec/"}
OTHER_POWERS = ("power_ec", "power_nbi", "power_ic", "power_lh")


class TendencyError(Exception):
    pass


@dataclass
class Summary:
    uri: str
    dd_version: str
    time: np.ndarray
    power_additional: np.ndarray
    power_ohm: np.ndarray
    ip: np.ndarray
    other_sizes: dict[str, int]


@dataclass
class Fit:
    time: list[float]
    value: list[float]
    max_error: float  # W, against the (rounded) knots
    n_data: int


# ----------------------------------------------------------------------------- input


def _source_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in env.items():
        env[key] = re.sub(
            r"\$\{?(\w+)\}?", lambda m: env.get(m.group(1), m.group(0)), value
        )
    return env


def resolve_uri(pulse: str, pds_repo: Path, scenarios_repo: Path) -> tuple[str, str]:
    """(uri, origin) of the summary entry of a pulse (case name, shot or pulse file)."""
    pulse_file = Path(pulse)
    if pulse_file.suffix != ".yaml":
        pulse_file = pds_repo / "cases" / "pulses" / f"{pulse}.yaml"
    if pulse_file.is_file():
        with pulse_file.open() as f:
            data = yaml.safe_load(f) or {}
        prepare = data.get("prepare") or {}
        for key in ("summary", "source"):
            uri = prepare.get(key)
            if isinstance(uri, str) and uri:
                return uri, f"{pulse_file}: prepare.{key}"
        raise TendencyError(f"{pulse_file}: no prepare.source")
    shot = re.match(r"\d+", pulse)
    env_file = scenarios_repo / (shot.group(0) if shot else pulse) / "source.env"
    if env_file.is_file():
        env = _source_env(env_file)
        for key in ("SUMMARY_URI", "SOURCE_URI"):
            if env.get(key):
                return env[key], f"{env_file}: {key}"
        raise TendencyError(f"{env_file}: no SOURCE_URI")
    raise TendencyError(
        f"pulse {pulse}: neither {pulse_file} nor {env_file} exists (set SCENARIOS_REPO, "
        "or give --uri)"
    )


def read_summary(uri: str) -> Summary:
    import imas  # the IMAS environment is only needed here

    with imas.DBEntry(uri, "r") as entry:
        # DD 3 data: read as stored, the paths below exist unchanged in DD 4
        summary = entry.get("summary", lazy=True, autoconvert=False)
        hcd = summary.heating_current_drive
        time = np.asarray(summary.time, dtype=float)
        p_add = np.asarray(hcd.power_additional.value, dtype=float)
        p_ohm = np.asarray(summary.global_quantities.power_ohm.value, dtype=float)
        ip = np.asarray(summary.global_quantities.ip.value, dtype=float)
        others = {
            name: int(np.asarray(getattr(hcd, name).value).size)
            for name in OTHER_POWERS
        }
        dd_version = str(summary.ids_properties.version_put.data_dictionary)
    if time.size == 0 or p_add.size == 0:
        raise TendencyError(
            f"{uri}: summary/time ({time.size}) or "
            f"heating_current_drive/power_additional ({p_add.size}) is empty"
        )
    if p_add.size != time.size:
        raise TendencyError(
            f"{uri}: power_additional has {p_add.size} points for {time.size} times"
        )
    keep = np.isfinite(p_add) & np.isfinite(time)
    return Summary(uri, dd_version, time[keep], p_add[keep], p_ohm, ip, others)


# ------------------------------------------------------------------------------- fit


def douglas_peucker(t: np.ndarray, y: np.ndarray, tol: float) -> list[int]:
    """Knot indices of a piecewise-linear fit of y(t) within tol (vertical error)."""
    n = t.size
    if n < 3:
        return list(range(n))
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        seg_t = t[i : j + 1]
        seg_y = y[i : j + 1]
        line = y[i] + (seg_y[-1] - seg_y[0]) * (seg_t - t[i]) / (t[j] - t[i])
        err = np.abs(seg_y - line)
        k = int(np.argmax(err))
        if err[k] > tol:
            keep[i + k] = True
            stack.append((i, i + k))
            stack.append((i + k, j))
    return [int(k) for k in np.flatnonzero(keep)]


def max_error(t: np.ndarray, y: np.ndarray, kt: list[float], kv: list[float]) -> float:
    """Max |y - tendency(t)| over the data; the tendency is 0 outside its knots."""
    fit = np.interp(t, kt, kv, left=0.0, right=0.0)
    return float(np.max(np.abs(y - fit)))


def _round_value(v: float, decimals: int, floor: float = 1.0) -> float:
    """Round to `decimals` significant digits; |v| below `floor` (W) is 0."""
    if abs(v) < floor:
        return 0.0
    return float(f"{v:.{decimals}e}")


def fit_tendency(s: Summary, tol_w: float, time_decimals: int = 2) -> Fit:
    """Piecewise-linear tendency of power_additional within tol_w (W), rounded knots."""
    t, y = s.time, s.power_additional
    if t.size == 1:
        return Fit([float(t[0])], [float(y[0])], 0.0, 1)
    for value_digits in (3, 4, 5, 6, 8):
        for decimals in (time_decimals, time_decimals + 1, time_decimals + 2):
            idx = douglas_peucker(t, y, tol_w)
            kt = [round(float(t[k]), decimals) for k in idx]
            kv = [_round_value(float(y[k]), value_digits) for k in idx]
            # rounding may merge two knots: keep them strictly increasing
            kt2, kv2 = [kt[0]], [kv[0]]
            for a, b in zip(kt[1:], kv[1:], strict=True):
                if a > kt2[-1]:
                    kt2.append(a)
                    kv2.append(b)
            err = max_error(t, y, kt2, kv2)
            if err <= tol_w:
                return Fit(kt2, kv2, err, int(t.size))
    return Fit(kt2, kv2, err, int(t.size))  # best effort, reported by the caller


# --------------------------------------------------------------------------- output


def _fmt_time(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else repr(v)


def _fmt_power(v: float) -> str:
    if v == 0:
        return "0"
    if abs(v) >= 1e6:
        mw = float(v) / 1e6
        return f"{mw:.6g}e6" if mw != int(mw) else f"{mw:.1f}e6"
    if abs(v) >= 1e3:
        return f"{v / 1e3:.6g}e3"
    return f"{v:.6g}"


def _inline_list(values: list[float], fmt) -> str:
    return "[" + ", ".join(fmt(v) for v in values) + "]"


def index_end(s: Summary) -> int:
    """End of the constant identifier/index tendency: past the pulse, a round number."""
    return int(math.ceil(float(s.time[-1]) / 10.0) * 10)


def render_entries(fit: Fit, s: Summary, ids: str, tol_w: float, cmd: str) -> list[str]:
    """The yaml lines (indented for the `targets:` section) of the EC entries."""
    others = ", ".join(f"{k}={v}" for k, v in s.other_sizes.items())
    pmax = max(fit.value) / 1e6
    head = [
        "  # EC heating power: piecewise-linear tendency of DINA's",
        "  # summary/heating_current_drive/power_additional (the only additional power",
        f"  # DINA fills: {others} points), {len(fit.time)} knots, max deviation",
        f"  # {fit.max_error / 1e6:.3f} MW (tolerance {tol_w / 1e6:g} MW) over "
        f"{fit.n_data} samples, peak {pmax:.4g} MW.",
        f"  # GENERATED by bin/pds-tendencies on {date.today().isoformat()}: {cmd}",
        f"  # source: {s.uri} (DD {s.dd_version})",
    ]
    tendency = (
        "    - {time: "
        + _inline_list(fit.time, _fmt_time)
        + ", value: "
        + _inline_list(fit.value, _fmt_power)
        + "}"
    )
    if ids == "pulse_schedule":
        return [*head, f"  {PS_KEY}:", tendency]
    end = index_end(s)
    return [
        *head,
        "  # TORAX (actor power_only_sources, see pds/tendencies.py) reads the power into",
        "  # sources.ecrh.P_total and computes the deposition, ohmic heating and radiation",
        "  # itself; the index tendency needs an explicit interval spanning the pulse.",
        f"  {NAME_KEY}:",
        "    - {value: ec}",
        f"  {INDEX_KEY}:",
        f"    - {{value: {EC_INDEX}, start: 0, end: {end}}}",
        f"  {POWER_KEY}:",
        tendency,
    ]


# ------------------------------------------------------------------------ yaml edit

_TOP_KEY = re.compile(r"^[A-Za-z_][\w]*:\s*(#.*)?$")
_ENTRY_KEY = re.compile(r"^  (\S[^:]*):\s*(#.*)?$")


def _targets_span(lines: list[str]) -> tuple[int, int] | None:
    """(start, end) line indices of the `targets:` section (end exclusive)."""
    start = next((i for i, ln in enumerate(lines) if ln.rstrip() == "targets:"), None)
    if start is None:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if _TOP_KEY.match(lines[i]):
            end = i
            break
    return start, end


def _entries(lines: list[str], start: int, end: int) -> list[tuple[int, int, str]]:
    """(first, last_exclusive, key) of each entry of a section, comments included."""
    out: list[tuple[int, int, str]] = []
    i = start + 1
    pending = i  # first line of the comments preceding the next key
    while i < end:
        m = _ENTRY_KEY.match(lines[i])
        if m:
            j = i + 1
            while j < end and (lines[j].startswith("    ") or lines[j].strip() == ""):
                j += 1
            # trailing blank lines belong to the section, not the entry
            while j > i + 1 and lines[j - 1].strip() == "":
                j -= 1
            out.append((pending, j, m.group(1).strip()))
            i = j
            pending = i
        elif lines[i].lstrip().startswith("#"):
            i += 1
        else:
            i += 1
            pending = i
    return out


def merge_entries(text: str, new_lines: list[str], ids: str) -> str:
    """Replace the EC entries of the `targets:` section of a waveform yaml text."""
    lines = text.splitlines()
    span = _targets_span(lines)
    if span is None:
        body = [*lines, "", "targets:", *new_lines]
        return "\n".join(body) + "\n"
    start, end = span
    prefix = KEY_PREFIX[ids]
    removed = [e for e in _entries(lines, start, end) if e[2].startswith(prefix)]
    if removed:
        first = removed[0][0]
        kept = list(lines[:first])
        pos = first
        for a, b, _key in removed:
            kept.extend(lines[pos:a])
            pos = b
        tail = lines[pos:]
        return "\n".join([*kept, *new_lines, *tail]) + "\n"
    # no EC entry yet: append at the end of the section (before trailing blanks)
    insert = end
    while insert > start + 1 and lines[insert - 1].strip() == "":
        insert -= 1
    return "\n".join([*lines[:insert], *new_lines, *lines[insert:]]) + "\n"


def _copy_header(generic: Path, pulse: str) -> str:
    return (
        f"# Per-pulse copy of {generic} for {pulse}, made by bin/pds-tendencies: only the\n"
        "# EC power entries (pulse data, see below) differ from the generic file. Regenerate\n"
        "# with the command recorded next to them.\n"
    )


def find_ec_waveform(path: Path, ids: str) -> tuple[list[float], list[float]]:
    """(time, value) of the EC power tendency stored in a waveform yaml."""
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    key = POWER_KEY if ids == "core_sources" else PS_KEY
    for section, entries in data.items():
        if isinstance(entries, dict) and key in entries:
            items = entries[key]
            if (
                isinstance(items, list)
                and len(items) == 1
                and isinstance(items[0], dict)
                and "time" in items[0]
            ):
                return (
                    [float(v) for v in items[0]["time"]],
                    [float(v) for v in items[0]["value"]],
                )
            raise TendencyError(
                f"{path}: {section}/{key} is not a single piecewise tendency: {items}"
            )
    raise TendencyError(f"{path}: no {key} entry")


def validate_yaml(path: Path, ids: str) -> None:
    kt, kv = find_ec_waveform(path, ids)
    if len(kt) != len(kv) or len(kt) < 1:
        raise TendencyError(f"{path}: inconsistent EC tendency written")


# ------------------------------------------------------------------------------ cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pds-tendencies",
        description="Fit the EC power tendency of a DINA pulse from its summary IDS "
        "(heating_current_drive/power_additional) and write the Waveform-Editor entries.",
    )
    parser.add_argument(
        "pulse",
        nargs="?",
        help="case name, shot or pulse file (cases/pulses/<case>.yaml, else "
        "$SCENARIOS_REPO/<shot>/source.env); not needed with --uri",
    )
    parser.add_argument("--uri", help="summary entry URI (bypasses the pulse lookup)")
    parser.add_argument(
        "--tol",
        type=float,
        default=0.1,
        metavar="MW",
        help="maximum deviation of the tendency from the data (default 0.1 MW)",
    )
    parser.add_argument(
        "--ids",
        choices=("core_sources", "pulse_schedule"),
        default="core_sources",
        help="output form: core_sources (TORAX workflows, default) or pulse_schedule "
        "(METIS workflows)",
    )
    parser.add_argument(
        "--write",
        type=Path,
        metavar="FILE",
        help="replace the EC entries of this waveform yaml (kept otherwise intact)",
    )
    parser.add_argument(
        "--from",
        dest="generic",
        type=Path,
        metavar="GENERIC",
        help="with --write: create FILE as a copy of GENERIC when it does not exist",
    )
    parser.add_argument(
        "--check",
        type=Path,
        metavar="FILE",
        help="print the max deviation of FILE's EC tendency from the data; no fit",
    )
    return parser


def _info(s: Summary) -> None:
    t0, t1 = float(s.time[0]), float(s.time[-1])
    logger.info(
        "summary %s (DD %s): %d samples, %g-%g s",
        s.uri,
        s.dd_version,
        s.time.size,
        t0,
        t1,
    )
    logger.info(
        "power_additional max %.4g MW; other additional powers: %s",
        float(np.max(s.power_additional)) / 1e6,
        ", ".join(f"{k} {v} points" for k, v in s.other_sizes.items()),
    )
    filled = [k for k, v in s.other_sizes.items() if v]
    if filled:
        logger.warning(
            "%s filled: power_additional may not be EC only", ", ".join(filled)
        )
    if s.power_ohm.size:
        logger.info(
            "for information: power_ohm max %.4g MW, ip %.4g..%.4g MA",
            float(np.nanmax(np.abs(s.power_ohm))) / 1e6,
            float(np.nanmin(s.ip)) / 1e6 if s.ip.size else math.nan,
            float(np.nanmax(s.ip)) / 1e6 if s.ip.size else math.nan,
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="pds-tendencies: %(message)s")
    logging.getLogger("imas").setLevel(logging.WARNING)  # DD parsing chatter
    pds_repo = Path(
        os.environ.get("PDS_REPO") or Path(__file__).resolve().parent.parent
    )
    scenarios_repo = Path(os.environ.get("SCENARIOS_REPO") or pds_repo / "scenarios")
    tol_w = args.tol * 1e6
    try:
        if args.uri:
            uri, origin = args.uri, "--uri"
        elif args.pulse:
            uri, origin = resolve_uri(args.pulse, pds_repo, scenarios_repo)
        else:
            raise TendencyError("give a pulse (case name, shot, pulse file) or --uri")
        logger.info("source: %s (%s)", uri, origin)
        summary = read_summary(uri)
        _info(summary)
        if args.check:
            kt, kv = find_ec_waveform(args.check, args.ids)
            err = max_error(summary.time, summary.power_additional, kt, kv)
            print(
                f"{args.check}: {len(kt)} knots, max deviation {err / 1e6:.4f} MW "
                f"({'within' if err <= tol_w else 'ABOVE'} {args.tol:g} MW)"
            )
            return 0 if err <= tol_w else 1
        fit = fit_tendency(summary, tol_w)
        if fit.max_error > tol_w:
            logger.warning(
                "tolerance %g MW not reached: max deviation %.4f MW",
                args.tol,
                fit.max_error / 1e6,
            )
        cmd = "pds-tendencies " + " ".join(argv if argv is not None else sys.argv[1:])
        lines = render_entries(fit, summary, args.ids, tol_w, cmd)
        logger.info(
            "%d knots, max deviation %.4f MW over %d samples",
            len(fit.time),
            fit.max_error / 1e6,
            fit.n_data,
        )
        if not args.write:
            print("targets:")
            print("\n".join(lines))
            return 0
        target: Path = args.write
        if target.is_file():
            text = target.read_text()
        elif args.generic:
            if not args.generic.is_file():
                raise TendencyError(f"--from {args.generic}: no such file")
            text = (
                _copy_header(args.generic, args.pulse or uri) + args.generic.read_text()
            )
            logger.info("%s created from %s", target, args.generic)
        else:
            raise TendencyError(f"--write {target}: no such file (give --from GENERIC)")
        target.write_text(merge_entries(text, lines, args.ids))
        validate_yaml(target, args.ids)
        logger.info("%s: EC entries written", target)
    except TendencyError as exc:
        print(f"pds-tendencies: error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
