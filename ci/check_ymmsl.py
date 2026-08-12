#!/usr/bin/env python3
"""Verification 1 -- static resolve + flatten of every case against its workflow.

Catches, without needing scenario data or a running MUSCLE3:

  1. unfilled holes, missing imports, bad custom_implementations paths, wrong hole fills
     (whatever check_consistent() covers)
  2. setting keys that match no instance -- SILENT at runtime: get_setting walks
     instance prefixes and falls through to the bare name, so a key at the wrong depth
     is simply never seen
  3. resources keys that match no instance -- also SILENT: get_resources logs at debug
     and returns 1 thread, so `torax: {threads: 8}` written at the wrong depth quietly
     runs single-threaded
  4. model ports declared in workflows/lib/*.ymmsl but not wired inside the model --
     flatten() then drops the caller's conduit with no error, and neither
     Model.check_consistent nor _check_consistent_ports objects
  5. scenario waveforms.yaml files whose top-level shape is wrong -- a mangled comment
     can swallow the machine_description: key and silently move its contents into globals
  6. undefined ${VAR} in settings -- expanded here exactly as the patched manager does,
     so CI cannot pass a case that could not start
  7. a self-contained case with no `resources:` -- an imported workflow's resources are
     discarded, so every component would silently get 1 thread

A case either imports its workflow (self-contained, one file on the command line) or
declares it in a `# workflow: <name>` comment header (stacked, two files).

Usage:  python ci/check_ymmsl.py [--scenarios <dir>]
"""
import argparse
import os
import re
import sys
from pathlib import Path

import ymmsl
from ymmsl.v0_2 import Configuration, Reference
from ymmsl.v0_2.resolver import resolve
from libmuscle.manager.hammer import flatten

REPO = Path(__file__).resolve().parent.parent
WORKFLOW_RE = re.compile(r"^#\s*workflow:\s*(\S+)", re.M)
# globals and machine_description are required; state/targets are not -- an
# MD-only scenario (feeding a NICE branch with no design of its own) has neither.
WAVEFORM_REQUIRED = {"globals", "machine_description"}
ENV_VAR_RE = re.compile(r"\$(\w+|\{[^}]*\})")


def _fail(errors, msg):
    errors.append(msg)


IMPORT_RE = re.compile(r"^\s*-\s*from\s+(\S+)\s+import\s+implementation\s+(\S+)", re.M)


def check_case(case: Path, errors: list) -> None:
    """Resolve a case and validate every prefixed key against the flattened instances.

    A case is either *self-contained* -- it imports its workflow, and runs as the single
    argument to muscle_manager -- or *stacked*, naming its workflow in a
    `# workflow: <name>` header so we can load and merge it here the way the command line
    would. Self-contained is the default; both are checked the same way afterwards.
    """
    text = case.read_text()
    self_contained = bool(IMPORT_RE.search(text))

    if self_contained:
        cfg = ymmsl.load_as(Configuration, case)
    else:  # noqa: RET505 -- mirrors the two ways the manager can be invoked
        m = WORKFLOW_RE.search(text)
        if not m:
            _fail(errors, f"{case.name}: neither imports a workflow nor declares one in "
                          f"a '# workflow: <name>' header, so it cannot be paired")
            return
        wf = REPO / "workflows" / m.group(1) / "workflow.ymmsl"
        if not wf.exists():
            _fail(errors, f"{case.name}: names workflow '{m.group(1)}', but {wf} "
                          f"does not exist")
            return
        cfg = ymmsl.load_as(Configuration, wf)
        cfg.update(ymmsl.load_as(Configuration, case))

    # Expand ${VAR} exactly as the patched manager does before resolving, so this check
    # sees the same values a run would. Undefined variables are reported rather than
    # left literal -- otherwise CI would pass on a case that cannot start.
    missing = set()
    for name in list(cfg.settings):
        value = cfg.settings[name]
        if not isinstance(value, str):
            continue
        expanded = os.path.expandvars(value)
        missing.update(m.group(0) for m in ENV_VAR_RE.finditer(expanded))
        cfg.settings[name] = expanded
    if missing:
        _fail(errors, f"{case.name}: undefined environment variable(s) in settings: "
                      f"{', '.join(sorted(missing))}")
        return

    # Reference([]) is exactly what muscle_manager passes (muscle3/muscle_manager.py:110).
    # Do not use the filename: case names like "105084_prescribed" are not valid ymmsl
    # Identifiers, and using one here would fail on files the manager accepts happily.
    try:
        resolve(Reference([]), cfg)
    except RuntimeError as e:
        _fail(errors, f"{case.name}: resolve failed:\n    {e}")
        return

    roots = [str(m.name) for m in cfg._root_models()]
    if len(roots) != 1:
        _fail(errors, f"{case.name}: expected exactly one root model, got {roots} -- "
                      f"muscle_manager would need -m/--model to disambiguate")
        return
    root = roots[0]

    try:
        cfg.check_consistent(selected_model=root)
    except RuntimeError as e:
        _fail(errors, f"{case.name}: check_consistent failed:\n    {e}")
        return

    flat = flatten(cfg, Reference(root))
    instances = {str(c) for c in flat.root_model().components}

    # An imported workflow's own `resources`/`settings` are dropped by the resolver
    # (resolve_impl_imports copies only models and programs), so a self-contained case
    # must carry them itself. Silent when wrong: the component just gets 1 thread.
    if self_contained and not cfg.resources:
        _fail(errors, f"{case.name}: imports its workflow but declares no `resources:`. "
                      f"An imported file's resources are discarded, so every component "
                      f"will silently get 1 thread.")

    def resolves(key: str) -> bool:
        """True if some instance is a prefix of key -- mirrors get_setting's walk."""
        parts = key.split(".")
        return any(".".join(parts[:i]) in instances for i in range(1, len(parts)))

    for key in (str(k) for k in cfg.settings):
        if "." in key and not resolves(key):
            _fail(
                errors,
                f"{case.name}: setting '{key}' matches no instance -- it will be "
                f"silently ignored. Instances: {sorted(instances)}",
            )

    for key in (str(k) for k in cfg.resources):
        if key not in instances:
            _fail(
                errors,
                f"{case.name}: resources key '{key}' matches no instance -- that "
                f"component silently gets 1 thread. Instances: {sorted(instances)}",
            )

    check_waveform_ports(cfg, flat.root_model(), case.name, errors)

    kind = "self-contained" if self_contained else "stacked"
    print(f"ok  {case.name} [{kind}] -> {root}: {len(instances)} instances, "
          f"{len(flat.root_model().conduits)} conduits")


