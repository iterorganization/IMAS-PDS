#!/bin/bash

# Should be run from PDS repo base directory.
# Takes all ymmsl/yaml files with a . in front, or ending in .template,
# changes [PWD_PLACEHOLDER] to the path of the current PDS installation,
# creates new files that can actually be run.

set -euo pipefail

given_dir="ymmsl_files"

# Recursively find all .*.ymmsl/.*.yaml and *.template files
find "$given_dir" -type f \( -name ".*" -o -name "*.template" \) | while read -r file; do

  # Extract filename relative to given_dir
  rel_path="${file#$given_dir/}"
  dir_path=$(dirname "$rel_path")
  filename=$(basename "$rel_path")

  # Strip the leading dot, or the .template suffix, whichever applies
  case "$filename" in
    .*) new_name="${filename#.}" ;;
    *.template) new_name="${filename%.template}" ;;
  esac
  new_filename="$given_dir/$dir_path/$new_name"

  # Ensure target directory exists
  mkdir -p "$given_dir/$dir_path"

  # Use sed to replace the matching substrings
  sed "s|\[PWD_PLACEHOLDER\]|$(pwd)|g" "$file" > "$new_filename"
done
