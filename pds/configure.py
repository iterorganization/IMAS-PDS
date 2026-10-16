"""Generate every shot-specific PDS input from one pulse file.

Two configuration layers only: ``workflows/<wf>/settings.ymmsl`` holds the generic
defaults of a workflow, and the pulse file ``cases/pulses/<case>.yaml`` holds everything
that is specific to one shot -- the DINA and machine-description inputs used to prepare
the scenario data, the simulated time window, the time steps, an optional TORAX transport
calibration, the post-processing plot times, and arbitrary setting overrides
(``settings:``). ``bin/pds-configure`` reads it and writes the tool-specific files
derived from it; ``bin/pds-create-case`` regenerates the per-workflow override from the
pulse file by itself. ``cases/overrides/`` is a generated, git-ignored cache; hand-written
override files are no longer supported. ``cases/pulses/TEMPLATE.yaml`` is a commented
starting point.

Pulse file keys
---------------

``shot`` (int, required)
    Shot / scenario number: the directory ``$SCENARIOS_REPO/<shot>`` holding the
    prepared data, and the ``${SHOT}`` of the workflow settings.
``case`` (str, default: the shot)
    Case name: the ``<case>`` of ``cases/overrides/<wf>_<case>.ymmsl``,
    ``cases/<wf>_<case>/`` and the second argument of ``bin/pds-create-case <wf> <case>``
    (which looks the pulse file up as ``cases/pulses/<case>.yaml``, so name the file after
    the case). Use it for a second design of the same shot's data, e.g. ``105084_literal``.
    When the case differs from the shot, every setting of the workflow's
    ``settings.ymmsl`` whose value contains ``${SHOT}`` is written explicitly into the
    override with the real shot number (``bin/pds-create-case`` substitutes ``${SHOT}``
    with its second argument, the case name), and every config file of that
    ``settings.ymmsl`` containing ``${SHOT}`` (e.g. the generic waveforms.yaml) must be
    replaced through ``settings:``.
``description`` (str, optional)
    Free text, copied as a comment into the generated files.
``workflows`` (list, required)
    Workflows this pulse is run with. Supported: ``inverse_convergence``,
    ``prescribed_transport``, ``evolutive_controller``, ``metis_from_dina``,
    ``metis_nice_inverse_from_dina``. One override file is generated per workflow; a
    workflow left out gets none (``bin/pds-create-case`` then uses the workflow's generic
    settings only, which is the same as an empty override). ``[]`` (empty) means
    preparation only: only ``source.env`` is written and ``--create`` does nothing.
``prepare`` (mapping, required) -> ``$SCENARIOS_REPO/<shot>/source.env``, the input of
``preprocessing/prepare``:

    ``source`` (str, required)             -> ``SOURCE_URI``, the DINA entry.
    ``summary`` (str, default ``source``)  -> ``SUMMARY_URI``.
    ``machine_description`` (required)     -> ``MD_PF_ACTIVE``, ``MD_PF_PASSIVE``,
        ``MD_WALL``, ``MD_IRON_CORE``. Either the name of a set or a mapping with the
        four keys ``pf_active``, ``pf_passive``, ``wall``, ``iron_core`` (URIs;
        ``iron_core`` may be ``empty``). Sets:

        ``basic``: the active ITER_MD catalogue versions (md_summary.yaml, checked
        2026-09-30): pf_active 111001/204, pf_passive 115005/3, wall 116000/5.
        ``legacy``: pf_active 111001/203, pf_passive 115005/2, wall 116000/4 -- the
        datasets the five pds-scenarios scenarios 105073/78/84/92/99 were prepared
        with; use only to reproduce them.

        ITER has no iron core, so in both sets iron_core is ``empty``: the converter
        creates an empty static iron_core IDS (a real URI is only needed for machines
        with an iron core, e.g. WEST).
    ``n_timeslices`` (int >= 2) -> ``N_TIMESLICES``, or ``dt_step`` (float > 0, s)
        -> ``DT_STEP``; exactly one is required. The slice selection:
        ``n_timeslices`` slices uniform over the viable DINA time range, or one slice
        every ``dt_step`` seconds from the first viable time (each mapped to the
        nearest viable raw sample). This slice grid is the outer time grid of
        inverse_convergence and prescribed_transport. ``time.t_start`` / ``t_end`` are
        also written as ``REPORT_T_START`` / ``REPORT_T_END``, used only by the
        preparation log (slices inside the simulation window).
    ``md_layout`` (``separate`` | ``combined``, default ``separate``) -> ``MD_LAYOUT``.
        inverse_convergence and prescribed_transport read ``data/in_md`` by default and
        therefore need ``separate``; with ``combined`` every setting of their
        ``settings.ymmsl`` that reads ``data/in_md`` (directly, or through a referenced
        config file such as the generic waveforms.yaml) must be replaced through
        ``settings:`` (see ``cases/pulses/105073.yaml``), otherwise the workflow is
        rejected. The two METIS workflows do not read ``data/``: their preprocess.sh
        builds their inputs from ``source.env`` at ``--create``, so they accept either
        layout.
    ``metis`` (mapping, optional) with ``mode`` (``interpretative`` | ``predictive``)
        -> ``METIS_MODE`` and ``nbt`` (int) -> ``METIS_NBT``; written only if present,
        and ``--prepare`` then passes ``--metis`` to preprocessing/prepare.
        ``nbt`` defaults to ``n_timeslices``, so it is required with ``dt_step``.
    ``dd_version`` (str, default ``"4.0.0"``) -> ``IMAS_VERSION`` of the
        preprocessing/prepare run, i.e. the data-dictionary version the prepared data
        are written at (recorded as a comment in source.env). 4.0.0 is the version of
        the stored data of the existing scenarios.

``time`` (mapping, required):

    ``t_start``, ``t_end`` (float, required, ``t_end > t_start``) -- simulated window:
        inverse_convergence ``loop.t_min`` / ``loop.t_max`` (selects slices of the
        prepared grid); prescribed_transport ``source.t_min`` / ``source.t_max``;
        evolutive_controller default of ``forward_t_start`` / ``forward_t_end``;
        metis_from_dina and metis_nice_inverse_from_dina ``source_metis.t_min`` /
        ``source_metis.t_max``. source_metis (imas_muscle3 ``source_component``,
        ``iterative`` default true) streams one slice per message for every native
        slice of its input in ``[t_min, t_max]``; METIS takes its time from the message
        timestamps (``metis_clock_internal`` off), so no METIS time setting is written.
        In metis_nice_inverse_from_dina, ``source_nice`` is a ``sink_source_component``
        that has no ``t_min``/``t_max``: it re-slices its input at the timestamp of each
        METIS equilibrium it receives, so the window reaches it through METIS.
    ``inverse_dt`` (float > 0, optional) -> inverse_convergence
        ``transport.torax.fixed_dt``, the TORAX step inside each outer slice interval
        (the last step is shortened to land on the next slice). Formerly
        ``transport_dt``; that key is rejected with a rename message.
    ``forward_dt`` (float > 0, optional) -> evolutive_controller ``torax.fixed_dt``,
        ``nice_evo_rd.dt`` and ``nice_evo_rd.t_interval``.
    ``forward_source_dt`` (float > 0, optional) -> evolutive_controller ``source.dt``,
        the resampling step of the input data.
    ``forward_t_start``, ``forward_t_end`` (float, default ``t_start`` / ``t_end``,
        ``forward_t_end > forward_t_start``) -- evolutive_controller forward window:
        ``source.t_min`` and the end of the forward simulation, ``torax.t_final`` and
        ``nice_evo_rd.t_end``.
    ``forward_load_t_end`` (float, default ``forward_t_end``, ``>= forward_t_end``) ->
        evolutive_controller ``source.t_max``, the end of the time range the source
        loads; set it above ``forward_t_end`` to load more of the inverse result than
        is simulated (105084 loads 136..256 s and simulates to 136.6 s).
    ``forward_source`` (str, optional) -> evolutive_controller ``source.source_uri``,
        the inverse result the forward run starts from. Default (not written): the
        workflow's ``imas:hdf5?path=${PDS_REPO}/cases/runs/inverse_convergence_${SHOT}/
        out_nice``, i.e. the latest inverse_convergence run of the same shot.

    Forward-window check: whenever evolutive_controller is selected (every mode,
    ``--dry-run`` included, before anything is written) the effective source is
    resolved (``$PDS_REPO``/``$SHOT`` expanded). For an existing local
    ``imas:hdf5?path=`` entry its ``equilibrium.time`` is read (read-only, lazy): a
    window outside it (tolerance 1e-6 s) is an error (a ``forward_load_t_end`` beyond
    it only a warning); otherwise the first native slice of the window is logged, with
    a warning if ``forward_t_start`` is not a native slice (a non-native start diverged
    on 105073). A non-HDF5 or not-yet-existing source only gets a warning: rerun after
    the inverse_convergence run for a hard check.

``inverse_convergence`` (mapping, optional) -> ``loop.<key>`` of inverse_convergence:
    ``max_iterations`` (int >= 1), ``tolerance`` (float > 0), ``rel_tolerance``
    (float >= 0), ``max_slices`` (int >= 0, 0 = all), ``cold_start`` (bool). Unset keys
    keep the workflow defaults of ``workflows/inverse_convergence/settings.ymmsl``.

``transport_calibration`` (mapping, optional). Omit it to keep the workflow's generic
qlknn transport. When present, a calibrated ``<wf>_<case>_config_torax.py`` is generated
for each selected workflow with TORAX (inverse_convergence, evolutive_controller; not
prescribed_transport and the METIS workflows, which have no TORAX): the
workflow's generic ``config_torax.py`` verbatim, followed by assignments that switch
``CONFIG["transport"]`` to the calibrated model; the override points
``<torax instance>.python_config_module`` at it. Keys:

    ``model`` (required): ``bohm-gyrobohm`` (the only supported model).
    ``chi_multiplier``: applied to all four multipliers below.
    ``chi_e_bohm_multiplier``, ``chi_i_bohm_multiplier``, ``chi_e_gyrobohm_multiplier``,
    ``chi_i_gyrobohm_multiplier``: per-channel values, overriding ``chi_multiplier``.

    Each value is a number or a table ``{time_s: value}`` (times strictly increasing,
    values > 0), piecewise-linear in time and constant outside the given range. A
    multiplier left unset keeps the TORAX default 1.0.

``settings`` (mapping, optional) -- pass-through of arbitrary MUSCLE3 settings:
``<workflow>: {<instance>.<setting>: value, ...}``. Each workflow named here must be in
``workflows``. Values are scalars (int, float, bool, str) or lists of scalars; strings
may contain ``${PDS_REPO}``, ``${SCENARIOS_REPO}``, ``${SHOT}`` and ``${CASE_DIR}``
literally (``bin/pds-create-case`` substitutes them). They are written at the end of the
workflow's override, under ``# settings: pass-through from the pulse file``, so they win
over the workflow's ``settings.ymmsl``. Checks: a key must start with the name of an
instance of the workflow (``workflows/<wf>/workflow.ymmsl``, nested models included,
e.g. ``equilibrium.nice.xml_path`` or ``equilibrium.xml_path``; libmuscle resolves a
setting through the instance's prefixes), or already appear in the workflow's
``settings.ymmsl``, or be a MUSCLE3 reserved setting (``muscle_*``); a key that one of
the keys above controls (e.g. ``loop.t_min`` from ``time.t_start``) is an error naming
that key. Config files of your own (a waveform design, a NICE xml, a TORAX config) go to
``cases/pulses/files/`` (tracked) and are referenced as
``${PDS_REPO}/cases/pulses/files/<name>``; ``bin/pds-create-case`` freezes a copy of
every ``*.xml_path`` / ``*.python_config_module`` / ``*.config`` / ``*.waveforms`` file
into the case's ``config/``.

``postprocess`` (mapping, optional):
    ``t_list`` (list of numbers) -- plot times of the validation plots
    (``workflows/inverse_convergence/postprocess.sh``). Default: 25/50/75 % of
    ``[t_start, t_end]``, rounded to 0.1 s.

Unknown keys and wrong types are errors.

Failures
--------

Pulse-file errors (unknown keys, wrong types, invalid ``settings`` keys, a ``--workflow``
not listed) and failures common to all workflows (``source.env``, ``--prepare``) are
fatal at once. A failure of one workflow -- generating its override, its check (e.g. the
evolutive_controller forward-window check), the overwrite guard of its files, or its
``pds-create-case`` -- is reported, that workflow is skipped and the others continue;
the command then exits with code 1 and a final ``failed workflows:`` summary line.

Generated files
---------------

* ``$SCENARIOS_REPO/<shot>/source.env`` (not with ``--overrides-only``)
* ``$PDS_REPO/cases/overrides/<wf>_<case>.ymmsl`` for each workflow, stacked after the
  generic ``workflows/<wf>/settings.ymmsl`` by ``bin/pds-create-case``
* ``$PDS_REPO/cases/overrides/<wf>_<case>_config_torax.py`` if ``transport_calibration``
* with ``--create``: ``export SCENARIOS_REPO=<data root>`` appended to each new
  ``<case>/case.env``, which bin/pds-run-case.sbatch sources before post-processing, and
  ``<case>/settings_origin.txt``, the ``--explain`` table of that case

``cases/overrides/`` is a git-ignored cache (only its README is tracked): generated
files are never committed, ``bin/pds-configure`` and ``bin/pds-create-case`` rebuild
them from the pulse file. Each file starts with a ``# GENERATED by bin/pds-configure``
marker line. A ``cases/overrides/<wf>_<case>.ymmsl`` without that marker is a
hand-written override: those are no longer supported, both commands refuse it -- move
its settings into the pulse file (``settings:`` section) and delete it (or ``--force``
to overwrite it).

``bin/pds-create-case <wf> <case>`` runs ``pds/configure.py cases/pulses/<case>.yaml
--overrides-only --workflow <wf>`` itself when that pulse file exists (unless
``PDS_CONFIGURE_NO_REGEN`` is set, which ``--create`` sets for the child it spawns), so
the override is always up to date with the pulse file; a workflow not listed in the
pulse file gets no override (a stale generated one is removed).

Command line
------------

::

    bin/pds-configure <pulse.yaml> [--workflow WF ...] [--prepare] [--create]
                      [--overrides-only] [--force] [--dry-run] [--print-t-list]
                      [--explain [WF]] [--overlay FILE ...]

Without options, writes the files above. ``--workflow`` restricts to a subset of
``workflows``. ``--overrides-only`` writes the overrides only, never source.env (used by
``bin/pds-create-case``; with it a ``--workflow`` not listed in the pulse file is not an
error: nothing is generated and a stale generated override is removed). ``--dry-run``
prints paths and contents (and the commands ``--prepare`` / ``--create`` would run)
without doing anything. ``--prepare`` then runs ``$PDS_REPO/preprocessing/prepare
<shot>`` (plus ``--metis`` if ``prepare.metis`` is set) with this interpreter as
``PREPARE_PYTHON`` (the IMAS-MUSCLE3 environment has everything preprocessing/prepare
needs) and ``IMAS_VERSION`` = ``prepare.dd_version``. ``--create`` then runs
``bin/pds-create-case -f <wf> <case>`` for each selected workflow, appends ``export
SCENARIOS_REPO=...`` to the new case's ``case.env``, writes ``settings_origin.txt``, and
runs ``preprocessing/check_scenario.py`` on the new case (figure
``<case>/check_<shot>.png``), printing its OK/WARN lines (a failing check is reported,
not fatal). ``--print-t-list`` prints the post-processing plot times, space separated,
and exits. ``--explain [WF]`` prints, for each selected workflow (or only WF), a table
``setting | value | origin`` of every effective setting of the case -- origin being the
workflow's ``workflow.ymmsl``, its ``settings.ymmsl``, the pulse key that produced it
(``pulse: time.t_start``, ``pulse: settings pass-through``, ``pulse: case name``) or an
``--overlay FILE`` (repeatable, stacked last like the overlays of ``bin/pds-run-case``)
-- and exits; values are shown raw, ``${...}`` unsubstituted.

Environment: ``PDS_REPO`` (default: the checkout containing this package),
``SCENARIOS_REPO`` (the scenario data root; default ``$PDS_REPO/scenarios``, which is
not committed). Both are exported to the child processes.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("pds-configure")

MARKER_PREFIX = "# GENERATED by bin/pds-configure from "
# Suffixes of the settings whose value is a config file that bin/pds-create-case copies
# into the case's config/ (its CONFIG_KEY_RE).
CONFIG_KEY_SUFFIXES = ("xml_path", "python_config_module", "config", "waveforms")
RESERVED_SETTING_PREFIX = "muscle_"  # MUSCLE3 reserved settings (muscle_*)
CASE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
SETTING_KEY_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(\[[0-9]+\])?(\.[A-Za-z_][A-Za-z0-9_]*(\[[0-9]+\])?)*"
)
# Origins shown by --explain.
ORIGIN_WORKFLOW = "workflow.ymmsl"
ORIGIN_SETTINGS = "workflow settings.ymmsl"
ORIGIN_PASS_THROUGH = "pulse: settings pass-through"
ORIGIN_CASE_NAME = "pulse: case name"
# Default evolutive_controller source (workflows/evolutive_controller/settings.ymmsl):
# the NICE inverse output of the latest inverse_convergence run of the same shot.
FORWARD_SOURCE_DEFAULT = (
    "imas:hdf5?path=${PDS_REPO}/cases/runs/inverse_convergence_${SHOT}/out_nice"
)
TIME_TOL = 1e-6  # s, tolerance of the forward-window check
DEFAULT_DD_VERSION = "4.0.0"
LINE_LENGTH = 88

SUPPORTED_WORKFLOWS = (
    "inverse_convergence",
    "prescribed_transport",
    "evolutive_controller",
    "metis_from_dina",
    "metis_nice_inverse_from_dina",
)
# Workflow -> ymmsl instance of its TORAX actor (None: no TORAX).
TORAX_INSTANCE: dict[str, str | None] = {
    "inverse_convergence": "transport.torax",
    "prescribed_transport": None,
    "evolutive_controller": "torax",
    "metis_from_dina": None,
    "metis_nice_inverse_from_dina": None,
}
# METIS workflows: their source_component that feeds METIS (the only time-bounded
# source; source_nice of metis_nice_inverse_from_dina is a sink_source_component without
# t_min/t_max that follows METIS's timestamps).
METIS_SOURCE = {
    "metis_from_dina": "source_metis",
    "metis_nice_inverse_from_dina": "source_metis",
}
# Workflows whose settings.ymmsl reads data/in + data/in_md (the separate layout).
SEPARATE_MD_WORKFLOWS = ("inverse_convergence", "prescribed_transport")

_ITER_MD = "imas:hdf5?path=/work/imas/shared/imasdb/ITER_MD/3"
# ITER has no iron core: the converter creates an empty static iron_core IDS.
_IRON_CORE_EMPTY = "empty"
MACHINE_DESCRIPTIONS: dict[str, dict[str, str]] = {
    # Active ITER_MD catalogue versions (md_summary.yaml, checked 2026-09-30).
    "basic": {
        "pf_active": f"{_ITER_MD}/111001/204",
        "pf_passive": f"{_ITER_MD}/115005/3",
        "wall": f"{_ITER_MD}/116000/5",
        "iron_core": _IRON_CORE_EMPTY,
    },
    # The datasets the five pds-scenarios scenarios 105073/78/84/92/99 were prepared
    # with; use only to reproduce them.
    "legacy": {
        "pf_active": f"{_ITER_MD}/111001/203",
        "pf_passive": f"{_ITER_MD}/115005/2",
        "wall": f"{_ITER_MD}/116000/4",
        "iron_core": _IRON_CORE_EMPTY,
    },
}
MD_KEYS = ("pf_active", "pf_passive", "wall", "iron_core")
MD_ENV = {
    "pf_active": "MD_PF_ACTIVE",
    "pf_passive": "MD_PF_PASSIVE",
    "wall": "MD_WALL",
    "iron_core": "MD_IRON_CORE",
}
MULTIPLIERS = (
    "chi_e_bohm_multiplier",
    "chi_i_bohm_multiplier",
    "chi_e_gyrobohm_multiplier",
    "chi_i_gyrobohm_multiplier",
)
CALIBRATION_MODELS = ("bohm-gyrobohm",)
METIS_MODES = ("interpretative", "predictive")

Table = float | dict[float, float]


class ConfigError(Exception):
    """Invalid pulse file or refused action."""


@dataclass
class Pulse:
    """Validated content of a pulse file."""

    path: Path
    shot: int
    case: str
    description: str | None
    workflows: list[str]
    source: str
    summary: str | None
    machine_description: dict[str, str]
    md_name: str | None
    n_timeslices: int | None
    md_layout: str
    metis: dict[str, Any] | None
    dd_version: str
    t_start: float
    t_end: float
    inverse_dt: float | None
    forward_dt: float | None
    forward_source_dt: float | None
    forward_t_start: float
    forward_t_end: float
    forward_source: str | None
    forward_load_t_end: float = 0.0
    dt_step: float | None = None
    settings: dict[str, dict[str, Any]] = field(default_factory=dict)
    loop: dict[str, Any] = field(default_factory=dict)
    calibration_model: str | None = None
    multipliers: dict[str, Table] = field(default_factory=dict)
    t_list: list[float] = field(default_factory=list)


# --------------------------------------------------------------------------- validation


class _Checker:
    """Type checks that name the offending key and the pulse file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def fail(self, key: str, msg: str) -> ConfigError:
        return ConfigError(f"{self.path}: {key}: {msg}")

    def mapping(
        self,
        value: object,
        key: str,
        allowed: tuple[str, ...],
        required: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise self.fail(key, f"expected a mapping, got {type(value).__name__}")
        for k in value:
            if not isinstance(k, str) or k not in allowed:
                where = f"{key}.{k}" if key else str(k)
                raise ConfigError(
                    f"{self.path}: unknown key '{where}' (allowed: {', '.join(allowed)})"
                )
        for k in required:
            if k not in value:
                where = f"{key}.{k}" if key else k
                raise ConfigError(f"{self.path}: missing required key '{where}'")
        return value

    def string(self, value: object, key: str) -> str:
        if not isinstance(value, str) or not value:
            raise self.fail(key, f"expected a non-empty string, got {value!r}")
        return value

    def integer(self, value: object, key: str, minimum: int | None = None) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise self.fail(key, f"expected an integer, got {value!r}")
        if minimum is not None and value < minimum:
            raise self.fail(key, f"must be >= {minimum}, got {value}")
        return value

    def number(
        self,
        value: object,
        key: str,
        positive: bool = False,
        nonnegative: bool = False,
    ) -> float:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise self.fail(key, f"expected a number, got {value!r}")
        result = float(value)
        if positive and result <= 0:
            raise self.fail(key, f"must be > 0, got {value}")
        if nonnegative and result < 0:
            raise self.fail(key, f"must be >= 0, got {value}")
        return result

    def boolean(self, value: object, key: str) -> bool:
        if not isinstance(value, bool):
            raise self.fail(key, f"expected true or false, got {value!r}")
        return value

    def choice(self, value: object, key: str, choices: tuple[str, ...]) -> str:
        if value not in choices:
            raise self.fail(key, f"must be one of {', '.join(choices)}, got {value!r}")
        return str(value)

    def table(self, value: object, key: str) -> Table:
        if not isinstance(value, dict):
            return self.number(value, key, positive=True)
        if not value:
            raise self.fail(key, "empty time table")
        result: dict[float, float] = {}
        previous: float | None = None
        for t, v in value.items():
            time = self.number(t, f"{key} (time {t!r})")
            if previous is not None and time <= previous:
                raise self.fail(key, f"times must be strictly increasing ({t!r})")
            result[time] = self.number(v, f"{key}[{t!r}]", positive=True)
            previous = time
        return result


def _setting_value(c: _Checker, value: object, key: str) -> Any:
    """A pass-through setting value: a scalar or a list of scalars."""
    if isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list):
        for i, item in enumerate(value):
            if not isinstance(item, bool | int | float | str):
                raise c.fail(
                    f"{key}[{i}]",
                    f"expected a scalar (int, float, bool, str), got {item!r}",
                )
        return list(value)
    raise c.fail(key, f"expected a scalar or a list of scalars, got {value!r}")


