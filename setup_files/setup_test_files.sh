#!/bin/bash

# Should be run from PDS repo base directory.
# Takes all ymmsl files with a . in front,
# changes [PWD_PLACEHOLDER] to the path of the current PDS installation,
# creates new ymmsl files that can actually be run.

set -euo pipefail

given_dir="ymmsl_files"

# Recursively find all .*.ymmsl and .*.yaml files
find "$given_dir" -type f \( -name ".*.ymmsl" -o -name ".*.yaml" \) | while read -r file; do

  # Extract filename relative to given_dir
  rel_path="${file#$given_dir/}"

  # Remove the leading dot from the basename
  dir_path=$(dirname "$rel_path")
  filename=$(basename "$rel_path")
  new_filename="${filename#.}"

  # Ensure target directory exists
  mkdir -p "$given_dir/$dir_path"

  # Skip if already exists
  # if [ -f "$given_dir/$dir_path/$new_filename" ]; then
  #     continue
  # fi

  # echo "Processing: $file"

  # Use sed to replace the matching substrings
  sed "s|\[PWD_PLACEHOLDER\]|$(pwd)|g" "$file" > "$given_dir/$dir_path/$new_filename"
done 
