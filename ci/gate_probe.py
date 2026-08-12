#!/usr/bin/env python3
"""Verification 0 gate probe -- run this before writing any nested yMMSL.

Everything in the modularisation plan that writes a prefixed key -- every case
setting, every custom_implementations path, every resources entry -- depends on
what this prints. Getting those prefixes wrong is silent: no error, no warning,
just a default quietly used instead of your value.

Usage:  python ci/gate_probe.py [ci/gate_probe.ymmsl]

Needs no scenario data, no actors and no IMAS -- only ymmsl and muscle3.

Measured on muscle3 0.10.0 with ymmsl 0.17.0 and again with ymmsl 0.16.1.dev0 --
same answers on both:

    instance names          run.inner          (nesting path only, no model name)
    custom_implementations  probe.run.inner    (model name REQUIRED; bare form fails)
    resources               run.inner          (instance name; model-prefixed is IGNORED)

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
    for form in ("probe.run.inner", "run.inner", "inner"):
        text = src.replace(
            "custom_implementations:",
            f"resources:\n  {form}: {{threads: 7}}\ncustom_implementations:",
        )
        res = flatten(load(text)).get_resources(Reference("run.inner"))
        got = getattr(res, "threads", res)
        note = "  <-- USE THIS" if got == 7 else "  (silently ignored, default 1)"
        print(f"   {form:18s} -> threads={got}{note}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
