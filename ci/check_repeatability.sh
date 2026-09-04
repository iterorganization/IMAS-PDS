#!/bin/bash
# Run a test coupling N times and require bit-identical sink outputs.
#   bash ci/check_repeatability.sh ymmsl_files/test_nice_actor.ymmsl [N=2]
# Sinks are found from the sink_uri settings; each run's sinks are kept under
# cases/runs/repeat_<name>/run<i>/ and compared with ci/compare_ids.py (exact).
set -euo pipefail
ymmsl=$1
n=${2:-2}
name=$(basename "$ymmsl" .ymmsl)
out="cases/runs/repeat_$name"
sinks=$(grep -o 'sink_uri: *"imas:hdf5?path=[^"]*"' "$ymmsl" | sed 's/.*path=//; s/"$//' | sort -u)
[ -n "$sinks" ] || { echo "no sink_uri settings in $ymmsl" >&2; exit 2; }

rm -rf "$out"
for i in $(seq 1 "$n"); do
  rm -rf $sinks
  mkdir -p "$out/run$i"
  muscle_manager --start-all --run-dir "$out/run$i" "$ymmsl"
  for s in $sinks; do cp -r "$s" "$out/run$i/$(basename "$s")"; done
done

status=0
for i in $(seq 2 "$n"); do
  for s in $sinks; do
    b=$(basename "$s")
    echo "== $b: run1 vs run$i"
    python ci/compare_ids.py "$out/run1/$b" "$out/run$i/$b" || status=1
  done
done
exit $status
