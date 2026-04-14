#!/usr/bin/env bash
# Entrypoint for the full test suite: shell tests, TypeScript tests, Python tests.
#
# By default runs all three stages (matching CI). Pass --shell, --ts, or
# --python to run a single stage during local iteration.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

usage() {
  cat <<'USAGE'
Usage: scripts/run-tests.sh [OPTIONS]

Runs the project's test suites.

Options:
  --shell       Run only shell tests (tests/shell/)
  --ts          Run only TypeScript tests (tests/ts/ via bun)
  --python      Run only Python tests (pytest)
  --actionlint  Run only GitHub Actions workflow lint (actionlint)
  -h, --help    Show this help message

With no options, all stages run in order (the same as CI).
USAGE
}

RUN_SHELL=0
RUN_TS=0
RUN_PYTHON=0
RUN_ACTIONLINT=0

if [[ $# -eq 0 ]]; then
  RUN_SHELL=1
  RUN_TS=1
  RUN_PYTHON=1
  RUN_ACTIONLINT=1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --shell)
      RUN_SHELL=1
      shift
      ;;
    --ts)
      RUN_TS=1
      shift
      ;;
    --python)
      RUN_PYTHON=1
      shift
      ;;
    --actionlint)
      RUN_ACTIONLINT=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ $RUN_SHELL -eq 1 ]]; then
  echo "=== Shell tests ==="
  bash tests/shell/run.sh
  echo ""
fi

if [[ $RUN_TS -eq 1 ]]; then
  echo "=== TypeScript tests ==="
  bun test tests/ts/
  echo ""
fi

if [[ $RUN_PYTHON -eq 1 ]]; then
  echo "=== Python tests ==="
  pytest
  echo ""
fi

if [[ $RUN_ACTIONLINT -eq 1 ]]; then
  echo "=== GitHub Actions workflow lint (actionlint) ==="
  if command -v actionlint >/dev/null 2>&1; then
    actionlint
    echo ""
  else
    # Mirror how bun is treated: if the tool isn't installed locally, print
    # a skip notice and continue. CI installs actionlint explicitly so the
    # lint still gates there.
    echo "actionlint not found on PATH — skipping workflow lint."
    echo "Install it locally with: https://github.com/rhysd/actionlint"
    echo ""
  fi
fi

echo "=== All tests passed ==="
