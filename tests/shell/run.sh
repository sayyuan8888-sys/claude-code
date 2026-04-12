#!/usr/bin/env bash
# Shell test runner. Discovers and runs all test_*.sh files in this directory.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OVERALL_EXIT=0

for test_file in "$SCRIPT_DIR"/test_*.sh; do
  [[ -f "$test_file" ]] || continue
  echo "=== Running $(basename "$test_file") ==="
  if bash "$test_file"; then
    echo ""
  else
    echo "^^^ FAILURES in $(basename "$test_file") ^^^"
    echo ""
    OVERALL_EXIT=1
  fi
done

if [[ "$OVERALL_EXIT" -eq 0 ]]; then
  echo "All shell tests passed."
else
  echo "Some shell tests failed." >&2
  exit 1
fi
