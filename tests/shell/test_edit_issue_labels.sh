#!/usr/bin/env bash
# Tests for scripts/edit-issue-labels.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
EDIT_SH="$REPO_ROOT/scripts/edit-issue-labels.sh"
FIXTURE_DIR="$SCRIPT_DIR/fixtures"

source "$SCRIPT_DIR/helpers.sh"
setup_stub_path

# Provide valid labels for the label-list call
export GH_STUB_LABEL_LIST=$'bug\nneeds-triage\nstale\nneeds-info\nfeature'

# ── Helpers ────────────────────────────────────────────────────────

run_edit() {
  local stdout stderr rc
  stdout="$(mktemp)"
  stderr="$(mktemp)"
  reset_stub_calls
  rc=0
  GITHUB_EVENT_PATH="$FIXTURE_DIR/event-payload.json" \
    bash "$EDIT_SH" "$@" >"$stdout" 2>"$stderr" || rc=$?
  _STDOUT="$(cat "$stdout")"
  _STDERR="$(cat "$stderr")"
  _RC=$rc
  rm -f "$stdout" "$stderr"
}

# ── Tests ──────────────────────────────────────────────────────────

test_add_and_remove_labels() {
  run_edit --add-label bug --remove-label stale
  assert_exit_code 0 "$_RC" || return 1
  assert_file_contains "$GH_STUB_CALLS" "issue edit 42 --add-label bug --remove-label stale" || return 1
  assert_stdout_contains "Added: bug" "$_STDOUT" || return 1
  assert_stdout_contains "Removed: stale" "$_STDOUT" || return 1
}

test_add_label_only() {
  run_edit --add-label needs-triage
  assert_exit_code 0 "$_RC" || return 1
  assert_file_contains "$GH_STUB_CALLS" "--add-label needs-triage" || return 1
}

test_remove_label_only() {
  run_edit --remove-label stale
  assert_exit_code 0 "$_RC" || return 1
  assert_file_contains "$GH_STUB_CALLS" "--remove-label stale" || return 1
}

test_unknown_arg_rejected() {
  run_edit --delete bug
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "unknown argument" "$_STDERR" || return 1
}

test_no_labels_exits_1() {
  local stdout stderr rc
  stdout="$(mktemp)"
  stderr="$(mktemp)"
  rc=0
  GITHUB_EVENT_PATH="$FIXTURE_DIR/event-payload.json" \
    bash "$EDIT_SH" >"$stdout" 2>"$stderr" || rc=$?
  assert_exit_code 1 "$rc" || return 1
  rm -f "$stdout" "$stderr"
}

test_missing_event_path() {
  local stdout stderr rc
  stdout="$(mktemp)"
  stderr="$(mktemp)"
  rc=0
  GITHUB_EVENT_PATH="" bash "$EDIT_SH" --add-label bug >"$stdout" 2>"$stderr" || rc=$?
  assert_exit_code 1 "$rc" || return 1
  rm -f "$stdout" "$stderr"
}

test_nonnumeric_issue_in_payload() {
  local bad_payload rc stdout stderr
  bad_payload="$(mktemp)"
  echo '{"issue": {"number": "abc"}}' > "$bad_payload"
  stdout="$(mktemp)"
  stderr="$(mktemp)"
  rc=0
  GITHUB_EVENT_PATH="$bad_payload" \
    bash "$EDIT_SH" --add-label bug >"$stdout" 2>"$stderr" || rc=$?
  assert_exit_code 1 "$rc" || return 1
  assert_stderr_contains "no issue number" "$(cat "$stderr")" || return 1
  rm -f "$bad_payload" "$stdout" "$stderr"
}

test_nonexistent_label_filtered() {
  # "nonexistent" is not in GH_STUB_LABEL_LIST, so it should be filtered out.
  # With only nonexistent labels, the script exits 0 without calling gh issue edit.
  run_edit --add-label nonexistent
  assert_exit_code 0 "$_RC" || return 1
  # The stub should have been called only for "label list", not "issue edit"
  assert_stdout_not_contains "Added:" "$_STDOUT" || return 1
}

# ── Run all tests ─────────────────────────────────────────────────

echo "tests/shell/test_edit_issue_labels.sh"
run_test test_add_and_remove_labels
run_test test_add_label_only
run_test test_remove_label_only
run_test test_unknown_arg_rejected
run_test test_no_labels_exits_1
run_test test_missing_event_path
run_test test_nonnumeric_issue_in_payload
run_test test_nonexistent_label_filtered

print_summary
cleanup_stubs
