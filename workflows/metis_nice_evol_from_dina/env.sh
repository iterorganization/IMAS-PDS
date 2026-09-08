#!/bin/bash
# See workflows/metis_from_dina/env.sh -- same fix, same reason.
export IMAS_AL_DISABLE_VALIDATE=1
# NICE/3.0.0.dev258's evolutive actor applies received IDS coil voltages without
# the COCOS sign flip it applies to coil currents (nice_imas.cc,
# ReadDataEvolutiveProblemWithRD: signIc = 1, flip commented out), so the plant the
# controller sees is inverted. controllers/KCURR_RZIp/muscle_NICE_input.m negates
# the voltages it sends when this is -1. Kept in this workflow's env.sh so that
# other controller workflows are not affected. Set to 1 / remove once NICE
# converts voltages like currents.
export NICE_VOLTAGE_SIGN=-1
