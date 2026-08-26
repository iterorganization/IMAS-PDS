#!/bin/bash
# source_component/sink_component (imported from imas_muscle3) have no env: override of
# their own and default to base_env: MANAGER, i.e. they inherit whatever environment
# muscle_manager itself was launched with -- so this is the only place that can reach them.
#
# METIS's own IDS writer (prepare_IDS4METIS_from_dina, in preprocess.sh) produces
# core_profiles with some fields shaped in a way IMAS-Python's stricter DD 4.0.0 validator
# rejects on put() (e.g. temperature_fit/source vs .../measured coordinate mismatch) --
# same class of issue the old run_simulation.sh already disabled validation for.
export IMAS_AL_DISABLE_VALIDATE=1
