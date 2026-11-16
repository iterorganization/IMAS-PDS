"""ip_waveform_export: one designer-level Ip reference with segments, three exports.

Phase P3 prototype of the PSPS-to-KCURR data-chain plan, sections 6-7 (the study notes, kept outside this repository):
Waveform-Editor-style YAML -> RefGen XML (PCSSP PSC), best-guess PSPS "WF" JSON,
IMAS pulse_schedule IDS; P5-seed validation (validate.py) and a PROPOSED
exception-handling example (export_refgen_eh_example.py). See README.md.
"""

from .model import (
    CONVENTION_IMAS,
    CONVENTION_MINUS_IP,
    DEFAULT_STOP_ID,
    IpWaveform,
    PulseDesign,
    Segment,
    ValidationError,
    segment_points,
    validate,
)
from .read_yaml import load_design

__all__ = [
    "CONVENTION_IMAS",
    "CONVENTION_MINUS_IP",
    "DEFAULT_STOP_ID",
    "IpWaveform",
    "PulseDesign",
    "Segment",
    "ValidationError",
    "load_design",
    "segment_points",
    "validate",
]
