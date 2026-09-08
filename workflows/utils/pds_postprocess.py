#!/usr/bin/env python3
"""Generic post-processing of a PDS run.

Everything done here is derived from the flattened ``configuration.ymmsl`` that
muscle_manager writes into the run directory, so the same code serves every
workflow -- hand-written or generated on the fly -- without a per-workflow copy:

* the sinks of the run are the components carrying a ``<component>.sink_uri``
  setting; their relative ``path=`` is resolved against the instance work
  directory ``<run dir>/instances/<component>/workdir``;
* what a sink holds is read off the conduits: each of its input ports is traced
  backwards through the coupling graph until a component whose implementation is
  an equilibrium or a transport code is reached (pass-through actors such as a
  load balancer, an outer convergence loop or a state splitter are transparent);
* the inputs of the run are the IMAS URIs appearing in the settings (source
  URIs, machine-description settings) plus the ``globals.imports`` of a
  waveform-editor configuration referenced by a ``*.waveforms`` setting;
* the same waveform-editor configuration says which heating system the imported
  heating stands for (it renames ``core_sources/source(N)/identifier/name``), so
  an input carrying only an aggregated ``auxiliary`` power can still be exported
  as that system's power (``--auxiliary-heating`` of the IMAS export).

From that it writes, into the run directory:

* ``imas_out``            -- one IMAS data entry for the whole run, with a summary
                             IDS (built by workflows/utils/pds_imas_export.py);
* ``pds_git_state.txt``   -- exact state of the repository and of the software stack;
* ``README_REPRODUCE.md`` -- how to re-run this exact case;
* ``simdb_manifest.yaml`` -- SimDB manifest listing inputs and outputs;
* ``plots/plotpulseschedule/`` -- figure of the exported pulse schedule with the
                             scenario inputs overlaid (workflows/utils/pdsplot).

Every step is best-effort: a failure is logged and the remaining steps still run.
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

LOGGER = logging.getLogger("pds-postprocess")

# ---------------------------------------------------------------------------
# Which implementation is which kind of code.
# ---------------------------------------------------------------------------
# Matched against the last dotted segment of the implementation name, lowercased
# (``lib.easybuild_programs.nice_inv`` -> ``nice_inv``).
EQUILIBRIUM_IMPLEMENTATIONS = {
    "nice", "nice_inv", "nice_inverse", "nice_evo", "nice_evo_rd",
    "chease", "feeqs", "equilibrium",
}
TRANSPORT_IMPLEMENTATIONS = {
    "torax", "metis", "transport", "jintrac", "ets",
}
# Fallback, used when the implementation name says nothing: the code that wrote
# the IDS names itself in ``<ids>/code/name``.
EQUILIBRIUM_CODE_NAMES = {"NICE", "CHEASE", "FEEQS"}
TRANSPORT_CODE_NAMES = {"TORAX", "METIS", "JINTRAC", "ETS"}

# Trailing tokens of a port name that describe the MUSCLE3 wiring rather than
# the IDS carried: equilibrium_in_f, core_profiles_f_init, equilibrium_o_i,
# pf_active_gather, equilibrium_init_out, equilibrium_target_out_f ...
PORT_TOKENS = {"in", "out", "f", "s", "i", "o", "init", "gather", "scatter",
               "target"}

# Operators an actor receives on / sends on.
INPUT_OPERATORS = ("f_init", "s")
OUTPUT_OPERATORS = ("o_i", "o_f")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def as_list(value) -> list:
    """A yMMSL port/conduit value is either a list or a space-separated string."""
    if value is None:
        return []
    if isinstance(value, str):
        return value.split()
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(as_list(item))
        return out
    return [str(value)]


def ids_of_port(port: str) -> str:
    """IDS name carried by a port, e.g. ``core_profiles_in_f`` -> ``core_profiles``."""
    parts = port.split("_")
    while len(parts) > 1 and parts[-1] in PORT_TOKENS:
        parts.pop()
    return "_".join(parts)


def uri_path(uri: str):
    """The ``path=`` component of an IMAS URI, or None."""
    match = re.search(r"path=([^?&;#\s]+)", uri or "")
    return match.group(1) if match else None


def with_path(uri: str, path) -> str:
    old = uri_path(uri)
    return uri.replace("path=" + old, "path=" + str(path)) if old else uri


def short_impl(implementation: str) -> str:
    return (implementation or "").rsplit(".", 1)[-1].lower()


def run_git(repo: str, *args) -> str:
    try:
        done = subprocess.run(("git", "-C", repo) + args, capture_output=True,
                              text=True, check=False)
        return done.stdout if done.returncode == 0 else ""
    except OSError as exc:                                    # pragma: no cover
        LOGGER.warning("git %s failed: %s", " ".join(args), exc)
        return ""


# ---------------------------------------------------------------------------
# a. the flattened configuration
# ---------------------------------------------------------------------------
class Configuration:
    """The parts of a flattened configuration.ymmsl this script needs."""

    def __init__(self, path: Path):
        with open(path) as stream:
            document = yaml.safe_load(stream) or {}
        self.path = path
        self.model_name = ""
        self.components: dict = {}
        self.conduits: dict = {}          # receiver endpoint -> sender endpoint
        self.settings: dict = document.get("settings") or {}
        # muscle_manager calls the implementation section "programs" in a
        # flattened file; accept "implementations" too.
        self.programs: dict = (document.get("programs")
                               or document.get("implementations") or {})

        models = document.get("models") or document.get("model") or {}
        if isinstance(models, dict) and "components" in models:
            models = {models.get("name", ""): models}
        for name, model in (models or {}).items():
            self.model_name = self.model_name or str(name)
            for component, spec in (model.get("components") or {}).items():
                self.components[component] = spec or {}
            for sender, receivers in (model.get("conduits") or {}).items():
                for receiver in as_list(receivers):
                    self.conduits[receiver] = sender

    def split_endpoint(self, endpoint: str):
        """``a.b.port`` -> (``a.b``, ``port``), component names may contain dots."""
        parts = endpoint.split(".")
        for index in range(len(parts) - 1, 0, -1):
            component = ".".join(parts[:index])
            if component in self.components:
                return component, ".".join(parts[index:])
        return None, None

    def ports(self, component: str, operators) -> list:
        spec = self.components.get(component) or {}
        ports = spec.get("ports") or {}
        names = []
        for operator in operators:
            names.extend(as_list(ports.get(operator)))
        return names

    def implementation(self, component: str) -> str:
        return (self.components.get(component) or {}).get("implementation", "")

    def trace_producers(self, component: str, port: str) -> list:
        """Components upstream of ``component.port``, nearest first.

        Follows the conduits backwards and keeps walking through every input
        port of an upstream component that carries the same IDS, so that
        pass-through actors (load balancer, convergence loop, state splitter)
        do not hide the code that actually computed the IDS.
        """
        wanted = ids_of_port(port)
        chain, seen_components, seen_endpoints = [], set(), set()
        queue = [(component, port)]
        while queue:
            here, here_port = queue.pop(0)
            endpoint = f"{here}.{here_port}"
            if endpoint in seen_endpoints:
                continue
            seen_endpoints.add(endpoint)
            sender = self.conduits.get(endpoint)
            if not sender:
                continue
            producer, _ = self.split_endpoint(sender)
            if producer is None:
                continue
            if producer not in seen_components:
                seen_components.add(producer)
                chain.append(producer)
            for upstream in self.ports(producer, INPUT_OPERATORS):
                if ids_of_port(upstream) == wanted:
                    queue.append((producer, upstream))
        return chain


# ---------------------------------------------------------------------------
# b/c. sinks, their contents and the role of each sink
# ---------------------------------------------------------------------------
class Sink:
    def __init__(self, component, uri, directory):
        self.component = component
        self.uri = uri
        self.directory = directory
        self.contents = {}      # ids name -> (code component, implementation)
        self.direct = {}        # ids name -> component actually wired to the sink
        self.role = ""

    @property
    def name(self) -> str:
        return self.directory.name


def code_name(uri: str, ids_name: str):
    """``<ids>/code/name`` of an IDS in a data entry, or None."""
    try:
        import imas
    except ImportError:
        return None
    try:
        with imas.DBEntry(uri, "r") as entry:
            ids = entry.get(ids_name, lazy=True)
            name = str(ids.code.name)
            return name or None
    except Exception:                    # any missing IDS / backend problem
        return None


def kind_of(implementation: str) -> str:
    stem = short_impl(implementation)
    if stem in EQUILIBRIUM_IMPLEMENTATIONS:
        return "equilibrium"
    if stem in TRANSPORT_IMPLEMENTATIONS:
        return "transport"
    return ""


def discover_sinks(config: Configuration, run_dir: Path) -> list:
    sinks = []
    for key, value in config.settings.items():
        if not key.endswith(".sink_uri") or not isinstance(value, str):
            continue
        component = key[: -len(".sink_uri")]
        if component not in config.components:
            LOGGER.warning("sink setting %s has no component, ignored", key)
            continue
        path = uri_path(value)
        if path is None:
            LOGGER.warning("sink %s has no path= in %r, ignored", component, value)
            continue
        directory = Path(path)
        if not directory.is_absolute():
            base = run_dir / "instances" / component / "workdir"
            directory = Path(os.path.normpath(base / directory))
        if not directory.is_dir():
            LOGGER.warning("sink %s -> %s does not exist, ignored",
                           component, directory)
            continue
        sinks.append(Sink(component, with_path(value, directory), directory))
    return sinks


def fill_sink_contents(config: Configuration, sinks: list) -> None:
    for sink in sinks:
        for port in config.ports(sink.component, INPUT_OPERATORS):
            ids_name = ids_of_port(port)
            chain = config.trace_producers(sink.component, port)
            if not chain:
                continue
            # The component wired to the sink is often a pass-through (load
            # balancer, convergence loop, state splitter, controller); the code
            # that computed the IDS is the first one upstream that is one.
            producer = chain[0]
            for candidate in chain:
                if kind_of(config.implementation(candidate)):
                    producer = candidate
                    break
            sink.contents[ids_name] = (producer, config.implementation(producer))
            sink.direct[ids_name] = chain[0]


def assign_roles(sinks: list) -> tuple:
    """Return (equilibrium sink, transport sink, transport-extras sink)."""
    equilibrium = transport = transport_only_extras = None

    candidates = [s for s in sinks
                  if "equilibrium" in s.contents
                  and kind_of(s.contents["equilibrium"][1]) == "equilibrium"]
    if not candidates:
        # Fallback: ask the stored IDS which code wrote it.
        for sink in sinks:
            if "equilibrium" not in sink.contents:
                continue
            written_by = code_name(sink.uri, "equilibrium")
            if written_by and written_by.upper() in EQUILIBRIUM_CODE_NAMES:
                LOGGER.info("sink %s: equilibrium code recognised from "
                            "equilibrium/code/name = %s", sink.name, written_by)
                candidates.append(sink)
    if candidates:
        if len(candidates) > 1:
            LOGGER.info("several equilibrium sinks (%s), taking the first",
                        ", ".join(s.name for s in candidates))
        equilibrium = candidates[0]
        equilibrium.role = "equilibrium"

    candidates = [s for s in sinks
                  if "core_profiles" in s.contents
                  and kind_of(s.contents["core_profiles"][1]) == "transport"]
    if not candidates:
        for sink in sinks:
            if "core_profiles" not in sink.contents:
                continue
            written_by = code_name(sink.uri, "core_profiles")
            if written_by and written_by.upper() in TRANSPORT_CODE_NAMES:
                LOGGER.info("sink %s: transport code recognised from "
                            "core_profiles/code/name = %s", sink.name, written_by)
                candidates.append(sink)
    if candidates:
        if len(candidates) > 1:
            LOGGER.info("several core_profiles sinks (%s), taking the first",
                        ", ".join(s.name for s in candidates))
        transport = candidates[0]
        transport.role = "core_profiles"
    else:
        for sink in sinks:
            if sink.role:
                continue
            for ids_name in ("plasma_profiles", "equilibrium", "summary"):
                entry = sink.contents.get(ids_name)
                if entry and kind_of(entry[1]) == "transport":
                    transport_only_extras = sink
                    break
            if transport_only_extras is not None:
                break
        LOGGER.info("no sink receives core_profiles from a transport code -- "
                    "the export gets no --core-profiles entry%s",
                    (" (transport outputs in %s are exported as extras)"
                     % transport_only_extras.name) if transport_only_extras else "")
    return equilibrium, transport, transport_only_extras


def log_role_table(config: Configuration, sinks: list) -> None:
    LOGGER.info("role table:")
    LOGGER.info("  %-16s %-14s %-16s %-22s %-22s %s", "sink dir", "role", "IDS",
                "wired to", "code", "implementation")
    for sink in sinks:
        for ids_name in sorted(sink.contents):
            producer, implementation = sink.contents[ids_name]
            LOGGER.info("  %-16s %-14s %-16s %-22s %-22s %s", sink.name,
                        sink.role or "extra", ids_name,
                        sink.direct.get(ids_name, producer), producer,
                        implementation)


# ---------------------------------------------------------------------------
# d. inputs
# ---------------------------------------------------------------------------
IMAS_URI = re.compile(r"imas:[A-Za-z0-9_]+\?[^\s\"']+")


class InputEntry:
    def __init__(self, uri, directory, referenced_by):
        self.uri = uri
        self.directory = directory
        self.referenced_by = referenced_by
        self.machine_description = False

    @property
    def name(self):
        return self.directory.name if self.directory else self.uri


def waveform_imports(path: str) -> list:
    """IMAS URIs of ``globals.imports`` of a waveform-editor configuration."""
    uris = []
    try:
        with open(path) as stream:
            document = yaml.safe_load(stream) or {}
    except Exception as exc:
        LOGGER.warning("cannot read waveforms file %s: %s", path, exc)
        return uris
    imports = ((document.get("globals") or {}).get("imports") or {})
    for value in imports.values():
        if isinstance(value, str) and "imas:" in value:
            uris.extend(IMAS_URI.findall(value))
    return uris


# ---------------------------------------------------------------------------
# Which heating system the workflow labels the imported heating with.
# ---------------------------------------------------------------------------
# A DINA-derived input often carries its auxiliary heating as one aggregated
# core_sources entry (identifier 100, "auxiliary"), with no power per system.
# The waveform-editor configuration of the workflow is what says which system
# that power stands for: it renames the imported source, e.g.
#
#   core_sources/source(1)/identifier/name:
#     - {value: ec}
#
# so the export is told to report that power as EC power.
HEATING_SYSTEMS = ("ec", "nbi", "ic", "lh")
SOURCE_NAME_KEY = re.compile(r"^core_sources/source\(\d+\)/identifier/name$")


def labelled_heating_systems(path: str) -> set:
    """Heating systems a waveform-editor configuration names a source after."""
    try:
        with open(path) as stream:
            document = yaml.safe_load(stream) or {}
    except Exception as exc:
        LOGGER.warning("cannot read waveforms file %s: %s", path, exc)
        return set()

    systems = set()

    def value_of(entry):
        """The literal a waveform entry sets, ``{value: ec}`` or ``ec``."""
        if isinstance(entry, dict):
            return entry.get("value")
        return entry

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str) and SOURCE_NAME_KEY.match(key):
                    entries = value if isinstance(value, list) else [value]
                    for entry in entries:
                        literal = value_of(entry)
                        if isinstance(literal, str) \
                                and literal.strip().lower() in HEATING_SYSTEMS:
                            systems.add(literal.strip().lower())
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(document)
    return systems


def auxiliary_heating(config: Configuration) -> tuple:
    """``(system, waveforms file)`` the aggregated auxiliary power belongs to.

    ``(None, "")`` when the workflow labels no heating source, or labels
    several: the attribution is then ambiguous and nothing is attributed.
    """
    found = {}
    for key, value in config.settings.items():
        if not isinstance(value, str):
            continue
        if key.endswith(".waveforms") or key == "waveforms":
            for system in labelled_heating_systems(value):
                found.setdefault(system, value)
    if len(found) == 1:
        system, path = next(iter(found.items()))
        LOGGER.info("auxiliary heating attributed to %s (from %s)", system, path)
        return system, path
    if found:
        LOGGER.info("auxiliary heating not attributed: the waveform-editor "
                    "configuration labels several heating systems (%s)",
                    ", ".join(sorted(found)))
    else:
        LOGGER.info("auxiliary heating not attributed: no waveform-editor "
                    "configuration labels a core_sources source ec/nbi/ic/lh")
    return None, ""


def entry_ids_names(entry) -> list:
    """Names of the IDSs that hold data in an open data entry."""
    import imas
    names = []
    for name in imas.IDSFactory().ids_names():
        try:
            occurrences = entry.list_all_occurrences(name)
        except Exception:
            continue
        if occurrences:
            names.append(name)
    return names


def is_machine_description(uri: str) -> bool:
    """True when every IDS of the entry is static (homogeneous_time == 2)."""
    try:
        import imas
    except ImportError:
        return False
    try:
        with imas.DBEntry(uri, "r") as entry:
            names = entry_ids_names(entry)
            if not names:
                return False
            for name in names:
                ids = entry.get(name, lazy=True)
                if int(ids.ids_properties.homogeneous_time) != 2:
                    return False
            return True
    except Exception as exc:
        LOGGER.info("cannot classify %s (%s), treated as a scenario input",
                    uri, exc)
        return False


def discover_inputs(config: Configuration) -> list:
    """IMAS entries the run read, in the order the settings mention them."""
    found, entries = [], []
    for key, value in config.settings.items():
        if not isinstance(value, str):
            continue
        if key.endswith("sink_uri"):
            continue                     # that is an output of the run, not an input
        if key.endswith(".waveforms") or key == "waveforms":
            found.extend((uri, key) for uri in waveform_imports(value))
        elif "imas:" in value:
            found.extend((uri, key) for uri in IMAS_URI.findall(value))
    seen = {}
    for uri, key in found:
        path = uri_path(uri)
        directory = Path(path) if path else None
        marker = str(directory) if directory else uri
        if marker in seen:
            existing = seen[marker].referenced_by
            if key not in existing.split(", "):
                seen[marker].referenced_by = f"{existing}, {key}"
            continue
        if directory is not None and not directory.exists():
            LOGGER.warning("input %s (%s) does not exist, ignored", uri, key)
            continue
        entry = InputEntry(uri, directory, key)
        seen[marker] = entry
        entries.append(entry)
    for entry in entries:
        entry.machine_description = is_machine_description(entry.uri)
        LOGGER.info("input %-14s %-22s %s", entry.name,
                    "machine description" if entry.machine_description
                    else "scenario input", entry.uri)
    # machine description first, then the scenario inputs
    return ([e for e in entries if e.machine_description]
            + [e for e in entries if not e.machine_description])


# ---------------------------------------------------------------------------
# e. the IMAS export
# ---------------------------------------------------------------------------
def describe(sink, ids_name):
    """``<sink dir>/<implementation>/<code name>`` of the IDS a sink holds."""
    if sink is None:
        return "not produced by this run"
    producer, implementation = sink.contents.get(ids_name, ("", ""))
    stem = short_impl(implementation) or producer or "?"
    written_by = code_name(sink.uri, ids_name)
    return f"{sink.name}/{stem}" + (f"/{written_by}" if written_by else "")


def export_imas(args, config, equilibrium, transport, extras, inputs, output_uri,
                heating_system=None):
    command = [sys.executable,
               str(Path(args.pds_repo) / "workflows" / "utils" / "pds_imas_export.py"),
               "--output", output_uri]
    if equilibrium is not None:
        command += ["--equilibrium", equilibrium.uri]
    if transport is not None:
        command += ["--core-profiles", transport.uri]
    if extras:
        command += ["--extra"] + extras
    if heating_system:
        command += ["--auxiliary-heating", heating_system]
    command += ["--machine", "ITER"]
    if args.shot:
        command += ["--shot", str(args.shot)]
    command += ["--workflow", args.wf_name or config.model_name]
    comment = ("PDS %s run, ITER pulse %s: equilibrium from %s, core_profiles "
               "from %s, inputs: %s"
               % (args.wf_name or config.model_name, args.shot or "?",
                  describe(equilibrium, "equilibrium"),
                  describe(transport, "core_profiles"),
                  ", ".join(entry.name for entry in inputs) or "none"))
    command += ["--comment", comment]
    LOGGER.info("running %s", " ".join(command))
    done = subprocess.run(command, check=False)
    if done.returncode != 0:
        raise RuntimeError("pds_imas_export.py exited with %d" % done.returncode)
    return comment


def plot_pulse_schedule(args, inputs, output_uri, run_dir):
    """Figure of the exported pulse schedule, with the scenario inputs overlaid.

    Runs ``pdsplot.scripts.plotpulseschedule`` (workflows/utils/pdsplot) as a
    subprocess so that a plotting failure can never take the post-processing
    down, and writes into ``<run dir>/plots/plotpulseschedule`` -- already
    covered by the ``plots/*/*.*`` glob of the manifest.

    Returns:
        list: the PNG files produced.
    """
    directory = run_dir / "plots" / "plotpulseschedule"
    command = [sys.executable, "-m", "pdsplot.scripts.plotpulseschedule",
               "--uri", output_uri, "--save", "--directory", str(directory)]
    for entry in inputs:
        if not entry.machine_description:
            command += ["--reference", entry.uri]
    utils = str(Path(args.pds_repo) / "workflows" / "utils")
    environment = dict(os.environ)
    environment["MPLBACKEND"] = "Agg"
    environment["PYTHONPATH"] = os.pathsep.join(
        [utils] + [item for item in [environment.get("PYTHONPATH")] if item])
    LOGGER.info("running %s", " ".join(command))
    done = subprocess.run(command, env=environment, check=False)
    if done.returncode != 0:
        raise RuntimeError("plotpulseschedule exited with %d" % done.returncode)
    return sorted(str(path) for path in directory.glob("*.png"))


# ---------------------------------------------------------------------------
# f. git state and software stack
# ---------------------------------------------------------------------------
def software_stack(config: Configuration) -> list:
    """(implementation, modules, executable) of every program of the run."""
    stack = []
    for name, program in sorted((config.programs or {}).items()):
        program = program or {}
        modules = as_list(program.get("modules"))
        executable = str(program.get("executable") or "")
        arguments = " ".join(as_list(program.get("args")))
        script = program.get("script") or ""
        if script:
            for line in script.splitlines():
                stripped = line.strip()
                if stripped.startswith("module load"):
                    modules.extend(stripped[len("module load"):].split())
            if not executable:
                for line in script.splitlines():
                    if line.strip().startswith("exec "):
                        executable = line.strip()[5:].split()[0]
                        break
        stack.append((name, modules, (executable + " " + arguments).strip()))
    return stack


def write_git_state(args, config: Configuration, path: Path) -> dict:
    repo = args.pds_repo
    state = {
        "head": run_git(repo, "rev-parse", "HEAD").strip() or "unknown",
        "describe": run_git(repo, "describe", "--always", "--dirty").strip(),
        "remote": run_git(repo, "remote", "-v").strip(),
        "status": run_git(repo, "status", "--short"),
        "diff": run_git(repo, "diff", "HEAD"),
        "untracked": run_git(repo, "ls-files", "--others", "--exclude-standard",
                             "--", "workflows", "controllers", "bin",
                             "cases/overrides"),
    }
    state["dirty"] = state["describe"].endswith("-dirty")
    state["short"] = state["head"][:7]
    remote_url = ""
    for line in state["remote"].splitlines():
        if "(fetch)" in line:
            remote_url = line.split()[1]
            break
    state["remote_url"] = remote_url or "git@github.com:iterorganization/IMAS-PDS.git"

    lines = [
        "# Git state of the PDS repository at post-processing time",
        "#",
        "# Together with README_REPRODUCE.md this is what is needed to rebuild the",
        "# exact code the run used: check out the commit below, then apply the diff",
        "# of the 'tracked changes' section with `git apply`.",
        "",
        "repository: %s" % repo,
        "HEAD:       %s" % state["head"],
        "describe:   %s" % state["describe"],
        "",
        "## remotes",
        state["remote"] or "(none)",
        "",
        "## git status --short",
        state["status"].rstrip() or "(clean)",
        "",
        "## untracked files under workflows/ controllers/ bin/ cases/overrides/",
        state["untracked"].rstrip() or "(none)",
        "",
        "## software stack (modules and executables of every actor of the run,",
        "## taken from the flattened configuration.ymmsl -- `module list` cannot be",
        "## replayed here because every actor loads its own environment)",
    ]
    for name, modules, executable in software_stack(config):
        lines.append("- %s" % name)
        lines.append("    modules:    %s" % (", ".join(modules) or "(none)"))
        lines.append("    executable: %s" % (executable or "(script)"))
    lines += [
        "",
        "## git diff HEAD (tracked changes)",
        state["diff"].rstrip() or "(no tracked change)",
        "",
    ]
    path.write_text("\n".join(lines) + "\n")
    return state


# ---------------------------------------------------------------------------
# g. README_REPRODUCE.md
# ---------------------------------------------------------------------------
# pulse_schedule node carrying the launched power of a heating system.
HEATING_REFERENCE = {"ec": "ec.power_launched", "nbi": "nbi.power",
                     "ic": "ic.power", "lh": "lh.power"}


def write_readme(args, config, state, sinks, equilibrium, transport, inputs,
                 heating, path: Path) -> None:
    case_dir = Path(args.case_dir)
    run_dir = Path(args.run_dir)
    workflow = args.wf_name or config.model_name
    case_name = case_dir.name
    archived = sorted(p.name for p in case_dir.iterdir() if p.is_file())

    roles = []
    for sink in sinks:
        for ids_name in sorted(sink.contents):
            producer, implementation = sink.contents[ids_name]
            roles.append("| `%s` | %s | `%s` | `%s` | `%s` | `%s` |"
                         % (sink.name, sink.role or "extra", ids_name,
                            sink.direct.get(ids_name, producer), producer,
                            short_impl(implementation)))

    heating_system, heating_file = heating
    attribution = ""
    if heating_system:
        attribution = (
            "\n\nThe aggregated `auxiliary` core_sources power (identifier 100) of the input "
            "carries no heating system of its own; it is reported as %s power "
            "(`summary.heating_current_drive.power_%s`, `pulse_schedule.%s`) because "
            "`%s` labels the imported heating source `%s`."
            % (heating_system.upper(), heating_system,
               HEATING_REFERENCE[heating_system], heating_file, heating_system))

    stack = []
    for name, modules, executable in software_stack(config):
        stack.append("| `%s` | %s | `%s` |"
                     % (name, ", ".join("`%s`" % m for m in modules) or "-",
                        executable or "-"))

    text = f"""# How to reproduce this run

Run directory: `{run_dir}`
Workflow: `{workflow}` -- ITER pulse `{args.shot or "?"}` -- case `{case_name}`
PDS commit: `{state["head"]}` (`{state["describe"]}`)
Repository: `{state["remote_url"]}`

The run is fully described by `configuration.ymmsl` in this directory (the flattened
yMMSL muscle_manager actually executed), by `pds_git_state.txt` (repository state and
software stack) and by `simdb_manifest.yaml` (every input and output file).

## What this run produced

| sink | role | IDS | wired to | code | implementation |
|------|------|-----|----------|------|----------------|
{chr(10).join(roles) or "| - | - | - | - | - | - |"}

The curated single-entry export of all of it is `imas_out`: equilibrium from
`{describe(equilibrium, "equilibrium")}`, core_profiles from `{describe(transport, "core_profiles")}`,
everything else from the entries above, plus `summary` and `pulse_schedule` IDSs built by
`workflows/utils/pds_imas_export.py`.{attribution}

Inputs read by the run:

{chr(10).join("- `%s` (%s) -- %s" % (e.uri, "machine description" if e.machine_description else "scenario input", e.referenced_by) for e in inputs) or "- (none discovered)"}

## Software stack

| implementation | modules | executable |
|----------------|---------|------------|
{chr(10).join(stack) or "| - | - | - |"}

These modules must be available (`module use /work/projects/pds/modules/all`) for the
run to be reproducible; local installs referenced by an absolute path must exist too.

## Procedure A -- from the PDS git repository

```bash
git clone {state["remote_url"]} IMAS-PDS
cd IMAS-PDS
git checkout {state["head"]}
```

If the "git diff HEAD" section of `pds_git_state.txt` is not empty, the run used a
modified working tree; re-apply it (and add the untracked files listed there by hand):

```bash
sed -n '/^## git diff HEAD/,$p' {run_dir}/pds_git_state.txt | tail -n +2 > /tmp/pds.diff
git apply /tmp/pds.diff
```

Restore the case folder from the archived case files
({", ".join("`%s`" % name for name in archived) or "none"}{", `config/`" if (case_dir / "config").is_dir() else ""}{", `preprocess/`" if (case_dir / "preprocess").is_dir() else ""})
into `cases/{case_name}/`, then launch:

```bash
module use /work/projects/pds/modules/all
module load PDS
bin/pds-run-case cases/{case_name}
```

`bin/pds-run-case` re-runs the whole chain, including this post-processing, and writes a
new timestamped directory under `cases/runs/`.

## Procedure B -- without git, from the archived runtime files

Recreate the shared runtime tree from the files archived in the manifest, keeping the
same relative layout:

```
bin/                      workflows/lib/            workflows/lib/actors/
workflows/utils/          workflows/{workflow}/
controllers/<name>/       pds_validation_tests/
cases/{case_name}/
```

then launch it exactly as in procedure A (`module load PDS; bin/pds-run-case
cases/{case_name}`).

Alternatively, replay the flattened configuration directly, without the case folder:

```bash
module use /work/projects/pds/modules/all && module load PDS
muscle_manager --start-all --run-dir <new run dir> configuration.ymmsl
```

`configuration.ymmsl` holds absolute paths (case config files, input data entries,
`$PDS_REPO`-derived actor paths); they must exist and point at the same content, so
this shortcut is meant for a re-run on the same machine, not for a fresh install.
"""
    path.write_text(text)


# ---------------------------------------------------------------------------
# h. SimDB manifest
# ---------------------------------------------------------------------------
def matching(pattern: str) -> int:
    return len(glob.glob(pattern))


def yaml_string(value) -> str:
    """Escape a value for a double-quoted YAML scalar, on a single line."""
    text = str(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    return " ".join(text.split())


def simdb_run_number(args):
    """Optional IMAS run number of this case (``--simdb-run`` or ``PDS_SIMDB_RUN``).

    Opt-in, for the special case where the result of this run is *also* stored in
    the shared IMAS database under a real ``<pulse>/<run>`` location: giving that
    run number makes the SimDB alias ``<pulse>/<run>`` instead of the descriptive
    PDS alias, so that the SimDB entry and the scenario-database entry are named
    alike. Normal PDS runs leave it unset.

    Returns:
        int or None: the run number, None when none is set or it is not an
        integer.
    """
    raw = str(args.simdb_run or os.environ.get("PDS_SIMDB_RUN", "")).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        LOGGER.warning("run number %r is not an integer, ignored", raw)
        return None


def simdb_version(args) -> str:
    """Version tag of this registration (``--simdb-version`` or ``PDS_SIMDB_VERSION``).

    Defaults to ``v1``, so an alias always ends with a ``-vN``. Bump it (``v2``,
    ``v3``, ...) every time the same run is registered anew, and push the new
    entry with ``--replaces <previous alias>``.
    """
    raw = str(args.simdb_version or os.environ.get("PDS_SIMDB_VERSION", "")).strip()
    return raw or "v1"


def simdb_alias(args, workflow: str, run_dir: Path, run, version: str):
    """The alias of the SimDB entry for this run.

    PDS names its entries descriptively::

        pds-<workflow>-<pulse>-<YYYYMMDD>-<HHMMSS>-v<N>

    where date and time are those of the run directory and ``vN`` is the version
    of the registration (``--simdb-version``/``PDS_SIMDB_VERSION``, ``v1`` by
    default), bumped whenever the same run is registered again.

    Two overrides exist: ``--simdb-alias`` sets the alias verbatim, and the
    opt-in ``--simdb-run`` (see :func:`simdb_run_number`) makes it ``<pulse>/<run>``
    for the special case of a run also stored in the shared IMAS database under
    that location.
    """
    if args.simdb_alias:
        return args.simdb_alias.strip()

    if run is not None and args.shot:
        return "%s/%s" % (args.shot, run)

    # Extract timestamp from run_dir.name if it matches the pattern _YYYYMMDD_HHMMSS
    timestamp_match = re.search(r'_(\d{8})_(\d{6})$', run_dir.name)
    if timestamp_match:
        date_str = timestamp_match.group(1)
        time_str = timestamp_match.group(2)
        # Format as YYYYMMDD-HHMMSS
        alias = "pds-%s-%s-%s-%s" % (workflow, args.shot or "0", date_str, time_str)
    else:
        alias = "pds-%s-%s-%s" % (workflow, args.shot or "0", run_dir.name)

    alias = "%s-%s" % (alias, version)
    LOGGER.debug("SimDB alias: %s", alias)
    return alias


def write_manifest(args, config, state, sinks, equilibrium, transport, inputs,
                   output_uri, path: Path) -> None:
    case_dir = Path(args.case_dir)
    run_dir = Path(args.run_dir)
    workflow = args.wf_name or config.model_name
    run = simdb_run_number(args)
    version = simdb_version(args)
    alias = simdb_alias(args, workflow, run_dir, run, version)

    inputs_block = []

    def add_input(comment, pattern, must_match=True):
        if must_match and not matching(pattern):
            return
        if comment:
            inputs_block.append("  # " + comment)
        inputs_block.append("  - uri: file://%s" % pattern)

    if inputs:
        inputs_block.append("  # data entries read by the run (no summary IDS, so"
                            " listed as plain files)")
        for entry in inputs:
            if entry.directory and matching(str(entry.directory / "*.h5")):
                inputs_block.append("  - uri: file://%s/*.h5" % entry.directory)
    inputs_block.append("  # the case folder: yMMSL stack, case.env, hooks")
    for item in sorted(case_dir.iterdir()):
        if item.is_file():
            inputs_block.append("  - uri: file://%s" % item)
    add_input("case configuration files (actor configs, waveforms)",
              str(case_dir / "config" / "*.*"))
    add_input("case preprocessing outputs",
              str(case_dir / "preprocess" / "*" / "*.h5"))
    add_input(None, str(case_dir / "preprocess" / "*.*"))
    if args.scenarios_repo and args.shot:
        add_input("scenario provenance",
                  str(Path(args.scenarios_repo) / str(args.shot) / "source.env"))
    inputs_block.append("  # shared PDS runtime code (the case-independent part of"
                        " the repository)")
    for comment, pattern in (
            (None, str(Path(args.pds_repo) / "bin" / "*")),
            (None, str(Path(args.pds_repo) / "workflows" / "lib" / "*.*")),
            (None, str(Path(args.pds_repo) / "workflows" / "lib" / "actors" / "*.py")),
            (None, str(Path(args.pds_repo) / "workflows" / "utils" / "*.py")),
            (None, str(Path(args.pds_repo) / "workflows" / workflow / "*.*")),
            (None, str(Path(args.pds_repo) / "controllers" / "*" / "*.*")),
            (None, str(Path(args.pds_repo) / "pds_validation_tests" / "*.*")),
    ):
        add_input(comment, pattern)

    outputs_block = ["  # the curated single-entry export of the whole run",
                     "  - uri: %s" % output_uri,
                     "  # raw MUSCLE3 sink outputs (no summary IDS, hence archived"
                     " as plain files)"]
    for sink in sinks:
        outputs_block.append("  - uri: file://%s/*.h5" % sink.directory)
    outputs_block.append("  # run configuration, logs and provenance")
    for name in ("configuration.ymmsl", "muscle3_manager.log", "performance.sqlite",
                 "pds_git_state.txt", "README_REPRODUCE.md", "simdb_manifest.yaml"):
        outputs_block.append("  - uri: file://%s" % (run_dir / name))
    for pattern in ("instances/*/stdout.txt", "instances/*/stderr.txt",
                    "instances/*/run_script.sh", "logs/*", "snapshots/*"):
        outputs_block.append("  - uri: file://%s" % (run_dir / pattern))
    outputs_block.append("  # post-processing")
    for pattern in ("plots/*.*", "plots/*/*.*"):
        outputs_block.append("  - uri: file://%s" % (run_dir / pattern))

    equilibrium_code = short_impl(equilibrium.contents["equilibrium"][1]) \
        if equilibrium is not None else "no"
    transport_sink = transport
    if transport_sink is None:
        for sink in sinks:
            for ids_name in ("plasma_profiles", "summary", "equilibrium"):
                entry = sink.contents.get(ids_name)
                if entry and kind_of(entry[1]) == "transport":
                    transport_sink = sink
                    break
            if transport_sink is not None:
                break
    transport_code = "no"
    if transport_sink is not None:
        for ids_name in ("core_profiles", "plasma_profiles", "summary",
                         "equilibrium"):
            entry = transport_sink.contents.get(ids_name)
            if entry and kind_of(entry[1]) == "transport":
                transport_code = short_impl(entry[1])
                break

    description = ("PDS %s run for ITER pulse %s: equilibrium from %s, "
                   "core_profiles from %s; summary and pulse_schedule IDSs derived by pds_imas_export.py from those outputs; "
                   "raw MUSCLE3 outputs, logs and configuration archived as files"
                   % (workflow, args.shot or "?",
                      describe(equilibrium, "equilibrium"),
                      describe(transport, "core_profiles")))
    # The code name is the product name the server filters on; which actors the
    # run used is said by the workflow metadata entry and by the parameters.
    software_name = "IMAS-PDS"
    # One line naming the actors of the run and then the software stack of every
    # one of them, taken from the same extraction that feeds pds_git_state.txt.
    parameters = ("workflow=%s; equilibrium=%s; transport=%s; "
                  % (workflow, equilibrium_code, transport_code)) + "; ".join(
        "%s: %s" % (name, ", ".join(modules) or executable or "(script)")
        for name, modules, executable in software_stack(config))

    text = "\n".join([
        "manifest_version: 2",
        "# SimDB manifest for this PDS run, written by"
        " workflows/utils/pds_postprocess.py.",
        "#",
        "# Alias: PDS entries are named pds-<workflow>-<pulse>-<date>-<time>-v<N>,"
        " where date",
        "# and time are those of the run directory and vN is the version of the"
        " registration",
        "# (v1 by default; --simdb-version vN, or PDS_SIMDB_VERSION=vN). Bump N every"
        " time the",
        "# same run is registered anew -- for instance after a metadata or"
        " post-processing fix --",
        "# and push the new entry with `simdb simulation push ITER <new alias>"
        " --replaces <previous",
        "# alias>`: the server then sets the previous entry to status \"deprecated\","
        " records",
        "# replaced_by on it, and `simdb remote ITER trace <new alias>` shows the"
        " chain.",
        "# The code name is the product name the web interface filters on,"
        " \"IMAS-PDS\"; which",
        "# workflow the run used is the `workflow` metadata entry.",
        "# Opt-in: --simdb-run N (PDS_SIMDB_RUN=N) makes the alias <pulse>/<run>"
        " instead, for the",
        "# case where this result is also stored in the shared IMAS database under"
        " that location.",
        "#",
        "# Edit alias/description if needed, then:",
        "#   module use /work/imas/etc/modules/all && module load"
        " SimDB/0.15.2-foss-2025b",
        "#   simdb manifest check simdb_manifest.yaml",
        "#   simdb simulation ingest simdb_manifest.yaml",
        "#   simdb simulation validate ITER <alias> ; simdb simulation push ITER"
        " <alias>",
        "#   simdb simulation push ITER <alias> --replaces <previous alias>"
        "   # a new version of the same run",
        "alias: %s" % alias,
        "inputs:",
        "\n".join(inputs_block),
        "outputs:",
        "\n".join(outputs_block),
        "metadata:",
        '  - machine: "ITER"',
        '  - workflow: "%s"' % yaml_string(workflow),
        "  - code:",
        '      name: "%s"' % yaml_string(software_name),
        '      version: "%s"' % yaml_string(state["describe"] or state["short"]),
        '      commit: "%s"' % yaml_string(state["head"]),
        '      repository: "%s"' % yaml_string(state["remote_url"]),
        '      parameters: "%s"' % yaml_string(parameters),
        '  - description: "%s"' % description,
        '  - responsible_name: "%s"' % (os.environ.get("USER") or "unknown"),
    ] + (["  - pulse: %s" % (int(args.shot) if str(args.shot).isdigit()
                             else '"%s"' % yaml_string(args.shot))]
         if args.shot else [])
      + (["  - run: %d" % run] if run is not None else [])
      + ['  - version: "%s"' % yaml_string(version)]
      + [""])
    path.write_text(text)


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------
def read_case_env(case_dir: Path, args) -> None:
    path = case_dir / "case.env"
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if key.strip() == "WF_NAME" and not args.wf_name:
            args.wf_name = value
        elif key.strip() == "SHOT" and not args.shot:
            args.shot = value


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generic post-processing of a PDS run "
                    "(IMAS export, git state, reproduction notes, SimDB manifest).")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--case-dir", required=True)
    parser.add_argument("--pds-repo", required=True)
    parser.add_argument("--scenarios-repo", default="")
    parser.add_argument("--shot", default="")
    parser.add_argument("--workflow", dest="wf_name", default="")
    parser.add_argument("--simdb-version", default="",
                        help="version of this registration, the -vN suffix of the "
                             "alias pds-<workflow>-<pulse>-<date>-<time>-v<N> and the "
                             "`version` metadata entry; default v1, bump it (v2, v3, "
                             "...) for every new registration of the same run and push "
                             "with --replaces <previous alias> "
                             "(env: PDS_SIMDB_VERSION)")
    parser.add_argument("--simdb-run", default="",
                        help="opt-in: run number of a <pulse>/<run> alias, e.g. 7 for "
                             "105073/7, for the special case where this result is also "
                             "stored in the shared IMAS database under that location; "
                             "the number must be free on the server "
                             "(env: PDS_SIMDB_RUN)")
    parser.add_argument("--simdb-alias", default="",
                        help="explicit SimDB alias, overriding both the descriptive "
                             "alias and the <pulse>/<run> one")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)-7s %(message)s")

    run_dir, case_dir = Path(args.run_dir), Path(args.case_dir)
    read_case_env(case_dir, args)

    configuration = run_dir / "configuration.ymmsl"
    if not configuration.is_file():
        LOGGER.error("no %s -- nothing to post-process", configuration)
        return 1
    config = Configuration(configuration)
    LOGGER.info("model %s: %d components, %d conduits, %d settings, %d programs",
                config.model_name, len(config.components), len(config.conduits),
                len(config.settings), len(config.programs))

    written, failed = [], []

    sinks = discover_sinks(config, run_dir)
    fill_sink_contents(config, sinks)
    equilibrium, transport, transport_extras = assign_roles(sinks)
    log_role_table(config, sinks)

    inputs = discover_inputs(config)
    heating = auxiliary_heating(config)

    # Order matters: pds_imas_export.py keeps, for every IDS not covered by
    # --equilibrium/--core-profiles, the first --extra entry that has it. So
    # the order here is: machine description first (it only holds static
    # IDSs, so nothing competes with it), then the run's own non-role sinks,
    # then the scenario inputs last -- an IDS the run produced must win over
    # the same IDS in its inputs.
    machine_description = [entry.uri for entry in inputs if entry.machine_description]
    scenario_inputs = [entry.uri for entry in inputs if not entry.machine_description]
    non_role_sinks = [sink.uri for sink in sinks
                      if sink is not equilibrium and sink is not transport]
    extras = machine_description + non_role_sinks + scenario_inputs

    output_uri = "imas:hdf5?path=%s" % (run_dir / "imas_out")
    try:
        export_imas(args, config, equilibrium, transport, extras, inputs,
                    output_uri, heating_system=heating[0])
        written.append(str(run_dir / "imas_out"))
        exported = True
    except Exception as exc:
        LOGGER.error("IMAS export failed: %s", exc)
        failed.append("imas_out")
        exported = False

    if exported:
        try:
            written.extend(plot_pulse_schedule(args, inputs, output_uri, run_dir))
        except Exception as exc:
            LOGGER.warning("pulse schedule figure not produced: %s", exc)

    state = {"head": "unknown", "describe": "unknown", "short": "unknown",
             "dirty": False, "remote_url": "", "remote": "", "status": "",
             "diff": "", "untracked": ""}
    try:
        state = write_git_state(args, config, run_dir / "pds_git_state.txt")
        written.append(str(run_dir / "pds_git_state.txt"))
    except Exception as exc:
        LOGGER.error("git state not written: %s", exc)
        failed.append("pds_git_state.txt")

    try:
        write_readme(args, config, state, sinks, equilibrium, transport, inputs,
                     heating, run_dir / "README_REPRODUCE.md")
        written.append(str(run_dir / "README_REPRODUCE.md"))
    except Exception as exc:
        LOGGER.error("README_REPRODUCE.md not written: %s", exc)
        failed.append("README_REPRODUCE.md")

    try:
        write_manifest(args, config, state, sinks, equilibrium, transport, inputs,
                       output_uri, run_dir / "simdb_manifest.yaml")
        written.append(str(run_dir / "simdb_manifest.yaml"))
    except Exception as exc:
        LOGGER.error("simdb_manifest.yaml not written: %s", exc)
        failed.append("simdb_manifest.yaml")

    LOGGER.info("---- post-processing summary ----")
    LOGGER.info("workflow %s, pulse %s, run %s",
                args.wf_name or config.model_name, args.shot or "?", run_dir.name)
    LOGGER.info("equilibrium: %s", describe(equilibrium, "equilibrium"))
    LOGGER.info("core_profiles: %s", describe(transport, "core_profiles"))
    LOGGER.info("extras: %s", ", ".join(
        [e.name for e in inputs if e.machine_description]
        + [s.name for s in sinks if s is not equilibrium and s is not transport]
        + [e.name for e in inputs if not e.machine_description])
        or "none")
    for item in written:
        LOGGER.info("written: %s", item)
    for item in failed:
        LOGGER.warning("failed:  %s", item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
