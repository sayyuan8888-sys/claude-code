#!/usr/bin/env bash
# Tests for scripts/comment-on-duplicates.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMMENT_SH="$REPO_ROOT/scripts/comment-on-duplicates.sh"
FIXTURE_DIR="$SCRIPT_DIR/fixtures"

source "$SCRIPT_DIR/helpers.sh"
setup_stub_path

# ── Helpers ────────────────────────────────────────────────────────

run_comment() {
  local stdout stderr rc
  stdout="$(mktemp)"
  stderr="$(mktemp)"
  reset_stub_calls
  rc=0
  GITHUB_EVENT_PATH="$FIXTURE_DIR/event-payload.json" \
    bash "$COMMENT_SH" "$@" >"$stdout" 2>"$stderr" || rc=$?
  _STDOUT="$(cat "$stdout")"
  _STDERR="$(cat "$stderr")"
  _RC=$rc
  rm -f "$stdout" "$stderr"
}

# ── Tests ──────────────────────────────────────────────────────────

test_single_duplicate() {
  run_comment --potential-duplicates 123
  assert_exit_code 0 "$_RC" || return 1
  assert_file_contains "$GH_STUB_CALLS" "issue comment 42" || return 1
  assert_stdout_contains "Posted duplicate comment" "$_STDOUT" || return 1
}

test_three_duplicates() {
  run_comment --potential-duplicates 1 2 3
  assert_exit_code 0 "$_RC" || return 1
  assert_file_contains "$GH_STUB_CALLS" "issue comment 42" || return 1
}

test_four_duplicates_rejected() {
  run_comment --potential-duplicates 1 2 3 4
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "at most 3" "$_STDERR" || return 1
}

test_no_duplicates_rejected() {
  run_comment --potential-duplicates
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "at least one" "$_STDERR" || return 1
}

test_nonnumeric_duplicate_rejected() {
  run_comment --potential-duplicates abc
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "must be a number" "$_STDERR" || return 1
}

test_unknown_arg_rejected() {
  run_comment --something 123
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "unknown argument" "$_STDERR" || return 1
}

test_missing_event_path() {
  local stdout stderr rc
  stdout="$(mktemp)"
  stderr="$(mktemp)"
  rc=0
  GITHUB_EVENT_PATH="" bash "$COMMENT_SH" --potential-duplicates 123 >"$stdout" 2>"$stderr" || rc=$?
  assert_exit_code 1 "$rc" || return 1
  rm -f "$stdout" "$stderr"
}

# ── Run all tests ─────────────────────────────────────────────────

echo "tests/shell/test_comment_on_duplicates.sh"
run_test test_single_duplicate
run_test test_three_duplicates
run_test test_four_duplicates_rejected
run_test test_no_duplicates_rejected
run_test test_nonnumeric_duplicate_rejected
run_test test_unknown_arg_rejected
run_test test_missing_event_path

print_summary
cleanup_stubs
