#!/usr/bin/env bash
# Tests for scripts/gh.sh — the hardened gh CLI wrapper.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GH_SH="$REPO_ROOT/scripts/gh.sh"

source "$SCRIPT_DIR/helpers.sh"
setup_stub_path

# ── Helpers ────────────────────────────────────────────────────────

# Run gh.sh with GH_REPO set, capture stdout/stderr/exit code.
run_gh() {
  local stdout stderr rc
  stdout="$(mktemp)"
  stderr="$(mktemp)"
  reset_stub_calls
  rc=0
  GH_REPO="owner/repo" bash "$GH_SH" "$@" >"$stdout" 2>"$stderr" || rc=$?
  _STDOUT="$(cat "$stdout")"
  _STDERR="$(cat "$stderr")"
  _RC=$rc
  rm -f "$stdout" "$stderr"
}

# Run gh.sh with a custom GH_REPO value (for malformed-repo tests).
run_gh_custom_repo() {
  local repo_val="$1"; shift
  local stdout stderr rc
  stdout="$(mktemp)"
  stderr="$(mktemp)"
  reset_stub_calls
  rc=0
  GH_REPO="$repo_val" GITHUB_REPOSITORY="" bash "$GH_SH" "$@" >"$stdout" 2>"$stderr" || rc=$?
  _STDOUT="$(cat "$stdout")"
  _STDERR="$(cat "$stderr")"
  _RC=$rc
  rm -f "$stdout" "$stderr"
}

# Run gh.sh with GH_REPO and GITHUB_REPOSITORY both unset.
run_gh_no_repo() {
  local stdout stderr rc
  stdout="$(mktemp)"
  stderr="$(mktemp)"
  reset_stub_calls
  rc=0
  GH_REPO="" GITHUB_REPOSITORY="" bash "$GH_SH" "$@" >"$stdout" 2>"$stderr" || rc=$?
  _STDOUT="$(cat "$stdout")"
  _STDERR="$(cat "$stderr")"
  _RC=$rc
  rm -f "$stdout" "$stderr"
}

# ── Allowed subcommand tests ──────────────────────────────────────

test_issue_view() {
  run_gh issue view 123
  assert_exit_code 0 "$_RC" || return 1
  assert_file_contains "$GH_STUB_CALLS" "issue view 123" || return 1
}

test_issue_view_with_comments() {
  run_gh issue view 456 --comments
  assert_exit_code 0 "$_RC" || return 1
  assert_file_contains "$GH_STUB_CALLS" "--comments" || return 1
}

test_issue_list() {
  run_gh issue list --state open --limit 20
  assert_exit_code 0 "$_RC" || return 1
  assert_file_contains "$GH_STUB_CALLS" "issue list" || return 1
}

test_search_issues() {
  run_gh search issues "bug report" --limit 10
  assert_exit_code 0 "$_RC" || return 1
  assert_file_contains "$GH_STUB_CALLS" "search issues" || return 1
}

test_label_list() {
  run_gh label list --limit 100
  assert_exit_code 0 "$_RC" || return 1
  assert_file_contains "$GH_STUB_CALLS" "label list" || return 1
}

test_issue_list_with_label_flag() {
  run_gh issue list --label bug
  assert_exit_code 0 "$_RC" || return 1
  assert_file_contains "$GH_STUB_CALLS" "--label bug" || return 1
}

test_flag_equals_syntax() {
  run_gh issue list --state=open --limit=5
  assert_exit_code 0 "$_RC" || return 1
  assert_file_contains "$GH_STUB_CALLS" "--state=open" || return 1
}

# ── Denied subcommand tests ───────────────────────────────────────

test_deny_issue_edit() {
  run_gh issue edit 123
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "only" "$_STDERR" || return 1
}

test_deny_issue_comment() {
  run_gh issue comment 123
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "only" "$_STDERR" || return 1
}

test_deny_issue_close() {
  run_gh issue close 123
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "only" "$_STDERR" || return 1
}

test_deny_pr_view() {
  run_gh pr view 123
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "only" "$_STDERR" || return 1
}

test_deny_repo_view() {
  run_gh repo view
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "only" "$_STDERR" || return 1
}

