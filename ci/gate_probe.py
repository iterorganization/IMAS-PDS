#!/usr/bin/env python3
"""Verification 0 gate probe -- run this before writing any nested yMMSL.

Everything in the modularisation plan that writes a prefixed key -- every case
setting, every custom_implementations path, every resources entry -- depends on
what this prints. Getting those prefixes wrong is silent: no error, no warning,
just a default quietly used instead of your value.

Usage:  python ci/gate_probe.py [ci/gate_probe.ymmsl]

Needs no scenario data, no actors and no IMAS -- only ymmsl and muscle3.

Measured on muscle3 0.10.0 with ymmsl 0.17.0:

    instance names          run.inner              (nesting path only, no model name)
    custom_implementations  probe.run.inner        (model name REQUIRED; bare form fails)
    resources               probe.probe.run.inner  (ROOT MODEL NAME + instance, exact match)

The three forms are all different -- do not generalise from one to another.

The resources answer was previously recorded here as the bare instance name. That was
wrong, and it silently cost a real run: `run.transport: {threads: 8}` in every case file
got 1 thread instead of 8. Two reasons it was missed:

  - the probe asked `get_resources(Reference("run.inner"))`, a lookup the manager never
    performs. instance_manager.py:142 asks `get_resources(model.name + component.name)`,
    and Configuration.get_resources is an exact dict `.get()` with no prefix walk -- so
    the old probe reported "bare works" regardless of version. It now builds the key the
    same way the manager does.
  - `model.name` is module-qualified. Here that is `probe.probe`; for a case that imports
    its workflow it is the full dotted import path, e.g.
    `inverse_convergence.workflow.inverse_convergence`. resolver.py:177 sets
    `impl.name = module + impl.name` and there is no way to alias it shorter.

Settings are the exception that makes this easy to get wrong: get_setting DOES walk
instance prefixes, so short `run.*` setting keys are correct while short resources keys
are not. ci/check_ymmsl.py enforces each with its own rule.

Re-run on the target install to confirm before relying on it.
"""
import sys
from pathlib import Path

import ymmsl
from ymmsl.v0_2 import Configuration, Reference  # 0.16 does not re-export these top level
from ymmsl.v0_2.resolver import resolve
from libmuscle.manager.hammer import flatten

DEFAULT = Path(__file__).parent / "gate_probe.ymmsl"


def load(text):
    cfg = ymmsl.load_as(Configuration, text)
    resolve(Reference("probe"), cfg)
    return cfg


def main() -> int:
    import importlib.metadata as md

    for pkg in ("ymmsl", "muscle3"):
        try:
            print(f"{pkg} {md.version(pkg)}")
        except Exception:
            print(f"{pkg} <no dist metadata>")

    src = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT).read_text()

    print("\n1. INSTANCE NAMES -- the prefix your case setting keys need")
    cfg = load(src)
    print(f"   custom_implementations after resolve(): {dict(cfg.custom_implementations)}")
    print("   (empty => the resolver consumes them; flatten() never sees them)")
    cfg.check_consistent(check_runnable=False)
    flat = flatten(cfg).root_model()
    names = sorted(str(c) for c in flat.components)
    print(f"   instances: {names}")
    print(f"   conduits:  {sorted(str(c) for c in flat.conduits)}")
    assert "spare" not in " ".join(names), "pruning did not take effect"
    print("   pruning: ok (spare absent)")

    print("\n2. custom_implementations key form")
    for form, text in (
        ("probe.run.inner (model-prefixed)", src),
        ("run.inner (bare)", src.replace("probe.run.", "run.")),
    ):
        try:
            load(text)
            print(f"   {form:34s} -> accepted")
        except Exception as e:
            print(f"   {form:34s} -> REJECTED: {str(e).strip().splitlines()[-1][:60]}")

    print("\n3. resources key form -- which one actually takes effect")
    # Ask this the way the manager asks it. instance_manager.py:142 does
    #     configuration.get_resources(model.name + component.name)
    # so probing with a bare Reference("run.inner") tests a lookup that never happens and
    # reports "bare works" on any version. Build the key from the flattened root model.
    for form in ("probe.probe.run.inner", "probe.run.inner", "run.inner", "inner"):
        text = src.replace(
            "custom_implementations:",
            f"resources:\n  {form}: {{threads: 7}}\ncustom_implementations:",
        )
        cfg = flatten(load(text))
        model = cfg.root_model()
        comp = next(c for c in model.components if str(c) == "run.inner")
        res = cfg.get_resources(model.name + comp)
        got = getattr(res, "threads", res)
        note = "  <-- USE THIS" if got == 7 else "  (silently ignored, default 1)"
        print(f"   {form:22s} -> threads={got}{note}")
    print(f"   (root model here is '{model.name}': module name + model name. For a case "
          f"that\n    imports its workflow that is the full dotted import path.)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
