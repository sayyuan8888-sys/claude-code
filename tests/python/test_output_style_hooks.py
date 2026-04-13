"""Tests for SessionStart hooks shipped with the output-style plugins.

Both hooks are `cat <<EOF`-style bash scripts that print a single JSON blob
with the SessionStart additional-context payload. The tests invoke the real
script via subprocess and check:
  - exit code is 0
  - stdout is valid JSON
  - the JSON matches the SessionStart hook output schema
"""

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

HOOKS = [
    REPO_ROOT
    / "plugins"
    / "learning-output-style"
    / "hooks-handlers"
    / "session-start.sh",
    REPO_ROOT
    / "plugins"
    / "explanatory-output-style"
    / "hooks-handlers"
    / "session-start.sh",
]


@pytest.mark.parametrize("hook_path", HOOKS, ids=lambda p: p.parent.parent.name)
class TestSessionStartHook:
    def test_hook_file_exists(self, hook_path: Path):
        assert hook_path.is_file()

    def test_hook_exits_zero(self, hook_path: Path):
        result = subprocess.run(
            ["bash", str(hook_path)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_hook_stdout_is_valid_json(self, hook_path: Path):
        result = subprocess.run(
            ["bash", str(hook_path)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_hook_payload_matches_session_start_schema(self, hook_path: Path):
        result = subprocess.run(
            ["bash", str(hook_path)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = json.loads(result.stdout)
        assert "hookSpecificOutput" in data
        hso = data["hookSpecificOutput"]
        assert hso.get("hookEventName") == "SessionStart"
        assert isinstance(hso.get("additionalContext"), str)
        assert hso["additionalContext"].strip(), "additionalContext is empty"
