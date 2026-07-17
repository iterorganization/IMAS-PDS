# inverse_convergence

A MUSCLE3 workflow that drives a NICE free-boundary inverse equilibrium and TORAX transport
to a self-consistent pulse via an outer Picard loop. Each iteration the loop sends a
whole-trace pulse (target equilibrium, core_profiles, coil-current seed); the Waveform-Editor
(`we`) overlays the designed Ip(t)/B0 onto the target equilibrium, mirrors core_profiles
through unchanged, imports the ECRH heating, and re-exports the scenario's static
wall/pf_passive/iron_core machine description straight to the NICE load balancer (these three
never change across the pulse or across iterations, so the loop never carries them); a
parallel NICE-inverse load balancer (`nice_lb.py`) solves it per time slice; its equilibrium
goes to TORAX, whose evolved profiles and NICE's coil currents return to the loop. It
converges when the max coil-current change between iterations drops below `loop.tolerance`.
Structure lives in `workflow.ymmsl`; shared knobs in `settings.ymmsl`; per-scenario data paths
in `scenarios/<shot>/settings.ymmsl`; the pulse design (Ip(t)/B0) lives in `waveforms.yaml`.
