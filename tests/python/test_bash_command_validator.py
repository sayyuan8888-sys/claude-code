"""Tests for examples/hooks/bash_command_validator_example.py."""

import pytest


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
