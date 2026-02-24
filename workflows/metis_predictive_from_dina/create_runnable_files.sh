set -euo pipefail # stop if anything doesn't work

# Use sed to replace the matching substrings
files=(
  "workflow.ymmsl"
)
for file in "${files[@]}"; do
  if test -f "$SUBDIR/.$file"; then
    cp "$SUBDIR/.$file" "$SUBDIR/$file" 
  else
    cp "$DIR/.$file" "$SUBDIR/$file" 
  fi
  sed -i "s|\[BASEDIR_PLACEHOLDER\]|$PWD|g" "$SUBDIR/$file"
  sed -i "s|\[SUBDIR_PLACEHOLDER\]|$SUBDIR|g" "$SUBDIR/$file"
  sed -i "s|\[SHOT_NR\]|$SHOT_NR|g" "$SUBDIR/$file"
done
