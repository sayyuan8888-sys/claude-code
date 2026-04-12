#!/usr/bin/env bash
# Minimal test helper library for shell tests.
# Source this file from each test_*.sh file.

set -euo pipefail

_PASS=0
_FAIL=0
_CURRENT_TEST=""

# ── Assertion helpers ──────────────────────────────────────────────

assert_exit_code() {
  local expected="$1" actual="$2"
  if [[ "$actual" -ne "$expected" ]]; then
    echo "  FAIL: expected exit code $expected, got $actual" >&2
    return 1
  fi
}

assert_stdout_contains() {
  local needle="$1" haystack="$2"
  if [[ "$haystack" != *"$needle"* ]]; then
    echo "  FAIL: stdout missing '$needle'" >&2
    echo "  stdout was: $haystack" >&2
    return 1
  fi
}

assert_stdout_not_contains() {
  local needle="$1" haystack="$2"
  if [[ "$haystack" == *"$needle"* ]]; then
    echo "  FAIL: stdout unexpectedly contains '$needle'" >&2
    return 1
  fi
}

assert_stderr_contains() {
  local needle="$1" haystack="$2"
  if [[ "$haystack" != *"$needle"* ]]; then
    echo "  FAIL: stderr missing '$needle'" >&2
    echo "  stderr was: $haystack" >&2
    return 1
  fi
}

assert_stderr_not_contains() {
  local needle="$1" haystack="$2"
  if [[ "$haystack" == *"$needle"* ]]; then
    echo "  FAIL: stderr unexpectedly contains '$needle'" >&2
    return 1
  fi
}

assert_file_contains() {
  local file="$1" needle="$2"
  if ! grep -qF -- "$needle" "$file" 2>/dev/null; then
    echo "  FAIL: file $file missing '$needle'" >&2
    return 1
  fi
}

# ── Test lifecycle ─────────────────────────────────────────────────

begin_test() {
  _CURRENT_TEST="$1"
}

pass_test() {
  echo "  PASS: $_CURRENT_TEST"
  ((_PASS++)) || true
}

fail_test() {
  echo "  FAIL: $_CURRENT_TEST" >&2
  ((_FAIL++)) || true
}

# Run a test function: captures pass/fail automatically.
run_test() {
  local name="$1"
  begin_test "$name"
  if "$name"; then
    pass_test
  else
    fail_test
  fi
}

# ── Stub setup ─────────────────────────────────────────────────────

STUB_DIR=""
GH_STUB_CALLS=""

setup_stub_path() {
  STUB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/stubs" && pwd)"
  GH_STUB_CALLS="$(mktemp)"
  export PATH="$STUB_DIR:$PATH"
  export GH_STUB_CALLS
  export GH_STUB_MODE="${GH_STUB_MODE:-record}"
  export GH_STUB_STDOUT="${GH_STUB_STDOUT:-}"
}

cleanup_stubs() {
  if [[ -n "${GH_STUB_CALLS:-}" && -f "${GH_STUB_CALLS:-}" ]]; then
    rm -f "$GH_STUB_CALLS"
  fi
}

reset_stub_calls() {
  if [[ -n "${GH_STUB_CALLS:-}" ]]; then
    : > "$GH_STUB_CALLS"
  fi
}

# ── Summary ────────────────────────────────────────────────────────

print_summary() {
  local total=$((_PASS + _FAIL))
  echo ""
  echo "────────────────────────────"
  echo "Results: $total tests, $_PASS passed, $_FAIL failed"
  echo "────────────────────────────"
  if [[ $_FAIL -gt 0 ]]; then
    return 1
  fi
}
