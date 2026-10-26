#!/bin/bash
# See workflows/metis_from_dina/env.sh -- same fix, same reason.
export IMAS_AL_DISABLE_VALIDATE=1
# Vertical (VS) position loop on, see controllers/KCURR_RZIp/muscle_NICE_input.m.
export NICE_VERTICAL_CONTROL=1