def load_pulse(path: Path) -> Pulse:
    """Read and strictly validate a pulse file."""
    try:
        raw = yaml.safe_load(path.read_text())
    except OSError as exc:
        raise ConfigError(f"cannot read pulse file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    c = _Checker(path)
    top = c.mapping(
        raw,
        "",
        (
            "shot",
            "case",
            "description",
            "workflows",
            "prepare",
            "time",
            "inverse_convergence",
            "transport_calibration",
            "settings",
            "postprocess",
        ),
        ("shot", "workflows", "prepare", "time"),
    )
    shot = c.integer(top["shot"], "shot", minimum=0)
    case = str(shot)
    if top.get("case") is not None:
        case = c.string(top["case"], "case")
        if not CASE_NAME_RE.fullmatch(case):
            raise c.fail("case", f"expected a name like 105084_literal, got {case!r}")
    if path.stem != case:
        logger.warning(
            "%s: the file is not named after the case (%s): bin/pds-create-case looks "
            "the pulse file up as cases/pulses/%s.yaml",
            path,
            case,
            case,
        )
    description = None
    if top.get("description") is not None:
        description = c.string(top["description"], "description")

    wfs = top["workflows"]
    if not isinstance(wfs, list):
        raise c.fail("workflows", "expected a list ([] for preparation only)")
    workflows: list[str] = []
    for i, wf in enumerate(wfs):
        name = c.choice(wf, f"workflows[{i}]", SUPPORTED_WORKFLOWS)
        if name in workflows:
            raise c.fail("workflows", f"'{name}' listed twice")
        workflows.append(name)

    prep = c.mapping(
        top["prepare"],
        "prepare",
        (
            "source",
            "summary",
            "machine_description",
            "n_timeslices",
            "dt_step",
            "md_layout",
            "metis",
            "dd_version",
        ),
        ("source", "machine_description"),
    )
    source = c.string(prep["source"], "prepare.source")
    summary = None
    if prep.get("summary") is not None:
        summary = c.string(prep["summary"], "prepare.summary")
    md_raw = prep["machine_description"]
    md_name: str | None = None
    if isinstance(md_raw, str):
        md_name = c.choice(
            md_raw, "prepare.machine_description", tuple(MACHINE_DESCRIPTIONS)
        )
        machine_description = dict(MACHINE_DESCRIPTIONS[md_name])
    else:
        md_map = c.mapping(md_raw, "prepare.machine_description", MD_KEYS, MD_KEYS)
        machine_description = {
            k: c.string(md_map[k], f"prepare.machine_description.{k}") for k in MD_KEYS
        }
    has_n = prep.get("n_timeslices") is not None
    has_dt = prep.get("dt_step") is not None
    if has_n == has_dt:
        raise c.fail(
            "prepare",
            "set exactly one of n_timeslices (number of slices) and dt_step (time step"
            " between slices, s)" + (", not both" if has_n else ""),
        )
    n_timeslices: int | None = None
    dt_step: float | None = None
    if has_n:
        n_timeslices = c.integer(
            prep["n_timeslices"], "prepare.n_timeslices", minimum=2
        )
    else:
        dt_step = c.number(prep["dt_step"], "prepare.dt_step", positive=True)
    md_layout = c.choice(
        prep.get("md_layout", "separate"), "prepare.md_layout", ("separate", "combined")
    )
    metis: dict[str, Any] | None = None
    if prep.get("metis") is not None:
        m = c.mapping(prep["metis"], "prepare.metis", ("mode", "nbt"))
        metis = {}
        if "mode" in m:
            metis["mode"] = c.choice(m["mode"], "prepare.metis.mode", METIS_MODES)
        if "nbt" in m:
            metis["nbt"] = c.integer(m["nbt"], "prepare.metis.nbt", minimum=2)
        elif dt_step is not None:
            raise c.fail(
                "prepare.metis.nbt",
                "required with prepare.dt_step (it defaults to n_timeslices)",
            )
    dd_version = DEFAULT_DD_VERSION
    if prep.get("dd_version") is not None:
        dd_version = c.string(prep["dd_version"], "prepare.dd_version")
        if not re.fullmatch(r"\d+\.\d+\.\d+", dd_version):
            raise c.fail(
                "prepare.dd_version",
                f"expected a version like '4.0.0', got {dd_version!r}",
            )

    if isinstance(top["time"], dict) and "transport_dt" in top["time"]:
        raise c.fail(
            "time.transport_dt",
            "time.transport_dt was renamed to time.inverse_dt "
            "(TORAX step inside inverse_convergence)",
        )
    tm = c.mapping(
        top["time"],
        "time",
        (
            "t_start",
            "t_end",
            "inverse_dt",
            "forward_dt",
            "forward_source_dt",
            "forward_t_start",
            "forward_t_end",
            "forward_load_t_end",
            "forward_source",
        ),
        ("t_start", "t_end"),
    )
    t_start = c.number(tm["t_start"], "time.t_start")
    t_end = c.number(tm["t_end"], "time.t_end")
    if t_end <= t_start:
        raise c.fail("time.t_end", f"must be > time.t_start ({t_end} <= {t_start})")
    steps: dict[str, float | None] = {}
    for k in ("inverse_dt", "forward_dt", "forward_source_dt"):
        steps[k] = None
        if tm.get(k) is not None:
            steps[k] = c.number(tm[k], f"time.{k}", positive=True)
    forward_t_start = t_start
    if tm.get("forward_t_start") is not None:
        forward_t_start = c.number(tm["forward_t_start"], "time.forward_t_start")
    forward_t_end = t_end
    if tm.get("forward_t_end") is not None:
        forward_t_end = c.number(tm["forward_t_end"], "time.forward_t_end")
    if forward_t_end <= forward_t_start:
        raise c.fail(
            "time.forward_t_end",
            f"must be > time.forward_t_start ({forward_t_end} <= {forward_t_start})",
        )
    forward_load_t_end = forward_t_end
    if tm.get("forward_load_t_end") is not None:
        forward_load_t_end = c.number(
            tm["forward_load_t_end"], "time.forward_load_t_end"
        )
    if forward_load_t_end < forward_t_end:
        raise c.fail(
            "time.forward_load_t_end",
            f"must be >= time.forward_t_end ({forward_load_t_end} < {forward_t_end})",
        )
    forward_source: str | None = None
    if tm.get("forward_source") is not None:
        forward_source = c.string(tm["forward_source"], "time.forward_source")

    loop: dict[str, Any] = {}
    if top.get("inverse_convergence") is not None:
        ic = c.mapping(
            top["inverse_convergence"],
            "inverse_convergence",
            (
                "max_iterations",
                "tolerance",
                "rel_tolerance",
                "max_slices",
                "cold_start",
            ),
        )
        checks = {
            "max_iterations": lambda v, k: c.integer(v, k, minimum=1),
            "tolerance": lambda v, k: c.number(v, k, positive=True),
            "rel_tolerance": lambda v, k: c.number(v, k, nonnegative=True),
            "max_slices": lambda v, k: c.integer(v, k, minimum=0),
            "cold_start": c.boolean,
        }
        for k, v in ic.items():
            loop[k] = checks[k](v, f"inverse_convergence.{k}")

    calibration_model: str | None = None
    multipliers: dict[str, Table] = {}
    if top.get("transport_calibration") is not None:
        tc = c.mapping(
            top["transport_calibration"],
            "transport_calibration",
            ("model", "chi_multiplier", *MULTIPLIERS),
            ("model",),
        )
        calibration_model = c.choice(
            tc["model"], "transport_calibration.model", CALIBRATION_MODELS
        )
        common = None
        if tc.get("chi_multiplier") is not None:
            common = c.table(
                tc["chi_multiplier"], "transport_calibration.chi_multiplier"
            )
        for k in MULTIPLIERS:
            if tc.get(k) is not None:
                multipliers[k] = c.table(tc[k], f"transport_calibration.{k}")
            elif common is not None:
                multipliers[k] = common

    settings: dict[str, dict[str, Any]] = {}
    if top.get("settings") is not None:
        st = c.mapping(top["settings"], "settings", tuple(SUPPORTED_WORKFLOWS))
        for wf, raw_items in st.items():
            if wf not in workflows:
                raise c.fail(
                    f"settings.{wf}",
                    f"{wf} is not in workflows ({', '.join(workflows) or 'empty'})",
                )
            if not isinstance(raw_items, dict):
                raise c.fail(f"settings.{wf}", "expected a mapping of <setting>: value")
            settings[wf] = {}
            for key, value in raw_items.items():
                where = f"settings.{wf}.{key}"
                if not isinstance(key, str) or not SETTING_KEY_RE.fullmatch(key):
                    raise c.fail(
                        where, "expected a setting name like <instance>.<setting>"
                    )
                settings[wf][key] = _setting_value(c, value, where)

    if top.get("postprocess") is not None:
        pp = c.mapping(top["postprocess"], "postprocess", ("t_list",))
    else:
        pp = {}
    if pp.get("t_list") is not None:
        tl = pp["t_list"]
        if not isinstance(tl, list) or not tl:
            raise c.fail("postprocess.t_list", "expected a non-empty list of numbers")
        t_list = [c.number(t, f"postprocess.t_list[{i}]") for i, t in enumerate(tl)]
        for t in t_list:
            if not t_start <= t <= t_end:
                logger.warning(
                    "%s: postprocess.t_list time %g is outside [t_start, t_end]",
                    path,
                    t,
                )
    else:
        span = t_end - t_start
        t_list = [round(t_start + f * span, 1) for f in (0.25, 0.5, 0.75)]

    return Pulse(
        path=path,
        shot=shot,
        case=case,
        description=description,
        workflows=workflows,
        source=source,
        summary=summary,
        machine_description=machine_description,
        md_name=md_name,
        n_timeslices=n_timeslices,
        dt_step=dt_step,
        md_layout=md_layout,
        metis=metis,
        dd_version=dd_version,
        t_start=t_start,
        t_end=t_end,
        inverse_dt=steps["inverse_dt"],
        forward_dt=steps["forward_dt"],
        forward_source_dt=steps["forward_source_dt"],
        forward_t_start=forward_t_start,
        forward_t_end=forward_t_end,
        forward_load_t_end=forward_load_t_end,
        forward_source=forward_source,
        settings=settings,
        loop=loop,
        calibration_model=calibration_model,
        multipliers=multipliers,
        t_list=t_list,
    )


# --------------------------------------------------------------------------- rendering


def marker(pulse: Pulse, pds_repo: Path) -> str:
    """The first line of every generated file."""
    try:
        shown = pulse.path.resolve().relative_to(pds_repo.resolve())
    except ValueError:
        shown = pulse.path.resolve()
    return f"{MARKER_PREFIX}{shown} -- edit that file and rerun; do not edit this one"


def _fmt_time(t: float) -> str:
    return f"{t:g}"


def render_source_env(pulse: Pulse, mark: str) -> str:
    """source.env for preprocessing/prepare."""
    md = pulse.machine_description
    lines = [
        mark,
        "# Inputs that preprocessing/prepare turns into data/. Read-only sources on the"
        " ITER SDCC cluster.",
        f"# data-dictionary version: IMAS_VERSION={pulse.dd_version} (prepare.dd_version,"
        " exported by pds-configure --prepare)",
    ]
    if pulse.description:
        lines.append(f"# {pulse.description}")
    lines.append(f'SOURCE_URI="{pulse.source}"')
    summary = pulse.summary if pulse.summary is not None else "$SOURCE_URI"
    lines.append(f'SUMMARY_URI="{summary}"')
    if pulse.md_name:
        lines.append(f"# machine description: set '{pulse.md_name}'")
    for k in MD_KEYS:
        line = f'{MD_ENV[k]}="{md[k]}"'
        if k == "iron_core" and md[k] == _IRON_CORE_EMPTY:
            line += "   # empty for ITER"
        lines.append(line)
    if pulse.dt_step is not None:
        lines.append(f"DT_STEP={_yaml_value(pulse.dt_step)}")
    else:
        lines.append(f"N_TIMESLICES={pulse.n_timeslices}")
    if pulse.md_layout != "separate":
        lines.append(f"MD_LAYOUT={pulse.md_layout}")
    if pulse.metis is not None:
        if "mode" in pulse.metis:
            lines.append(f"METIS_MODE={pulse.metis['mode']}")
        if "nbt" in pulse.metis:
            lines.append(f"METIS_NBT={pulse.metis['nbt']}")
    lines.append(
        "# simulation window (time.t_start/t_end), only for the preparation log"
    )
    lines.append(f"REPORT_T_START={_fmt_time(pulse.t_start)}")
    lines.append(f"REPORT_T_END={_fmt_time(pulse.t_end)}")
    return "\n".join(lines) + "\n"


def _yaml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)
    return str(value)


