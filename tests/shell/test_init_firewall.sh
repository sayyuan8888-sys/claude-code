#!/usr/bin/env bash
# Tests for .devcontainer/init-firewall.sh — the devcontainer sandbox firewall setup.
#
# The real script requires root and mutates host networking. We isolate every
# external command via stubs under tests/shell/stubs/firewall/ so the test
# suite can run unprivileged and offline.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FW_SH="$REPO_ROOT/.devcontainer/init-firewall.sh"
FIXTURES="$SCRIPT_DIR/fixtures"

source "$SCRIPT_DIR/helpers.sh"
# helpers.sh defines STUB_DIR="" at the top level, so declare ours after.
FW_STUB_DIR="$SCRIPT_DIR/stubs/firewall"

export FW_STUB_CALLS=""

_reset_env() {
  export PATH="$FW_STUB_DIR:$REPO_ROOT/tests/shell/stubs:/usr/local/bin:/usr/bin:/bin"
  FW_STUB_CALLS="$(mktemp)"
  export FW_STUB_CALLS
  # Clear per-test overrides so leftover state from one case doesn't leak.
  unset FW_CURL_META_FIXTURE FW_CURL_EXAMPLE_EXIT FW_CURL_GH_ZEN_EXIT
  unset FW_DIG_MAP FW_DIG_FORCE_BAD_IP
  unset FW_IPTABLES_SAVE_OUT FW_IP_ROUTE_OUT
}

# Run init-firewall.sh, capture stdout+stderr+exit.
run_fw() {
  local stdout stderr rc
  stdout="$(mktemp)"
  stderr="$(mktemp)"
  rc=0
  bash "$FW_SH" >"$stdout" 2>"$stderr" || rc=$?
  _STDOUT="$(cat "$stdout")"
  _STDERR="$(cat "$stderr")"
  _RC=$rc
  rm -f "$stdout" "$stderr"
}

# ── Happy path ─────────────────────────────────────────────────────

test_happy_path_sets_default_drop_and_populates_ipset() {
  _reset_env
  export FW_CURL_META_FIXTURE="$FIXTURES/github-meta.json"
  export FW_DIG_MAP="$FIXTURES/init-firewall-dns-map.tsv"

  run_fw
  assert_exit_code 0 "$_RC" || return 1
  # Default policies set to DROP on all three chains.
  assert_file_contains "$FW_STUB_CALLS" "iptables -P INPUT DROP" || return 1
  assert_file_contains "$FW_STUB_CALLS" "iptables -P FORWARD DROP" || return 1
  assert_file_contains "$FW_STUB_CALLS" "iptables -P OUTPUT DROP" || return 1
  # ipset created and at least one GitHub CIDR added.
  assert_file_contains "$FW_STUB_CALLS" "ipset create allowed-domains hash:net" || return 1
  assert_file_contains "$FW_STUB_CALLS" "ipset add allowed-domains 140.82.112.0/20" || return 1
  # Each configured domain resolved and its IP added.
  assert_file_contains "$FW_STUB_CALLS" "ipset add allowed-domains 160.79.104.10" || return 1
  # Final verification outputs the success message.
  assert_stdout_contains "Firewall configuration complete" "$_STDOUT" || return 1
  assert_stdout_contains "unable to reach https://example.com as expected" "$_STDOUT" || return 1
}

# ── Failure modes ──────────────────────────────────────────────────

test_github_api_fetch_failure_exits_1() {
  _reset_env
  # Intentionally no FW_CURL_META_FIXTURE → empty body → script errors.
  export FW_DIG_MAP="$FIXTURES/init-firewall-dns-map.tsv"

  run_fw
  assert_exit_code 1 "$_RC" || return 1
  assert_stdout_contains "Failed to fetch GitHub IP ranges" "$_STDOUT" || return 1
}

test_invalid_cidr_from_github_exits_1() {
  _reset_env
  export FW_CURL_META_FIXTURE="$FIXTURES/github-meta-invalid-cidr.json"
  export FW_DIG_MAP="$FIXTURES/init-firewall-dns-map.tsv"

  run_fw
  assert_exit_code 1 "$_RC" || return 1
  assert_stdout_contains "Invalid CIDR range from GitHub meta" "$_STDOUT" || return 1
}

test_dns_resolution_failure_exits_1() {
  _reset_env
  export FW_CURL_META_FIXTURE="$FIXTURES/github-meta.json"
  # Empty DNS map → first domain (registry.npmjs.org) returns no IPs.
  export FW_DIG_MAP="/dev/null"

  run_fw
  assert_exit_code 1 "$_RC" || return 1
  assert_stdout_contains "Failed to resolve registry.npmjs.org" "$_STDOUT" || return 1
}

test_invalid_ip_from_dns_exits_1() {
  _reset_env
  export FW_CURL_META_FIXTURE="$FIXTURES/github-meta.json"
  export FW_DIG_MAP="$FIXTURES/init-firewall-dns-map.tsv"
  export FW_DIG_FORCE_BAD_IP="bogus.ip.addr.xx"

  run_fw
  assert_exit_code 1 "$_RC" || return 1
  assert_stdout_contains "Invalid IP from DNS" "$_STDOUT" || return 1
}

test_example_com_reachable_is_a_failure() {
  # Verification step: if example.com is somehow reachable, the firewall is
  # not actually blocking outbound traffic and we must fail.
  _reset_env
  export FW_CURL_META_FIXTURE="$FIXTURES/github-meta.json"
  export FW_DIG_MAP="$FIXTURES/init-firewall-dns-map.tsv"
  export FW_CURL_EXAMPLE_EXIT=0  # Pretend the block was bypassed.

  run_fw
  assert_exit_code 1 "$_RC" || return 1
  assert_stdout_contains "was able to reach https://example.com" "$_STDOUT" || return 1
}

test_github_zen_unreachable_is_a_failure() {
  _reset_env
  export FW_CURL_META_FIXTURE="$FIXTURES/github-meta.json"
  export FW_DIG_MAP="$FIXTURES/init-firewall-dns-map.tsv"
  export FW_CURL_GH_ZEN_EXIT=7  # Pretend GitHub is also unreachable.

  run_fw
  assert_exit_code 1 "$_RC" || return 1
  assert_stdout_contains "unable to reach https://api.github.com" "$_STDOUT" || return 1
}

# ── Run ────────────────────────────────────────────────────────────

run_test test_happy_path_sets_default_drop_and_populates_ipset
run_test test_github_api_fetch_failure_exits_1
run_test test_invalid_cidr_from_github_exits_1
run_test test_dns_resolution_failure_exits_1
run_test test_invalid_ip_from_dns_exits_1
run_test test_example_com_reachable_is_a_failure
run_test test_github_zen_unreachable_is_a_failure

print_summary
