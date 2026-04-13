"""Integration tests for the hookify hook handlers.

These test the glue scripts under plugins/hookify/hooks/ end-to-end: spawning
them as subprocesses, piping JSON to stdin, and asserting exit code + stdout.

Contract for every handler:
  - ALWAYS exit 0 (handlers must never block the host tool call on error)
  - ALWAYS emit valid JSON on stdout (even an empty object)

We also verify that matching rules propagate through to the output when a
fixture rule file is present in .claude/hookify.*.local.md.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
HANDLERS = {
    "pretooluse": HOOKS_DIR / "pretooluse.py",
    "posttooluse": HOOKS_DIR / "posttooluse.py",
    "userpromptsubmit": HOOKS_DIR / "userpromptsubmit.py",
    "stop": HOOKS_DIR / "stop.py",
}


def _run_handler(handler_path: Path, payload: dict, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke a hookify handler as a subprocess with `payload` on stdin."""
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    return subprocess.run(
        [sys.executable, str(handler_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=env,
        timeout=10,
    )


# ── Exit-code contract ────────────────────────────────────────────


@pytest.mark.parametrize("name,path", list(HANDLERS.items()))
def test_handler_exits_zero_on_empty_rules(name, path, tmp_path):
    """With no rule files, every handler must exit 0 and emit JSON."""
    (tmp_path / ".claude").mkdir()
    result = _run_handler(path, {"tool_name": "Bash", "tool_input": {}}, tmp_path)
    assert result.returncode == 0, f"{name} returned {result.returncode}: {result.stderr}"
    # stdout must be valid JSON (empty dict is fine)
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, dict)


@pytest.mark.parametrize("name,path", list(HANDLERS.items()))
def test_handler_exits_zero_on_malformed_stdin(name, path, tmp_path):
    """Even bogus stdin must not block — handlers catch all exceptions."""
    (tmp_path / ".claude").mkdir()
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    result = subprocess.run(
        [sys.executable, str(path)],
        input="this is not json",
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
        timeout=10,
    )
    assert result.returncode == 0, f"{name} returned {result.returncode}: {result.stderr}"
    # Should emit a systemMessage surfacing the error
    parsed = json.loads(result.stdout)
    assert "systemMessage" in parsed


@pytest.mark.parametrize("name,path", list(HANDLERS.items()))
def test_handler_exits_zero_on_empty_stdin(name, path, tmp_path):
    """Empty stdin is also tolerated."""
    (tmp_path / ".claude").mkdir()
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    result = subprocess.run(
        [sys.executable, str(path)],
        input="",
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
        timeout=10,
    )
    assert result.returncode == 0


# ── Rule evaluation end-to-end ────────────────────────────────────


def _write_bash_rule(dot_claude: Path, *, action: str = "warn") -> None:
    """Write a hookify rule that matches `rm -rf` Bash commands."""
    dot_claude.mkdir(exist_ok=True)
    rule = (
        "---\n"
        "name: block-rm-rf\n"
        "enabled: true\n"
        "event: bash\n"
        f"action: {action}\n"
        "conditions:\n"
        "- field: command, operator: regex_match, pattern: rm\\s+-rf\n"
        "---\n"
        "Detected a dangerous rm -rf command.\n"
    )
    (dot_claude / "hookify.rm.local.md").write_text(rule)


def test_pretooluse_surfaces_matching_warning(tmp_path):
    _write_bash_rule(tmp_path / ".claude", action="warn")
    payload = {"tool_name": "Bash", "tool_input": {"command": "rm -rf /tmp/x"}}
    result = _run_handler(HANDLERS["pretooluse"], payload, tmp_path)
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    # The rule engine surfaces matches via systemMessage or hookSpecificOutput;
    # we only assert *something* was produced, not the exact shape, so this test
    # stays robust to engine output refactors.
    assert parsed, f"Expected a non-empty response, got: {parsed}"


def test_pretooluse_no_match_returns_empty(tmp_path):
    _write_bash_rule(tmp_path / ".claude", action="warn")
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
    result = _run_handler(HANDLERS["pretooluse"], payload, tmp_path)
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    # No rule should match "ls" — expect empty dict
    assert parsed == {}


def test_pretooluse_event_filter_skips_file_events(tmp_path):
    """A `bash` rule must NOT fire on an Edit (file) tool call."""
    _write_bash_rule(tmp_path / ".claude", action="warn")
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "/tmp/x", "new_string": "rm -rf /"},
    }
    result = _run_handler(HANDLERS["pretooluse"], payload, tmp_path)
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert parsed == {}
