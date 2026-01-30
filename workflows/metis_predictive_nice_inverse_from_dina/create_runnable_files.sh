set -euo pipefail # stop if anything doesn't work

# get psi_offset
source $PWD/tmp/PSI_OFFSET
echo PSI_OFFSET = $PSI_OFFSET

# Use sed to replace the matching substrings
files=(
  "workflow.ymmsl"
  "param.xml"
)
for file in "${files[@]}"; do
  if test -f "$SUBDIR/.$file"; then
    echo "Use local configuration file $file"
    cp "$SUBDIR/.$file" "$SUBDIR/$file" 
  else
    echo "Use default configuration file $file"
    cp "$DIR/.$file" "$SUBDIR/$file" 
  fi
  sed -i "s|\[BASEDIR_PLACEHOLDER\]|$PWD|g" "$SUBDIR/$file"
  sed -i "s|\[SUBDIR_PLACEHOLDER\]|$SUBDIR|g" "$SUBDIR/$file"
  sed -i "s|\[SHOT_NR\]|$SHOT_NR|g" "$SUBDIR/$file"
  sed -i "s|\[PSI_OFFSET\]|$PSI_OFFSET|g" "$SUBDIR/$file"
done
