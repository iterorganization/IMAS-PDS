#!/bin/bash

# Should be run from PDS repo directory

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

