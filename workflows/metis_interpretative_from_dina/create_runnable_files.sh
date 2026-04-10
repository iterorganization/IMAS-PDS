set -euo pipefail # stop if anything doesn't work

# Use sed to replace the matching substrings
find "$DIR" -type f -name "*.template" | while read -r template; do
  rel="${template#$DIR/}"                 # relative path
  sub_template="$SUBDIR/$rel"             # possible override
  out="$SUBDIR/${rel%.template}"          # output file

  if [ -f "$sub_template" ]; then
    src="$sub_template"   # SUBDIR wins
  else
    src="$template"       # fallback to DIR
  fi

  mkdir -p "$(dirname "$out")"
  cp "$src" "$out"

  sed -i \
    -e "s|\[BASEDIR_PLACEHOLDER\]|$PWD|g" \
    -e "s|\[SUBDIR_PLACEHOLDER\]|$SUBDIR|g" \
    -e "s|\[SHOT_NR\]|$SHOT_NR|g" \
    "$out"
done
