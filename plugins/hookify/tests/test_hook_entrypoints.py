"""Integration tests for hookify hook entrypoint scripts.

Each hook script is invoked as a subprocess with real stdin JSON.
Contract under test:
  * Always exits 0 (never blocks on hook errors).
  * Always prints valid JSON to stdout.
  * Processes rule files from CWD/.claude/hookify.*.local.md.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = PLUGIN_ROOT / "hooks"


def _run_hook(script_name: str, stdin_payload: str, cwd: Path, extra_env=None):
    """Invoke a hook script as a subprocess. Returns (returncode, stdout, stderr)."""
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [sys.executable, str(HOOKS_DIR / script_name)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=env,
        timeout=10,
    )
    return result.returncode, result.stdout, result.stderr


class TestPreToolUseHook:
    def test_exits_zero_on_valid_input_no_rules(self, tmp_path):
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        rc, stdout, _ = _run_hook("pretooluse.py", payload, tmp_path)
        assert rc == 0
        assert json.loads(stdout) == {}

    def test_exits_zero_on_malformed_json(self, tmp_path):
        rc, stdout, _ = _run_hook("pretooluse.py", "not json{", tmp_path)
        assert rc == 0
        data = json.loads(stdout)
        assert "systemMessage" in data

    def test_exits_zero_on_empty_stdin(self, tmp_path):
        rc, stdout, _ = _run_hook("pretooluse.py", "", tmp_path)
        assert rc == 0
        # Empty stdin triggers JSON parse error → systemMessage output
        json.loads(stdout)  # must be valid JSON

    def test_loads_rule_and_matches_bash(self, tmp_path):
        # Create a .claude/hookify rule file in the fake repo
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        rule_file = claude_dir / "hookify.test-rule.local.md"
        rule_file.write_text(
            "---\n"
            "name: block-rm-rf\n"
            "enabled: true\n"
            "event: bash\n"
            "action: block\n"
            "pattern: 'rm -rf'\n"
            "---\n"
            "Dangerous rm -rf detected\n"
        )
        payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
        })
        rc, stdout, _ = _run_hook("pretooluse.py", payload, tmp_path)
        assert rc == 0
        data = json.loads(stdout)
        # PreToolUse block maps to hookSpecificOutput.permissionDecision=deny
        assert "hookSpecificOutput" in data
        assert data["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_non_matching_command_emits_empty(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "hookify.test.local.md").write_text(
            "---\nname: r\nenabled: true\nevent: bash\naction: block\npattern: 'rm -rf'\n---\nmsg\n"
        )
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        rc, stdout, _ = _run_hook("pretooluse.py", payload, tmp_path)
        assert rc == 0
        assert json.loads(stdout) == {}


class TestOtherHookEntrypoints:
    """Smoke tests that other hook scripts also satisfy the exit-0-valid-JSON contract."""

    @pytest.mark.parametrize("script", ["posttooluse.py", "stop.py", "userpromptsubmit.py"])
    def test_script_exits_zero_on_empty_input(self, tmp_path, script):
        rc, stdout, _ = _run_hook(script, "{}", tmp_path)
        assert rc == 0
        json.loads(stdout)  # must parse

    @pytest.mark.parametrize("script", ["posttooluse.py", "stop.py", "userpromptsubmit.py"])
    def test_script_exits_zero_on_malformed_input(self, tmp_path, script):
        rc, stdout, _ = _run_hook(script, "garbage", tmp_path)
        assert rc == 0
        json.loads(stdout)  # must parse
