#!/bin/bash

# Usage: ./script.sh /path/to/ymmsl_dir /new/path
# Usage: bash ./script.sh . ~/gitrepos/pds

set -euo pipefail

# Check that exactly 2 arguments are provided
if [[ $# -ne 2 ]]; then
  echo "❌ Usage: $0 <ymmsl_dir> <new_path>"
  echo "   Both arguments are required."
  exit 1
fi

# Arguments
ymmsl_dir="$1"
new_path="$2"

if [[ ! -d "$ymmsl_dir" ]]; then
  echo "❌ Error: '$ymmsl_dir' is not a valid directory."
  exit 1
fi

# Loop through all test_*.ymmsl files in the given directory
for file in "$ymmsl_dir"/test_*.ymmsl; do
  echo "Processing: $file"
  # Use sed to replace the matching substrings
  sed -i -E "s|(imas:hdf5\?path=)[^ ]*(ymmsl_files/input/*)|\1$new_path/\2|g" "$file"
  sed -i -E "s|(imas:hdf5\?path=)[^ ]*(ymmsl_files/output/*)|\1$new_path/\2|g" "$file"
done

