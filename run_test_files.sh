#!/bin/bash

# Should be run from PDS repo base directory.
# Takes all ymmsl files with a . in front,
# changes [PWD_PLACEHOLDER] to the path of the current PDS installation,
# creates new ymmsl files that can actually be run.

set -euo pipefail

given_dir="ymmsl_files"
source "run/imas_base_env"

# Recursively find all .*.ymmsl and .*.yaml files
for f in "$given_dir"/test*.ymmsl; do
    [ -e "$f" ] || continue
    filename=$(basename "$f")
    mid=$(echo "$filename" | sed -E 's/^(test[^.]*)\.ymmsl$/\1/')
    ts=$(date +"%Y-%m-%d-%H%M%S")
    new="run/tmp/m3_runs/run-$ts-$mid"
    mkdir -p $new
    echo "Running: $f"
    # echo $new
    muscle_manager --start-all $f --run-dir $new
done

