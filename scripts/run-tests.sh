#!/usr/bin/env bash
# Entrypoint for the full test suite: shell tests, TypeScript tests, Python tests.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Shell tests ==="
bash tests/shell/run.sh
echo ""

echo "=== TypeScript tests ==="
bun test tests/ts/
echo ""

echo "=== Python tests ==="
pytest
echo ""

echo "=== All tests passed ==="
