set -euo pipefail # stop if anything doesn't work

module load IMAS-Python
module load IDStools/2.3.0

next_path() {
  local base="$1"
  local n=1

  # If the exact path doesn't exist, just return it
  [[ -e "$base" ]] || { echo "$base"; return; }

  # Otherwise find next free numbered name
  while [[ -e "${base}_${n}" ]]; do
    n=$((n + 1))   # arithmetic only on the counter
  done

  echo "${base}_${n}"
}

SUMMARY_URI=$SOURCE_URI

# check if --rerun is among arguments
if [[ " $* " == *" --rerun "* ]]; then
  old_in="$SUBDIR/tmp/data/${SHOT_NR}_in"
  old_in_md="$SUBDIR/tmp/data/${SHOT_NR}_in_md"
  old_out_nice="$SUBDIR/tmp/data/${SHOT_NR}_out_nice"
  old_out_torax="$SUBDIR/tmp/data/${SHOT_NR}_out_torax"
  if [[ -e "$old_in" && -e "$old_in_md" && -e "$old_out_nice" && -e "$old_out_torax" ]]; then
    new_in=$(next_path "$SUBDIR/tmp/data/${SHOT_NR}_in")
    new_in_md=$(next_path "$SUBDIR/tmp/data/${SHOT_NR}_in_md")
    new_out_nice=$(next_path "$SUBDIR/tmp/data/${SHOT_NR}_out_nice")
    new_out_torax=$(next_path "$SUBDIR/tmp/data/${SHOT_NR}_out_torax")
    mv "$old_in" "$new_in"
    mv "$old_in_md" "$new_in_md"
    mv "$old_out_nice" "$new_out_nice"
    mv "$old_out_torax" "$new_out_torax"
    SOURCE_URI="imas:hdf5?path=$new_out_torax"
  else
    echo "No results available yet"
    exit 1
  fi
fi

python $PWD/workflows/utils/convert_dina_data_to_input.py \
  --source_uri $SOURCE_URI \
  --summary_uri $SUMMARY_URI \
  --md_pf_active_uri $MD_PF_ACTIVE \
  --md_pf_passive_uri $MD_PF_PASSIVE \
  --md_wall_uri $MD_WALL \
  --md_iron_core_uri $MD_IRON_CORE \
  --sink_uri $SINK_URI \
  --md_sink_uri $MD_SINK_URI \
  --n_timeslices $N_TIMESLICES

# until IMAS-AL bug is fixed where hdf5 backend does not respect read mode
cp -r "$SUBDIR/tmp/data/${SHOT_NR}_in" "$SUBDIR/tmp/data/${SHOT_NR}_in_waveform_editor"
cp -r "$SUBDIR/tmp/data/${SHOT_NR}_in_md" "$SUBDIR/tmp/data/${SHOT_NR}_in_md_waveform_editor"
