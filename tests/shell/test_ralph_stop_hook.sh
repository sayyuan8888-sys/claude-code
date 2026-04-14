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

# Variant of run_hook that also writes a JSONL transcript into $workdir and
# points hook input at it. Used for the deeper tests that exercise the
# promise/text-extraction paths.
#
# Args: <state_body> <transcript_body>
run_hook_with_transcript() {
  local workdir state_body transcript_body
  workdir="$(mktemp -d)"
  state_body="$1"
  transcript_body="$2"

  mkdir -p "$workdir/.claude"
  printf '%s' "$state_body" > "$workdir/.claude/ralph-loop.local.md"
  printf '%s' "$transcript_body" > "$workdir/transcript.jsonl"
  local hook_input
  hook_input="$(jq -n --arg p "$workdir/transcript.jsonl" '{transcript_path: $p}')"

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

# ── Transcript-driven tests ────────────────────────────────────────
#
# These exercise the paths the earlier tests skip: the Perl-based <promise>
# extractor (multiline support + whitespace normalization), the jq-based text
# extractor (filter out tool_use blocks), and the awk prompt extractor
# (preserve `---` inside the prompt body).

test_multiline_promise_is_detected() {
  # completion_promise in state is a single-line literal; the assistant
  # output embeds <promise>...</promise> across multiple lines with extra
  # whitespace. Perl extractor normalizes whitespace → must match.
  local state='---
iteration: 2
max_iterations: 10
completion_promise: "loop done"
---
keep going'
  # One assistant JSONL line with a text content block whose text contains
  # a multi-line <promise> block. The inner newlines and indentation must
  # be collapsed to a single space by the Perl `s/\s+/ /g` normalization.
  local transcript
  transcript=$(jq -c -n '{role:"assistant", message:{content:[{type:"text", text:"here is my answer\n<promise>\n  loop\n  done\n</promise>\nbye"}]}}')
  run_hook_with_transcript "$state" "$transcript"
  assert_exit_code 0 "$_RC" || return 1
  assert_stdout_contains "Detected" "$_STDOUT" || return 1
  assert_stdout_contains "loop done" "$_STDOUT" || return 1
  if [[ "$_STATE_EXISTS" -ne 0 ]]; then
    echo "  FAIL: expected state file to be removed when promise matches" >&2
    return 1
  fi
}

test_tool_use_blocks_are_ignored_when_extracting_text() {
  # Assistant message with interleaved tool_use and text blocks. The jq
  # extractor selects type=="text" only; promise isn't in the text so the
  # loop continues — verifying that tool_use output isn't accidentally
  # treated as assistant text.
  local state='---
iteration: 1
max_iterations: 5
completion_promise: "will-never-appear"
---
The original prompt.'
  local transcript
  transcript=$(jq -c -n '{
    role:"assistant",
    message:{content:[
      {type:"tool_use", name:"Bash", input:{command:"ls"}, id:"toolu_1"},
      {type:"text", text:"Looking at the results..."},
      {type:"tool_use", name:"Read", input:{path:"/tmp/x"}, id:"toolu_2"},
      {type:"text", text:"Nothing conclusive yet."}
    ]}
  }')
  run_hook_with_transcript "$state" "$transcript"
  assert_exit_code 0 "$_RC" || return 1
  # Promise didn't match → hook emits continuation JSON to stdout and
  # bumps iteration. State file must still be present (not removed).
  assert_stdout_contains '"decision": "block"' "$_STDOUT" || return 1
  assert_stdout_contains "Ralph iteration 2" "$_STDOUT" || return 1
  if [[ "$_STATE_EXISTS" -ne 1 ]]; then
    echo "  FAIL: expected state file to persist on continuation" >&2
    return 1
  fi
}

test_prompt_body_preserves_content_around_inner_dashes() {
  # The awk extractor uses `i>=2` (not `i==2`) specifically so that a `---`
  # line inside the prompt body doesn't stop extraction at the 3rd delimiter.
  # This test proves content on both sides of an inner `---` survives.
  # (The `---` line itself is consumed by `i++; next` — that's the current
  # behavior; we lock in the cross-delimiter survival, not the delimiter line.)
  local state='---
iteration: 1
max_iterations: 5
completion_promise: "done"
---
First section of the prompt.

---

Second section after a horizontal rule.'
  local transcript
  transcript=$(jq -c -n '{role:"assistant", message:{content:[{type:"text", text:"not done yet"}]}}')
  run_hook_with_transcript "$state" "$transcript"
  assert_exit_code 0 "$_RC" || return 1
  # reason field in the continuation JSON is the full prompt. Parse it back
  # out of stdout and verify both sections survived past the inner ---.
  local reason
  reason=$(printf '%s' "$_STDOUT" | jq -r '.reason')
  if [[ "$reason" != *"First section"* ]]; then
    echo "  FAIL: reason missing first section, got: $reason" >&2
    return 1
  fi
  if [[ "$reason" != *"Second section"* ]]; then
    echo "  FAIL: reason missing section after inner ---, got: $reason" >&2
    return 1
  fi
}

test_quoted_iteration_is_rejected_loudly() {
  # Regression guard: if someone hand-edits iteration to be quoted
  # (`"5"` instead of `5`), the ^[0-9]+$ regex should fail and the hook
  # should surface the corruption rather than silently treating the quoted
  # form as a number.
  local state='---
iteration: "5"
max_iterations: 10
completion_promise: "done"
---
keep going'
  run_hook "$state"
  assert_exit_code 0 "$_RC" || return 1
  assert_stderr_contains "State file corrupted" "$_STDERR" || return 1
  assert_stderr_contains "iteration" "$_STDERR" || return 1
  # Should include the literal quoted value in the error for debuggability.
  assert_stderr_contains '"5"' "$_STDERR" || return 1
  if [[ "$_STATE_EXISTS" -ne 0 ]]; then
    echo "  FAIL: expected state file to be deleted on corruption" >&2
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
run_test test_multiline_promise_is_detected
run_test test_tool_use_blocks_are_ignored_when_extracting_text
run_test test_prompt_body_preserves_content_around_inner_dashes
run_test test_quoted_iteration_is_rejected_loudly

print_summary
