#!/usr/bin/env bash
# Tests for plugins/ralph-wiggum/hooks/stop-hook.sh
#
# The stop hook reads a state file at .claude/ralph-loop.local.md in $PWD.
# These tests exercise the paths that don't require constructing a full
# JSONL transcript: no-state (fast exit), corrupted state, and max-iterations.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK_SH="$REPO_ROOT/plugins/ralph-wiggum/hooks/stop-hook.sh"

source "$SCRIPT_DIR/helpers.sh"

# ── Helpers ────────────────────────────────────────────────────────

# Run the hook in an isolated working directory, feeding a minimal hook-input
# JSON on stdin. Captures exit code, stdout, stderr, and whether the state
# file survived.
run_hook() {
  local workdir state_body hook_input
  workdir="$(mktemp -d)"
  state_body="$1"
  # Default hook input: transcript path that doesn't exist. A literal default
  # inside `${2:-...}` doesn't play well with `}` in the value, so use a
  # plain conditional.
  if [[ -n "${2:-}" ]]; then
    hook_input="$2"
  else
    hook_input='{"transcript_path":"/nonexistent"}'
  fi

  if [[ -n "$state_body" ]]; then
    mkdir -p "$workdir/.claude"
    printf '%s' "$state_body" > "$workdir/.claude/ralph-loop.local.md"
  fi

  local stdout stderr rc
  stdout="$(mktemp)"
  stderr="$(mktemp)"
  rc=0
  (cd "$workdir" && printf '%s' "$hook_input" | bash "$HOOK_SH") \
    >"$stdout" 2>"$stderr" || rc=$?

  _STDOUT="$(cat "$stdout")"
  _STDERR="$(cat "$stderr")"
  _RC=$rc
  _STATE_EXISTS=0
  [[ -f "$workdir/.claude/ralph-loop.local.md" ]] && _STATE_EXISTS=1

  rm -f "$stdout" "$stderr"
  rm -rf "$workdir"
}

# ── Tests ──────────────────────────────────────────────────────────

test_no_state_file_exits_silently() {
  run_hook ""
  assert_exit_code 0 "$_RC" || return 1
  # No state, no ralph loop: stdout and stderr should be empty.
  if [[ -n "$_STDOUT" ]]; then
    echo "  FAIL: expected empty stdout, got: $_STDOUT" >&2
    return 1
  fi
}

test_corrupt_iteration_removes_state_and_warns() {
  local state='---
iteration: not-a-number
max_iterations: 5
completion_promise: "done"
---
keep going'
  run_hook "$state"
  assert_exit_code 0 "$_RC" || return 1
  assert_stderr_contains "State file corrupted" "$_STDERR" || return 1
  assert_stderr_contains "iteration" "$_STDERR" || return 1
  if [[ "$_STATE_EXISTS" -ne 0 ]]; then
    echo "  FAIL: expected state file to be deleted on corruption" >&2
    return 1
  fi
}

test_corrupt_max_iterations_removes_state_and_warns() {
  local state='---
iteration: 1
max_iterations: abc
completion_promise: "done"
---
keep going'
  run_hook "$state"
  assert_exit_code 0 "$_RC" || return 1
  assert_stderr_contains "max_iterations" "$_STDERR" || return 1
  if [[ "$_STATE_EXISTS" -ne 0 ]]; then
    echo "  FAIL: expected state file to be deleted on corruption" >&2
    return 1
  fi
}

test_max_iterations_reached_removes_state() {
  local state='---
iteration: 5
max_iterations: 5
completion_promise: "done"
---
keep going'
  run_hook "$state"
  assert_exit_code 0 "$_RC" || return 1
  assert_stdout_contains "Max iterations" "$_STDOUT" || return 1
  if [[ "$_STATE_EXISTS" -ne 0 ]]; then
    echo "  FAIL: expected state file to be deleted when limit hit" >&2
    return 1
  fi
}

test_missing_transcript_removes_state() {
  # Below max iterations but transcript_path points at a nonexistent file.
  local state='---
iteration: 1
max_iterations: 5
completion_promise: "done"
---
keep going'
  run_hook "$state" '{"transcript_path":"/definitely/does/not/exist"}'
  assert_exit_code 0 "$_RC" || return 1
  assert_stderr_contains "Transcript file not found" "$_STDERR" || return 1
  if [[ "$_STATE_EXISTS" -ne 0 ]]; then
    echo "  FAIL: expected state file to be deleted on transcript error" >&2
    return 1
  fi
}

# ── Run all tests ─────────────────────────────────────────────────

echo "tests/shell/test_ralph_stop_hook.sh"
run_test test_no_state_file_exits_silently
run_test test_corrupt_iteration_removes_state_and_warns
run_test test_corrupt_max_iterations_removes_state_and_warns
run_test test_max_iterations_reached_removes_state
run_test test_missing_transcript_removes_state

print_summary
