# prescribed_transport

A minimal MUSCLE3 chain -- `source -> waveform_editor -> nice_inv -> sink` -- that produces a
"prescribed" (fixed, not self-consistently coupled to transport) NICE free-boundary equilibrium
dataset for one scenario. The waveform editor overlays the designed
Ip(t)/B0 boundary target
(`waveforms.yaml`) onto the source's raw equilibrium and supplies the static machine
description (wall, pf_passive, iron_core) plus the coil-current seed (pf_active), all imported
from `waveforms.yaml` rather than carried through `source`. NICE-inverse solves the
free-boundary equilibrium per time slice; `sink` stores its resulting equilibrium and coil
currents.