test_deny_no_subcommand() {
  run_gh issue
  assert_exit_code 1 "$_RC" || return 1
}

# ── Denied flag tests ─────────────────────────────────────────────

test_deny_json_flag() {
  run_gh issue list --json title
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "only --comments" "$_STDERR" || return 1
}

test_deny_jq_flag() {
  run_gh issue list --jq '.title'
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "only --comments" "$_STDERR" || return 1
}

test_deny_web_flag() {
  run_gh issue view 123 --web
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "only --comments" "$_STDERR" || return 1
}

test_deny_repo_flag() {
  run_gh issue list --repo other/repo
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "only --comments" "$_STDERR" || return 1
}

# ── Search qualifier rejection ────────────────────────────────────

test_deny_search_repo_qualifier() {
  run_gh search issues "repo:foo/bar hello" --limit 5
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "must not contain" "$_STDERR" || return 1
}

test_deny_search_org_qualifier() {
  run_gh search issues "org:anthropic bugs" --limit 5
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "must not contain" "$_STDERR" || return 1
}

test_deny_search_user_qualifier() {
  run_gh search issues "user:bob issue" --limit 5
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "must not contain" "$_STDERR" || return 1
}

test_deny_search_repo_qualifier_uppercase() {
  run_gh search issues "REPO:foo/bar hello" --limit 5
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "must not contain" "$_STDERR" || return 1
}

test_deny_search_embedded_qualifier() {
  run_gh search issues "hello repo:x world" --limit 5
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "must not contain" "$_STDERR" || return 1
}

# ── issue view validation ─────────────────────────────────────────

test_issue_view_nonnumeric() {
  run_gh issue view abc
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "numeric" "$_STDERR" || return 1
}

test_issue_view_multiple_positional() {
  run_gh issue view 123 456
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "exactly one" "$_STDERR" || return 1
}

test_issue_view_no_arg() {
  run_gh issue view
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "exactly one" "$_STDERR" || return 1
}

# ── issue list / label list positional rejection ──────────────────

test_issue_list_positional_rejected() {
  run_gh issue list 123
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "do not accept positional" "$_STDERR" || return 1
}

test_label_list_positional_rejected() {
  run_gh label list somename
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "do not accept positional" "$_STDERR" || return 1
}

# ── Environment precondition tests ────────────────────────────────

test_no_repo_env() {
  run_gh_no_repo issue view 123
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "GH_REPO" "$_STDERR" || return 1
}

test_malformed_repo_no_slash() {
  run_gh_custom_repo "noslash" issue view 123
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "owner/repo" "$_STDERR" || return 1
}

test_malformed_repo_too_many_slashes() {
  run_gh_custom_repo "a/b/c" issue view 123
  assert_exit_code 1 "$_RC" || return 1
  assert_stderr_contains "owner/repo" "$_STDERR" || return 1
}

# ── Run all tests ─────────────────────────────────────────────────

echo "tests/shell/test_gh_wrapper.sh"
run_test test_issue_view
run_test test_issue_view_with_comments
run_test test_issue_list
run_test test_search_issues
run_test test_label_list
run_test test_issue_list_with_label_flag
run_test test_flag_equals_syntax
run_test test_deny_issue_edit
run_test test_deny_issue_comment
run_test test_deny_issue_close
run_test test_deny_pr_view
run_test test_deny_repo_view
run_test test_deny_no_subcommand
run_test test_deny_json_flag
run_test test_deny_jq_flag
run_test test_deny_web_flag
run_test test_deny_repo_flag
run_test test_deny_search_repo_qualifier
run_test test_deny_search_org_qualifier
run_test test_deny_search_user_qualifier
run_test test_deny_search_repo_qualifier_uppercase
run_test test_deny_search_embedded_qualifier
run_test test_issue_view_nonnumeric
run_test test_issue_view_multiple_positional
run_test test_issue_view_no_arg
run_test test_issue_list_positional_rejected
run_test test_label_list_positional_rejected
run_test test_no_repo_env
run_test test_malformed_repo_no_slash
run_test test_malformed_repo_too_many_slashes

print_summary
cleanup_stubs
