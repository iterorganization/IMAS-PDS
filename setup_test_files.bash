#!/bin/bash

# Should be run from PDS repo base directory.
# Takes all ymmsl files with a . in front,
# changes [PWD_PLACEHOLDER] to the path of the current PDS installation,
# creates new ymmsl files that can actually be run.

set -euo pipefail

given_dir="ymmsl_files"

for file in "$given_dir"/.*.ymmsl; do
  # Skip . and ..
  [[ "$file" != "$given_dir"/.*.ymmsl ]] && continue

  # Extract filename
  filename=$(basename "$file")
  
  # Remove the leading dot
  new_filename="${filename#.}"

  # Skip if already exists
  if [ -f "$given_dir/$new_filename" ]; then
    continue
  fi

  echo "Processing: $file"
  # Use sed to replace the matching substrings
  sed "s|\[PWD_PLACEHOLDER\]|$(pwd)|g"  "$file" > "$given_dir/$new_filename"
done

