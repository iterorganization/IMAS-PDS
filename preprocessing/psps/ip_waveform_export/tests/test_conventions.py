"""Decisions of 2026-11-02: D11 sign convention, D10 time origin, D8 identifiers."""

from __future__ import annotations

import textwrap
from pathlib import Path

import numpy as np
import pytest

from ip_waveform_export import ValidationError, load_design

TOOL = Path(__file__).resolve().parent.parent
EXAMPLE = TOOL / "examples" / "ip_105073_like.yaml"


def _yaml(tmp_path: Path, values: str, glob: str = "", entry_conv: str = "") -> Path:
    conv = f"convention: {entry_conv}, " if entry_conv else ""
    text = textwrap.dedent(
        f"""\
        globals: {{name: t{glob}}}
        references:
          pulse_schedule/flux_control/ip/reference:
            - {{{conv}time: [0, 10, 20], value: {values}}}
        segments:
          - {{name: ramp-up, id: 0, start: 0.0, end: 10.0}}
          - {{name: flat-top, id: 1, end: 20.0}}
          - {{name: STOP, id: 99}}
        """
    )
    p = tmp_path / "d.yaml"
    p.write_text(text)
    return p


def test_example_is_minus_ip_and_model_is_imas():
    d = load_design(EXAMPLE)
    assert d.convention == "minus_ip"
    assert np.all(d.waveform.value <= 0.0)  # IMAS sign in the model (ITER Ip < 0)
    assert d.waveform.value.min() == pytest.approx(-15.0e6)


def test_example_d8_identifiers():
    d = load_design(EXAMPLE)
    assert [(s.name, s.id) for s in d.segments] == [
        ("ramp-up", 0),
        ("flat-top", 1),
        ("ramp-down", 2),
        ("STOP", 99),
    ]


def test_minus_ip_default_and_imas_equivalent(tmp_path):
    a = load_design(_yaml(tmp_path, "[0, 5.0e6, 5.0e6]"))  # default = minus_ip
    b = load_design(_yaml(tmp_path, "[0, -5.0e6, -5.0e6]", entry_conv="imas"))
    c = load_design(_yaml(tmp_path, "[0, -5.0e6, -5.0e6]", glob=", convention: imas"))
    assert a.convention == "minus_ip" and b.convention == c.convention == "imas"
    assert np.array_equal(a.waveform.value, b.waveform.value)
    assert np.array_equal(b.waveform.value, c.waveform.value)
    assert np.all(a.waveform.value <= 0.0)


def test_minus_ip_rejects_negative_values(tmp_path):
    with pytest.raises(
        ValidationError, match="minus_ip.*negative values found at t=10"
    ):
        load_design(_yaml(tmp_path, "[0, -5.0e6, 5.0e6]"))


def test_convention_errors(tmp_path):
    with pytest.raises(ValidationError, match="unknown"):
        load_design(_yaml(tmp_path, "[0, 1, 1]", entry_conv="pcs"))
    with pytest.raises(ValidationError, match="disagrees"):
        load_design(
            _yaml(
                tmp_path, "[0, 1, 1]", glob=", convention: imas", entry_conv="minus_ip"
            )
        )


def test_time_origin(tmp_path):
    d = load_design(_yaml(tmp_path, "[0, 1, 1]", glob=", time_offset_s: 3.5"))
    assert d.time_origin == "plasma_initiation" and d.time_offset_s == 3.5
    for reserved in ("control_handover_T0", "dina"):
        with pytest.raises(ValidationError, match="reserved value"):
            load_design(_yaml(tmp_path, "[0, 1, 1]", glob=f", time_origin: {reserved}"))
    with pytest.raises(ValidationError, match="unknown"):
        load_design(_yaml(tmp_path, "[0, 1, 1]", glob=", time_origin: breakdown"))