def torax_config_name(wf: str, case: str) -> str:
    return f"{wf}_{case}_config_torax.py"


def _yaml_scalar(value: object) -> str:
    """One scalar as a YAML value: plain when it reads back unchanged, else quoted."""
    if isinstance(value, bool | int | float):
        return _yaml_value(value)
    text = str(value)
    try:
        plain = yaml.safe_load(text) == text and "\n" not in text
    except yaml.YAMLError:
        plain = False
    # pds-create-case localizes config paths with a line regex that takes the rest of
    # the line verbatim, so a plain (unquoted) path is required there; json.dumps gives
    # a valid YAML double-quoted scalar for everything else.
    return (
        text
        if plain and not text.startswith(("#", " ", "!", "&", "*"))
        else json.dumps(text)
    )


def _yaml_setting(value: object) -> str:
    if isinstance(value, list):
        items = [json.dumps(v) if isinstance(v, str) else _yaml_value(v) for v in value]
        return "[" + ", ".join(items) + "]"
    return _yaml_scalar(value)


@dataclass
class Entry:
    """One setting of a generated override, with the pulse key it comes from."""

    key: str
    value: object
    origin: str


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text())
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    return raw if isinstance(raw, dict) else {}


def workflow_instances(pds_repo: Path, wf: str) -> list[str]:
    """Instance paths of a workflow (``workflows/<wf>/workflow.ymmsl``), nested models
    flattened the way muscle_manager does (``equilibrium.nice``, ``transport.torax``)."""
    raw = _load_yaml_mapping(pds_repo / "workflows" / wf / "workflow.ymmsl")
    models: dict[str, dict[str, Any]] = {}
    if isinstance(raw.get("models"), dict):
        models = raw["models"]
    elif isinstance(raw.get("model"), dict):
        models = {str(raw["model"].get("name", wf)): raw["model"]}

    def components(model: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        comps = model.get("components") or {}
        if isinstance(comps, dict):
            return [(str(k), v or {}) for k, v in comps.items()]
        return [(str(c.get("name")), c) for c in comps if isinstance(c, dict)]

    used = {
        str(comp.get("implementation"))
        for model in models.values()
        for _, comp in components(model)
    }
    roots = [name for name in models if name not in used]
    root = wf if wf in models else (roots[0] if len(roots) == 1 else None)
    if root is None:
        raise ConfigError(
            f"workflows/{wf}/workflow.ymmsl: cannot find the root model "
            f"(models: {', '.join(models) or 'none'})"
        )
    out: list[str] = []

    def walk(model: dict[str, Any], prefix: str) -> None:
        for name, comp in components(model):
            path = f"{prefix}{name}"
            impl = str(comp.get("implementation"))
            if impl in models:
                walk(models[impl], f"{path}.")
            else:
                out.append(path)

    walk(models[root], "")
    return out


def workflow_settings(pds_repo: Path, wf: str) -> dict[str, Any]:
    """The ``settings:`` of ``workflows/<wf>/settings.ymmsl`` (raw, ${...} kept)."""
    path = pds_repo / "workflows" / wf / "settings.ymmsl"
    if not path.is_file():
        return {}
    raw = _load_yaml_mapping(path).get("settings") or {}
    return {str(k): v for k, v in raw.items()} if isinstance(raw, dict) else {}


def _is_config_key(key: str) -> bool:
    return key.rsplit(".", 1)[-1] in CONFIG_KEY_SUFFIXES and "." in key


def _referenced_text(pds_repo: Path, key: str, value: object) -> str:
    """Content of the config file a ``*.xml_path``-like setting points at, else ''."""
    if not _is_config_key(key) or not isinstance(value, str):
        return ""
    path = Path(value.replace("${PDS_REPO}", str(pds_repo)))
    try:
        return path.read_text() if path.is_file() else ""
    except OSError:
        return ""


def _setting_prefixes(instances: list[str]) -> set[str]:
    """Every instance path and every ancestor path (``equilibrium`` for
    ``equilibrium.nice``): libmuscle resolves ``<prefix>.<setting>`` for all of them."""
    prefixes: set[str] = set()
    for inst in instances:
        parts = inst.split(".")
        prefixes.update(".".join(parts[:i]) for i in range(1, len(parts) + 1))
    return prefixes


def check_settings(pulse: Pulse, pds_repo: Path) -> None:
    """Validate the ``settings:`` pass-through against the workflows' definitions."""
    for wf, items in pulse.settings.items():
        instances = workflow_instances(pds_repo, wf)
        prefixes = _setting_prefixes(instances)
        generic = workflow_settings(pds_repo, wf)
        generated = {
            e.key: e.origin
            for e in generated_entries(pulse, wf)
            if e.origin != ORIGIN_CASE_NAME
        }
        for key in items:
            where = f"{pulse.path}: settings.{wf}.{key}"
            if key in generated:
                raise ConfigError(
                    f"{where}: this setting is controlled by the pulse key "
                    f"{generated[key].removeprefix('pulse: ')}; set that key instead"
                )
            if key.startswith(RESERVED_SETTING_PREFIX) or key in generic:
                continue
            parts = key.split(".")
            if not any(".".join(parts[:i]) in prefixes for i in range(1, len(parts))):
                raise ConfigError(
                    f"{where}: not a setting of an instance of {wf} (instances: "
                    f"{', '.join(instances)}) nor a key of workflows/{wf}/"
                    "settings.ymmsl nor a MUSCLE3 reserved muscle_* setting"
                )


def _shot_dependent(pulse: Pulse, pds_repo: Path, wf: str) -> list[Entry]:
    """With case != shot: the settings.ymmsl values containing ${SHOT}, made explicit."""
    if pulse.case == str(pulse.shot):
        return []
    passed = pulse.settings.get(wf, {})
    out: list[Entry] = []
    for key, value in workflow_settings(pds_repo, wf).items():
        if key in passed or not isinstance(value, str):
            continue
        if "${SHOT}" in value:
            out.append(
                Entry(key, value.replace("${SHOT}", str(pulse.shot)), ORIGIN_CASE_NAME)
            )
        elif "${SHOT}" in _referenced_text(pds_repo, key, value):
            raise ConfigError(
                f"{pulse.path}: case {pulse.case} differs from shot {pulse.shot}, but "
                f"the config file of {wf} setting {key} ({value}) contains ${{SHOT}}, "
                "which bin/pds-create-case replaces with the case name; replace it "
                f"through settings.{wf}.{key} (a copy under cases/pulses/files/ with "
                "the shot number written in)"
            )
    return out


def _check_combined_layout(pulse: Pulse, pds_repo: Path, wf: str) -> None:
    """A combined-layout shot must redirect every data/in_md read of the workflow."""
    if pulse.md_layout != "combined" or wf not in SEPARATE_MD_WORKFLOWS:
        return
    passed = pulse.settings.get(wf, {})
    for key, value in workflow_settings(pds_repo, wf).items():
        if key in passed or not isinstance(value, str):
            continue
        if "data/in_md" in value or "data/in_md" in _referenced_text(
            pds_repo, key, value
        ):
            raise ConfigError(
                f"{pulse.path}: prepare.md_layout is 'combined' (no data/in_md) but "
                f"{wf} setting {key} of workflows/{wf}/settings.ymmsl reads data/in_md"
                f"{' through its config file' if 'data/in_md' not in value else ''}; "
                f"replace it through settings.{wf}.{key} (see cases/pulses/105073.yaml)"
            )


def generated_entries(pulse: Pulse, wf: str) -> list[Entry]:
    """The override settings derived from the pulse keys (not the pass-through)."""
    entries: list[Entry] = []
    window = [("t_min", pulse.t_start), ("t_max", pulse.t_end)]
    window_origin = "pulse: time.t_start / time.t_end"
    if wf == "inverse_convergence":
        entries += [Entry(f"loop.{k}", v, window_origin) for k, v in window]
        if pulse.inverse_dt is not None:
            entries.append(
                Entry(
                    "transport.torax.fixed_dt",
                    pulse.inverse_dt,
                    "pulse: time.inverse_dt",
                )
            )
        entries += [
            Entry(f"loop.{k}", v, f"pulse: inverse_convergence.{k}")
            for k, v in pulse.loop.items()
        ]
    elif wf == "prescribed_transport":
        entries += [Entry(f"source.{k}", v, window_origin) for k, v in window]
    elif wf == "evolutive_controller":
        if pulse.forward_source is not None:
            entries.append(
                Entry(
                    "source.source_uri",
                    pulse.forward_source,
                    "pulse: time.forward_source",
                )
            )
        entries.append(
            Entry("source.t_min", pulse.forward_t_start, "pulse: time.forward_t_start")
        )
        entries.append(
            Entry(
                "source.t_max",
                pulse.forward_load_t_end,
                "pulse: time.forward_load_t_end",
            )
        )
        if pulse.forward_source_dt is not None:
            entries.append(
                Entry(
                    "source.dt",
                    pulse.forward_source_dt,
                    "pulse: time.forward_source_dt",
                )
            )
        if pulse.forward_dt is not None:
            entries += [
                Entry(k, pulse.forward_dt, "pulse: time.forward_dt")
                for k in ("torax.fixed_dt", "nice_evo_rd.dt", "nice_evo_rd.t_interval")
            ]
        entries += [
            Entry(k, pulse.forward_t_end, "pulse: time.forward_t_end")
            for k in ("torax.t_final", "nice_evo_rd.t_end")
        ]
    elif wf in METIS_SOURCE:
        src = METIS_SOURCE[wf]
        entries += [Entry(f"{src}.{k}", v, window_origin) for k, v in window]
    else:  # pragma: no cover - rejected by load_pulse
        raise ConfigError(f"unsupported workflow {wf}")
    instance = TORAX_INSTANCE[wf]
    if pulse.calibration_model is not None and instance is not None:
        entries.append(
            Entry(
                f"{instance}.python_config_module",
                f"${{PDS_REPO}}/cases/overrides/{torax_config_name(wf, pulse.case)}",
                "pulse: transport_calibration",
            )
        )
    return entries


def override_entries(pulse: Pulse, wf: str, pds_repo: Path) -> list[Entry]:
    """Every setting of ``cases/overrides/<wf>_<case>.ymmsl``, in file order."""
    _check_combined_layout(pulse, pds_repo, wf)
    no_torax = TORAX_INSTANCE.get(wf) is None
    if no_torax and (
        pulse.inverse_dt is not None or pulse.calibration_model is not None
    ):
        logger.info(
            "%s has no TORAX: time.inverse_dt and transport_calibration do not "
            "apply to it",
            wf,
        )
    entries = generated_entries(pulse, wf)
    keys = {e.key for e in entries}
    entries += [e for e in _shot_dependent(pulse, pds_repo, wf) if e.key not in keys]
    entries += [
        Entry(k, v, ORIGIN_PASS_THROUGH) for k, v in pulse.settings.get(wf, {}).items()
    ]
    return entries


# Comment written above each group of generated settings, by origin.
_GROUP_COMMENTS = {
    "pulse: time.t_start / time.t_end": {
        "inverse_convergence": "time.t_start / time.t_end: slices of the prepared grid "
        "the loop visits",
        "prescribed_transport": "time.t_start / time.t_end: time range loaded by the "
        "source",
        "metis_from_dina": "time.t_start / time.t_end: time range streamed to METIS, "
        "one native slice per message",
        "metis_nice_inverse_from_dina": "time.t_start / time.t_end: time range "
        "streamed to METIS, one native slice per message",
    },
    "pulse: time.inverse_dt": "time.inverse_dt: TORAX step inside each slice interval",
    "pulse: time.forward_source": "time.forward_source: inverse result the forward run "
    "starts from",
    "pulse: time.forward_t_start": "time.forward_t_start: first forward time loaded by "
    "the source",
    "pulse: time.forward_load_t_end": "time.forward_load_t_end: end of the time range "
    "loaded by the source",
    "pulse: time.forward_source_dt": "time.forward_source_dt: resampling step of the "
    "source",
    "pulse: time.forward_dt": "time.forward_dt: TORAX and NICE evolutive step",
    "pulse: time.forward_t_end": "time.forward_t_end: end of the forward simulation",
    "pulse: transport_calibration": "transport_calibration: calibrated TORAX config "
    "generated alongside",
    ORIGIN_CASE_NAME: "case differs from shot: ${SHOT}-dependent settings of the "
    "workflow made explicit",
    ORIGIN_PASS_THROUGH: "settings: pass-through from the pulse file",
}


def _group_comment(origin: str, wf: str) -> str:
    if origin.startswith("pulse: inverse_convergence."):
        return "inverse_convergence: outer loop tuning"
    comment = _GROUP_COMMENTS.get(origin, origin)
    if isinstance(comment, dict):
        return comment.get(wf, origin)
    return comment


def render_override(pulse: Pulse, wf: str, mark: str, entries: list[Entry]) -> str:
    """cases/overrides/<wf>_<case>.ymmsl."""
    lines = [mark, "ymmsl_version: v0.2"]
    lines.append(f"# Per-shot settings for {wf} on {pulse.case} (shot {pulse.shot}),")
    lines.append(f"# stacked after the generic workflows/{wf}/settings.ymmsl by")
    lines.append("# bin/pds-create-case.")
    if pulse.description:
        lines.append(f"# {pulse.description}")
    lines.append("settings:")
    if not entries:
        lines[-1] = "settings: {}"
    previous: str | None = None
    for e in entries:
        comment = _group_comment(e.origin, wf)
        if comment != previous:
            lines.append(f"  # {comment}")
            previous = comment
        lines.append(f"  {e.key}: {_yaml_setting(e.value)}")
    return "\n".join(lines) + "\n"


def _py_literal(value: Table) -> list[str]:
    """Items of a multiplier rendered as Python literal pieces."""
    if isinstance(value, dict):
        return [f"{float(t)!r}: {float(v)!r}" for t, v in value.items()]
    return [repr(float(value))]


def _py_assignment(key: str, value: Table) -> str:
    """One ``CONFIG["transport"][key] = ...`` statement, in ruff format style."""
    lhs = f'CONFIG["transport"]["{key}"] = '
    items = _py_literal(value)
    if not isinstance(value, dict):
        return lhs + items[0]
    one_line = lhs + "{" + ", ".join(items) + "}"
    if len(one_line) <= LINE_LENGTH:
        return one_line
    body = "".join(f"    {item},\n" for item in items)
    return lhs + "{\n" + body + "}"


def render_torax_config(pulse: Pulse, wf: str, generic: str, mark: str) -> str:
    """Generic config_torax.py plus the calibration assignments."""
    text = generic if generic.endswith("\n") else generic + "\n"
    lines = [
        "",
        mark,
        f"# transport_calibration of shot {pulse.shot}: switch the generic transport "
        "block",
        "# to the calibrated model; unset multipliers keep the TORAX default 1.0.",
        f'CONFIG["transport"]["model_name"] = "{pulse.calibration_model}"',
    ]
    lines.extend(_py_assignment(k, v) for k, v in pulse.multipliers.items())
    return f"{mark}\n{text}" + "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- actions


@dataclass
class Output:
    path: Path
    content: str


def source_env_output(pulse: Pulse, pds_repo: Path, scenarios_repo: Path) -> Output:
    """The source.env that would be written, without touching the disk."""
    return Output(
        scenarios_repo / str(pulse.shot) / "source.env",
        render_source_env(pulse, marker(pulse, pds_repo)),
    )


def workflow_outputs(pulse: Pulse, wf: str, pds_repo: Path) -> list[Output]:
    """The files that would be written for one workflow, without touching the disk."""
    mark = marker(pulse, pds_repo)
    overrides = overrides_dir(pds_repo)
    entries = override_entries(pulse, wf, pds_repo)
    outputs = [
        Output(
            overrides / override_name(wf, pulse.case),
            render_override(pulse, wf, mark, entries),
        )
    ]
    if pulse.calibration_model is not None and TORAX_INSTANCE[wf] is not None:
        generic_path = pds_repo / "workflows" / wf / "config_torax.py"
        try:
            generic = generic_path.read_text()
        except OSError as exc:
            raise ConfigError(f"cannot read {generic_path}: {exc}") from exc
        outputs.append(
            Output(
                overrides / torax_config_name(wf, pulse.case),
                render_torax_config(pulse, wf, generic, mark),
            )
        )
    return outputs


def overrides_dir(pds_repo: Path) -> Path:
    return pds_repo / "cases" / "overrides"


def override_name(wf: str, case: str) -> str:
    return f"{wf}_{case}.ymmsl"


def _has_marker(path: Path) -> bool:
    with path.open() as f:
        return f.readline().startswith(MARKER_PREFIX)


def check_overwrite(outputs: list[Output], force: bool) -> None:
    """Refuse to replace a file that bin/pds-configure did not write."""
    for out in outputs:
        if not out.path.exists() or force or _has_marker(out.path):
            continue
        if out.path.parent.name == "overrides":
            raise ConfigError(hand_written_message(out.path))
        raise ConfigError(
            f"{out.path} exists and was not generated by bin/pds-configure "
            "(no marker line); move it away or rerun with --force"
        )


def hand_written_message(path: Path) -> str:
    stem = path.name.removesuffix(".ymmsl")
    case = stem.split("_", 1)[1] if "_" in stem else "<case>"
    for wf in SUPPORTED_WORKFLOWS:
        if stem.startswith(f"{wf}_"):
            case = stem[len(wf) + 1 :]
    return (
        f"{path} exists without the GENERATED marker: hand-written overrides are no "
        f"longer supported; move its settings into cases/pulses/{case}.yaml (settings: "
        "section, companion files under cases/pulses/files/) and delete it (or rerun "
        "with --force to overwrite it)"
    )


def remove_stale_override(pulse: Pulse, wf: str, pds_repo: Path) -> None:
    """A workflow not listed in the pulse file must have no override left behind."""
    overrides = overrides_dir(pds_repo)
    for name in (override_name(wf, pulse.case), torax_config_name(wf, pulse.case)):
        path = overrides / name
        if not path.is_file():
            continue
        if not _has_marker(path):
            raise ConfigError(hand_written_message(path))
        path.unlink()
        logger.info(
            "removed stale generated %s (%s is not in the workflows of %s)",
            path,
            wf,
            pulse.path,
        )


def forward_source_uri(pulse: Pulse, pds_repo: Path) -> str:
    """Effective evolutive_controller source URI, with PDS_REPO / SHOT expanded."""
    uri = pulse.forward_source or FORWARD_SOURCE_DEFAULT
    return uri.replace("${PDS_REPO}", str(pds_repo)).replace("${SHOT}", str(pulse.shot))


def _local_hdf5_path(uri: str) -> Path | None:
    """The directory of an ``imas:hdf5?path=<dir>`` URI, else None."""
    m = re.fullmatch(r"imas:hdf5\?path=([^;&]+)", uri.strip())
    if m is None:
        return None
    return Path(os.path.expandvars(m.group(1)))


def _equilibrium_times(uri: str) -> list[float]:
    """equilibrium.time of a local HDF5 entry, read lazily and read-only."""
    os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")
    try:
        import imas  # only needed for this check

        with imas.DBEntry(uri, "r") as entry:
            eq = entry.get("equilibrium", lazy=True, autoconvert=False)
            times = [float(t) for t in eq.time]
    except Exception as exc:  # any failure to read is a config error
        raise ConfigError(
            f"forward source {uri}: cannot read equilibrium.time: {exc}"
        ) from exc
    if not times:
        raise ConfigError(f"forward source {uri}: equilibrium.time is empty")
    return times


def check_forward_window(pulse: Pulse, pds_repo: Path) -> None:
    """Check [forward_t_start, forward_t_end] against the inverse result it reads."""
    a, b = pulse.forward_t_start, pulse.forward_t_end
    uri = forward_source_uri(pulse, pds_repo)
    path = _local_hdf5_path(uri)
    if path is None or not (path / "master.h5").is_file():
        reason = "not a local HDF5 entry" if path is None else "does not exist yet"
        logger.warning(
            "warning: cannot check the forward window against %s (%s); make sure it "
            "covers [%g, %g]; rerun bin/pds-configure after the inverse_convergence "
            "run for a hard check",
            uri,
            reason,
            a,
            b,
        )
        return
    times = _equilibrium_times(uri)
    first, last = times[0], times[-1]
    if pulse.forward_load_t_end > last + TIME_TOL:
        logger.warning(
            "warning: time.forward_load_t_end = %g is beyond the last slice (%g s) of "
            "the forward source %s; the source loads up to that slice",
            pulse.forward_load_t_end,
            last,
            uri,
        )
    if a < first - TIME_TOL or b > last + TIME_TOL:
        raise ConfigError(
            f"{pulse.path}: forward window [{a:g}, {b:g}] "
            "(time.forward_t_start / time.forward_t_end) is not covered by the forward "
            f"source {uri}, whose equilibrium spans [{first:g}, {last:g}] s "
            f"({len(times)} slices)"
        )
    start = next(t for t in times if t >= a - TIME_TOL)
    logger.info(
        "evolutive_controller: first native slice of the forward window is "
        "t = %r s of %s (%d slices in [%g, %g] s)",
        start,
        uri,
        len(times),
        first,
        last,
    )
    if abs(start - a) > TIME_TOL:
        before = max((t for t in times if t < a), default=None)
        nearest = ", ".join(f"{t!r}" for t in (before, start) if t is not None)
        logger.warning(
            "warning: time.forward_t_start = %g is not a native slice of %s (nearest "
            "native slices: %s s); the source then starts from the next native slice "
            "or, with time.forward_source_dt set, from a state interpolated at "
            "forward_t_start -- seeding the forward run from a non-native/other slice "
            "diverged on 105073 (see cases/pulses/105073.yaml); prefer one of the "
            "native values",
            a,
            uri,
            nearest,
        )


def write_outputs(outputs: list[Output]) -> None:
    for out in outputs:
        out.path.parent.mkdir(parents=True, exist_ok=True)
        out.path.write_text(out.content)
        logger.info("wrote %s", out.path)


def prepare_command(pulse: Pulse, pds_repo: Path) -> list[str]:
    cmd = [str(pds_repo / "preprocessing" / "prepare"), str(pulse.shot)]
    if pulse.metis is not None:
        cmd.append("--metis")
    return cmd


def create_command(wf: str, pulse: Pulse, pds_repo: Path) -> list[str]:
    return [str(pds_repo / "bin" / "pds-create-case"), "-f", wf, pulse.case]


def _run(cmd: list[str], env: dict[str, str], capture: bool = False) -> str:
    logger.info("running %s", " ".join(cmd))
    result = subprocess.run(
        cmd, env=env, check=False, text=True, capture_output=capture
    )
    if result.returncode != 0:
        detail = ""
        if capture and result.stderr:
            # The last lines carry the error; a MATLAB preprocess can print thousands.
            tail = result.stderr.strip().splitlines()[-20:]
            detail = ":\n  " + "\n  ".join(tail)
        raise ConfigError(f"{cmd[0]} failed with exit code {result.returncode}{detail}")
    return result.stdout if capture else ""


def run_create(
    pulse: Pulse,
    workflows: list[str],
    pds_repo: Path,
    scenarios_repo: Path,
    env: dict[str, str],
    failed: dict[str, str],
) -> None:
    """Create one case per workflow; a failing workflow is recorded in ``failed``."""
    check = pds_repo / "preprocessing" / "check_scenario.py"
    # The overrides were just written: pds-create-case must not regenerate them.
    env = dict(env, PDS_CONFIGURE_NO_REGEN="1")
    for wf in workflows:
        try:
            out = _run(create_command(wf, pulse, pds_repo), env, capture=True)
            lines = [line for line in out.splitlines() if line.strip()]
            if not lines:
                raise ConfigError(f"pds-create-case printed no case dir for {wf}")
        except ConfigError as exc:
            _fail_workflow(failed, wf, exc)
            continue
        case_dir = Path(lines[-1].strip())
        print(f"{wf}: case {case_dir}")
        # bin/pds-run-case.sbatch sources case.env right before postprocess.sh, so the
        # post-processing reads this data root without SCENARIOS_REPO exported at submit.
        with (case_dir / "case.env").open("a") as f:
            f.write(
                f"export SCENARIOS_REPO={shlex.quote(str(scenarios_repo.resolve()))}\n"
            )
        try:
            (case_dir / "settings_origin.txt").write_text(
                explain_table(pulse, wf, pds_repo, [])
            )
        except ConfigError as exc:
            logger.warning("settings_origin.txt not written for %s: %s", wf, exc)
        if not check.exists():
            logger.warning("%s not found; skipping the configuration check plot", check)
            continue
        result = subprocess.run(
            [
                sys.executable,
                str(check),
                str(pulse.shot),
                "--case",
                str(case_dir),
                "--out",
                str(case_dir / f"check_{pulse.shot}.png"),
            ],
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            logger.warning(
                "check_scenario.py exited with code %d for %s; continuing "
                "(the case itself was created)",
                result.returncode,
                wf,
            )
        for line in result.stdout.splitlines():
            if line.startswith(("OK", "WARN")):
                print(f"  {line}")


def _fail_workflow(failed: dict[str, str], wf: str, exc: ConfigError) -> None:
    """Report a per-workflow failure; the caller skips that workflow."""
    failed[wf] = str(exc)
    sys.stdout.flush()
    print(f"pds-configure: error: {wf}: {exc}", file=sys.stderr)
    print(f"pds-configure: {wf}: skipped, continuing with the others", file=sys.stderr)


# --------------------------------------------------------------------------- explain


def _ymmsl_settings(text: str, where: str) -> dict[str, Any]:
    """The ``settings:`` of a yMMSL document, loaded with the ymmsl library (falling
    back to a plain YAML read when ymmsl is not importable)."""
    try:
        import ymmsl
        from ymmsl.v0_2 import Configuration

        cfg = ymmsl.load_as(Configuration, text)
        return {str(k): cfg.settings[k] for k in cfg.settings}
    except ImportError:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"{where}: invalid YAML: {exc}") from exc
        items = (raw or {}).get("settings") if isinstance(raw, dict) else None
        return {str(k): v for k, v in (items or {}).items()}
    except Exception as exc:  # ymmsl raises its own error types
        raise ConfigError(f"{where}: cannot load settings: {exc}") from exc


def _read(path: Path) -> str:
    try:
        return path.read_text()
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc


def explain_rows(
    pulse: Pulse, wf: str, pds_repo: Path, overlays: list[Path]
) -> list[tuple[str, Any, str]]:
    """Every effective setting of the case ``<wf>_<case>`` with its origin, in the
    stacking order of bin/pds-create-case / bin/pds-run-case (later files win)."""
    wf_dir = pds_repo / "workflows" / wf
    merged: dict[str, tuple[Any, str]] = {}
    for name, origin in (
        ("workflow.ymmsl", ORIGIN_WORKFLOW),
        ("settings.ymmsl", ORIGIN_SETTINGS),
    ):
        path = wf_dir / name
        if path.is_file():
            for key, value in _ymmsl_settings(_read(path), str(path)).items():
                merged[key] = (value, origin)
    entries = override_entries(pulse, wf, pds_repo)
    rendered = _ymmsl_settings(
        render_override(pulse, wf, marker(pulse, pds_repo), entries), "override"
    )
    for e in entries:
        merged[e.key] = (rendered.get(e.key, e.value), e.origin)
    for overlay in overlays:
        for key, value in _ymmsl_settings(_read(overlay), str(overlay)).items():
            merged[key] = (value, f"overlay: {overlay}")
    return [(key, value, origin) for key, (value, origin) in merged.items()]


def _shown(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "[" + ", ".join(_shown(v) for v in value) + "]"
    return _yaml_value(value)


def explain_table(pulse: Pulse, wf: str, pds_repo: Path, overlays: list[Path]) -> str:
    rows = [
        (k, _shown(v), o) for k, v, o in explain_rows(pulse, wf, pds_repo, overlays)
    ]
    head = ("setting", "value", "origin")
    widths = [max(len(r[i]) for r in [head, *rows]) for i in range(3)]
    lines = [
        f"# {wf} on {pulse.case} (shot {pulse.shot}), from {pulse.path}: effective "
        "settings and their origin",
        "# values are raw: ${PDS_REPO}/${SCENARIOS_REPO}/${SHOT}/${CASE_DIR} are "
        "substituted by bin/pds-create-case, config paths localized into config/",
    ]
    fmt = f"{{:<{widths[0]}}} | {{:<{widths[1]}}} | {{}}"
    lines.append(fmt.format(*head))
    lines.append("-" * widths[0] + "-+-" + "-" * widths[1] + "-+-" + "-" * widths[2])
    lines.extend(fmt.format(*r) for r in rows)
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pds-configure",
        description="Generate the shot-specific PDS files from a pulse file "
        "(cases/pulses/<shot>.yaml).",
    )
    parser.add_argument(
        "pulse", type=Path, help="pulse file, e.g. cases/pulses/105033.yaml"
    )
    parser.add_argument(
        "--workflow",
        action="append",
        metavar="WF",
        help="only this workflow (repeatable; must be listed in the pulse file)",
    )
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="run preprocessing/prepare afterwards",
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="run bin/pds-create-case and preprocessing/check_scenario.py afterwards",
    )
    parser.add_argument(
        "--overrides-only",
        action="store_true",
        help="write the overrides only, never source.env (bin/pds-create-case uses it; "
        "a --workflow not listed in the pulse file then generates nothing)",
    )
    parser.add_argument(
        "--force", action="store_true", help="overwrite files without the marker line"
    )
    parser.add_argument(
        "--explain",
        nargs="?",
        const="*",
        metavar="WF",
        help="print the effective settings of each selected workflow (or only WF) with "
        "their origin, and exit",
    )
    parser.add_argument(
        "--overlay",
        action="append",
        type=Path,
        default=[],
        metavar="FILE",
        help="run-time overlay ymmsl to include in --explain (repeatable)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be done, change nothing",
    )
    parser.add_argument(
        "--print-t-list",
        action="store_true",
        help="print the post-processing plot times and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="pds-configure: %(message)s")
    # The ymmsl loader (yatiml) logs every YAML node at INFO; keep it quiet.
    for name in ("yatiml", "ymmsl"):
        logging.getLogger(name).setLevel(logging.WARNING)
    pds_repo = Path(
        os.environ.get("PDS_REPO") or Path(__file__).resolve().parent.parent
    )
    scenarios_repo = Path(os.environ.get("SCENARIOS_REPO") or pds_repo / "scenarios")
    try:
        pulse = load_pulse(args.pulse)
        if args.print_t_list:
            print(" ".join(_fmt_time(t) for t in pulse.t_list))
            return 0
        check_settings(pulse, pds_repo)
        selected = pulse.workflows
        if args.workflow:
            for wf in args.workflow:
                if wf in pulse.workflows:
                    continue
                if not args.overrides_only:
                    raise ConfigError(
                        f"--workflow {wf}: not in the workflows of {pulse.path} "
                        f"({', '.join(pulse.workflows)})"
                    )
                logger.info(
                    "%s is not in the workflows of %s: no override generated",
                    wf,
                    pulse.path,
                )
                if not args.dry_run:
                    remove_stale_override(pulse, wf, pds_repo)
            selected = [wf for wf in pulse.workflows if wf in args.workflow]
        if args.explain is not None:
            explained = selected
            if args.explain != "*":
                if args.explain not in pulse.workflows:
                    raise ConfigError(
                        f"--explain {args.explain}: not in the workflows of "
                        f"{pulse.path} ({', '.join(pulse.workflows)})"
                    )
                explained = [args.explain]
            for wf in explained:
                print(explain_table(pulse, wf, pds_repo, args.overlay), end="")
            return 0
        outputs: list[Output] = []
        if not args.overrides_only:
            source_env = source_env_output(pulse, pds_repo, scenarios_repo)
            check_overwrite([source_env], args.force)
            outputs.append(source_env)
        # Per-workflow generation and checks: a failure skips that workflow only.
        failed: dict[str, str] = {}
        workflows: list[str] = []
        for wf in selected:
            try:
                wf_outputs = workflow_outputs(pulse, wf, pds_repo)
                if wf == "evolutive_controller":
                    check_forward_window(pulse, pds_repo)
                check_overwrite(wf_outputs, args.force)
            except ConfigError as exc:
                _fail_workflow(failed, wf, exc)
                continue
            workflows.append(wf)
            outputs.extend(wf_outputs)
        env = dict(os.environ)
        env.update(
            PDS_REPO=str(pds_repo),
            SCENARIOS_REPO=str(scenarios_repo),
            PREPARE_PYTHON=env.get("PREPARE_PYTHON", sys.executable),
        )
        prepare_env = dict(env, IMAS_VERSION=pulse.dd_version)
        if args.dry_run:
            for out in outputs:
                print(f"==> {out.path}")
                print(out.content, end="")
            if args.prepare:
                cmd = prepare_command(pulse, pds_repo)
                print(
                    f"would run: IMAS_VERSION={pulse.dd_version} "
                    f"SCENARIOS_REPO={scenarios_repo} " + " ".join(cmd)
                )
            if args.create:
                if not selected:
                    print("would create nothing: workflows is empty (preparation only)")
                for wf in workflows:
                    cmd = create_command(wf, pulse, pds_repo)
                    print(
                        "would run: " + " ".join(cmd) + " + case.env SCENARIOS_REPO"
                        " + preprocessing/check_scenario.py"
                    )
        else:
            write_outputs(outputs)
            if args.prepare:
                _run(prepare_command(pulse, pds_repo), prepare_env)
            if args.create:
                if not selected:
                    print(
                        f"{pulse.path}: workflows is empty (preparation only); "
                        "--create has nothing to create"
                    )
                run_create(pulse, workflows, pds_repo, scenarios_repo, env, failed)
    except ConfigError as exc:
        print(f"pds-configure: error: {exc}", file=sys.stderr)
        return 1
    if failed:
        sys.stdout.flush()
        print(
            f"pds-configure: failed workflows: {', '.join(failed)} "
            f"(succeeded: {', '.join(wf for wf in selected if wf not in failed) or 'none'})",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
