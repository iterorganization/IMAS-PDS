#!/bin/bash

set -euo pipefail

given_dir="pds/ymmsl_files"

for file in "$given_dir"/.*.ymmsl; do
  echo "Processing: $file"
  # Skip . and ..
  [[ "$file" != "$given_dir"/.*.ymmsl ]] && continue

  # Extract filename
  filename=$(basename "$file")
  
  # Remove the leading dot
  new_filename="${filename#.}"

  # Use sed to replace the matching substrings
  sed "s|\[PWD_PLACEHOLDER\]|$(pwd)|g"  "$file" > "$given_dir/$new_filename"
done

