"""P5 seed: validate.check / --validate."""

from __future__ import annotations

from pathlib import Path

import pytest

from ip_waveform_export import IpWaveform, PulseDesign, Segment, load_design
from ip_waveform_export.validate import (
    DEFAULT_LIMITS,
    Limits,
    check,
    load_limits,
    report,
)

TOOL = Path(__file__).resolve().parent.parent
EXAMPLE = TOOL / "examples" / "ip_105073_like.yaml"
CLI = TOOL / "ip_waveform_export.py"


def _design(values, segs=None):
    wf = IpWaveform(time=[0.0, 10.0, 20.0, 60.0, 80.0], value=values)
    segs = segs or [
        Segment("ramp-up", 0, 0.0, 20.0, "flat-top"),
        Segment("flat-top", 1, 20.0, 60.0, "ramp-down"),
        Segment("ramp-down", 2, 60.0, 80.0, "STOP"),
        Segment("STOP", 99, 80.0, 80.0, None),
    ]
    return PulseDesign(waveform=wf, segments=segs, name="v")


def test_limits_file_is_placeholder():
    lim = load_limits()
    assert lim.status == "PLACEHOLDER"
    assert lim.ip_abs_max == pytest.approx(15.0e6)
    assert lim.dip_dt_abs_max == pytest.approx(0.3e6)
    assert lim.flat_top_min_duration == pytest.approx(50.0)
    text = DEFAULT_LIMITS.read_text()
    assert "PSCGlobalMonConfig.xml:17-19" in text and "OLC" in text


def test_example_passes():
    v = check(load_design(EXAMPLE), load_limits())
    assert v == []
    assert "OK" in report(v, load_limits()) and "PLACEHOLDER" in report(
        v, load_limits()
    )


def test_limit_violations_located():
    # 0 -> -5 MA in 10 s = 0.5 MA/s (ramp-up); |Ip| 15.5 MA in the flat-top; flat-top 40 s
    d = _design([0.0, -5.0e6, -15.5e6, -15.5e6, -1.0e6])
    v = check(d, load_limits())
    rules = {(x.rule, x.segment, x.time) for x in v}
    assert ("dip_dt_abs_max", "ramp-up", 0.0) in rules
    assert ("dip_dt_abs_max", "ramp-up", 10.0) in rules  # 1.05 MA/s
    assert ("ip_abs_max", "flat-top", 20.0) in rules
    assert ("ip_abs_max", "ramp-down", 60.0) in rules  # t = 60 s starts the ramp-down
    assert ("flat_top_min_duration", "flat-top", 20.0) in rules
    assert ("dip_dt_abs_max", "ramp-down", 60.0) in rules  # 0.725 MA/s
    assert all(x.limit is not None for x in v)
    assert "violation(s)" in report(v)


def test_structure_reported_not_raised():
    segs = [
        Segment("ramp-up", 0, 0.0, 20.0, "flat-top"),
        Segment("flat-top", 0, 21.0, 80.0, "STOP"),  # gap + duplicate id
        Segment("STOP", 99, 80.0, 80.0, None),
    ]
    v = check(_design([0.0, -1e6, -2e6, -2e6, -1e6], segs), Limits())
    assert v and all(x.rule == "structure" for x in v)
    msgs = " ".join(x.message for x in v)
    assert "not unique" in msgs and "not contiguous" in msgs


def test_cli_validate(tmp_path):
    import subprocess
    import sys

    ok = subprocess.run(
        [sys.executable, "-I", str(CLI), "--yaml", str(EXAMPLE), "--validate"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0 and "OK: no violation" in ok.stdout
    lim = tmp_path / "strict.yaml"
    lim.write_text("status: TEST\nlimits:\n  dip_dt_abs_max_MA_per_s: {value: 0.1}\n")
    bad = subprocess.run(
        [
            sys.executable,
            "-I",
            str(CLI),
            "--yaml",
            str(EXAMPLE),
            "--validate",
            "--limits",
            str(lim),
            "--refgen",
            "--out-dir",
            str(tmp_path / "o"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode == 4 and "dip_dt_abs_max" in bad.stdout
    assert not (tmp_path / "o").exists()  # no export when violations are found
