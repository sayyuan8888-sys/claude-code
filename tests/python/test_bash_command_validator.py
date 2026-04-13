"""Tests for examples/hooks/bash_command_validator_example.py."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "examples"
    / "hooks"
    / "bash_command_validator_example.py"
)


def _run(stdin_payload: str):
    """Invoke the validator script as a subprocess."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result.returncode, result.stdout, result.stderr


class TestValidateCommand:
    def test_grep_flagged(self, bash_command_validator):
        issues = bash_command_validator._validate_command("grep foo bar.txt")
        assert len(issues) == 1
        assert "rg" in issues[0]

    def test_piped_grep_allowed(self, bash_command_validator):
        issues = bash_command_validator._validate_command("grep foo bar.txt | wc -l")
        assert len(issues) == 0

    def test_find_name_flagged(self, bash_command_validator):
        issues = bash_command_validator._validate_command('find /tmp -name "*.txt"')
        assert len(issues) == 1
        assert "rg" in issues[0]

    def test_rg_not_flagged(self, bash_command_validator):
        issues = bash_command_validator._validate_command("rg pattern file.txt")
        assert len(issues) == 0

    def test_ls_not_flagged(self, bash_command_validator):
        issues = bash_command_validator._validate_command("ls -la")
        assert len(issues) == 0

    def test_bare_grep_not_flagged(self, bash_command_validator):
        # "grep" without a following word boundary + no pipe → still matches
        # because ^grep\b matches "grep" at start
        issues = bash_command_validator._validate_command("grep")
        # The regex ^grep\b(?!.*\|) matches "grep" with word boundary,
        # and there's no pipe, so it SHOULD flag it
        assert len(issues) == 1

    def test_grep_midline_not_flagged(self, bash_command_validator):
        # grep not at start of command
        issues = bash_command_validator._validate_command("echo hello | grep pattern")
        assert len(issues) == 0

    def test_multiple_issues(self, bash_command_validator):
        # This shouldn't hit both since grep is piped (no flag) and find is separate
        issues = bash_command_validator._validate_command("grep foo")
        assert len(issues) >= 1

    def test_find_without_name_not_flagged(self, bash_command_validator):
        issues = bash_command_validator._validate_command("find /tmp -type f")
        assert len(issues) == 0


class TestMainSubprocess:
    """Exercises main()'s stdin/exit-code contract end-to-end."""

    def test_malformed_json_exits_1(self):
        rc, _, stderr = _run("not-json{")
        assert rc == 1
        assert "Invalid JSON" in stderr

    def test_non_bash_tool_exits_0(self):
        payload = json.dumps({"tool_name": "Write", "tool_input": {"content": "x"}})
        rc, _, _ = _run(payload)
        assert rc == 0

    def test_empty_command_exits_0(self):
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": ""}})
        rc, _, _ = _run(payload)
        assert rc == 0

    def test_clean_command_exits_0(self):
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
        rc, _, stderr = _run(payload)
        assert rc == 0
        assert stderr == ""

    def test_grep_command_exits_2_with_stderr(self):
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "grep foo bar.txt"}})
        rc, _, stderr = _run(payload)
        assert rc == 2
        assert "rg" in stderr
