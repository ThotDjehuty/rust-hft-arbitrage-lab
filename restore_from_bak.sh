#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
echo "Running restore in: $ROOT"
found=0
restored=0
missing=0

# find Cargo.toml files in repo
mapfile -t files < <(find . -type f -name Cargo.toml)

for f in "${files[@]}"; do
  # check if file contains the broken literal
  if grep -q '\$content' "$f" || grep -q '"\$content"' "$f"; then
    found=$((found+1))
    bak="${f}.bak"
    if [ -f "$bak" ]; then
      echo "Restoring: $f <- $bak"
      mv -f "$bak" "$f"
      restored=$((restored+1))
    else
      echo "Backup not found for $f (expected $bak). Please restore manually." >&2
      missing=$((missing+1))
    fi
  fi
done

echo "Summary: broken-files-found=$found restored=$restored missing-backups=$missing"

if [ "$found" -eq 0 ]; then
  echo "No Cargo.toml files containing \$content were found. Nothing changed."
else
  echo "Run 'git status' to review changes, then 'cargo update' and 'cargo build --workspace' when ready."
fi