def check_waveform_ports(cfg, flat_model, case_name, errors: list) -> None:
    """Every `<ids>_out` port of a waveform-editor instance must exist in its config.

    The actor derives the IDS name by stripping `_out` from each connected O_F port and
    fails the run with "Output port ... does not match any IDS in the waveform
    configuration" if the config does not produce it. That needs no data to check: the
    IDSs a config produces are the first path segment of each waveform it declares.
    """
    import yaml as _yaml

    ports = {}
    for comp in flat_model.components.values():
        names = [str(p) for p in comp.ports.sending_port_names()]
        if names:
            ports[str(comp.name)] = names

    for key in (str(k) for k in cfg.settings):
        if not key.endswith(".waveforms"):
            continue
        instance = key[: -len(".waveforms")]
        if instance not in ports:
            continue
        path = Path(str(cfg.settings[key]))
        if not path.is_file():
            continue  # data/scenario not checked out; the key check already ran
        doc = _yaml.safe_load(path.read_text()) or {}
        produced = {
            str(w).split("/", 1)[0]
            for group, content in doc.items()
            if group != "globals" and isinstance(content, dict)
            for w in content
        }
        for port in ports[instance]:
            ids = port[: -len("_out")] if port.endswith("_out") else port
            if ids not in produced:
                _fail(errors, f"{case_name}: '{instance}' declares output port "
                              f"'{port}', but {path.name} produces no '{ids}' IDS "
                              f"(it produces {sorted(produced)})")


def check_lib_ports(errors: list) -> None:
    """Every declared model port must be wired inside that model."""
    for path in sorted((REPO / "workflows" / "lib").glob("*.ymmsl")):
        cfg = ymmsl.load_as(Configuration, path)
        for model in cfg.models.values():
            wired = set()
            for c in model.conduits:
                if not c.sending_component():
                    wired.add(str(c.sending_port()))
                if not c.receiving_component():
                    wired.add(str(c.receiving_port()))
            declared = {
                str(p)
                for p in model.ports.receiving_port_names() + model.ports.sending_port_names()
            }
            for orphan in sorted(declared - wired):
                _fail(
                    errors,
                    f"{path.name}: model '{model.name}' declares port '{orphan}' but "
                    f"never wires it internally -- flatten() will silently drop the "
                    f"caller's conduit",
                )
        print(f"ok  {path.name}: model ports wired")


def check_scenarios(scenarios: Path, errors: list) -> None:
    import yaml

    for wf_yaml in sorted(scenarios.glob("*/waveforms.yaml")):
        doc = yaml.safe_load(wf_yaml.read_text())
        rel = wf_yaml.relative_to(scenarios)
        missing = WAVEFORM_REQUIRED - set(doc)
        if missing:
            _fail(errors, f"{rel}: missing top-level key(s) {sorted(missing)} -- a "
                          f"mangled comment can swallow one; check the raw YAML")
        stray = set(doc.get("globals", {})) - {"dd_version", "imports"}
        if stray:
            _fail(errors, f"{rel}: unexpected keys inside globals: {sorted(stray)} -- "
                          f"these have almost certainly fallen out of another block")
        if not missing and not stray:
            print(f"ok  {rel}: shape")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenarios", type=Path, help="path to a pds-scenarios checkout")
    args = ap.parse_args()

    errors: list = []
    check_lib_ports(errors)
    for case in sorted((REPO / "cases").glob("*.ymmsl")):
        check_case(case, errors)
    if args.scenarios:
        check_scenarios(args.scenarios, errors)

    if errors:
        print(f"\n{len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
