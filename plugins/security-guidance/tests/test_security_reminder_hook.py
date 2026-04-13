"""Tests for security_reminder_hook: check_patterns, extract_content_from_input, state."""

import json
import os
import tempfile

import pytest


# We import the module via conftest fixture since it's a standalone script.


class TestCheckPatterns:
    def test_github_actions_workflow_yml(self, security_reminder_hook):
        rule, reminder = security_reminder_hook.check_patterns(
            ".github/workflows/ci.yml", ""
        )
        assert rule == "github_actions_workflow"
        assert reminder is not None

    def test_github_actions_workflow_yaml(self, security_reminder_hook):
        rule, _ = security_reminder_hook.check_patterns(
            ".github/workflows/deploy.yaml", ""
        )
        assert rule == "github_actions_workflow"

    def test_yml_outside_workflows_no_match(self, security_reminder_hook):
        rule, _ = security_reminder_hook.check_patterns("config/app.yml", "")
        assert rule is None

    def test_leading_slash_normalization(self, security_reminder_hook):
        rule, _ = security_reminder_hook.check_patterns(
            "/.github/workflows/ci.yml", ""
        )
        assert rule == "github_actions_workflow"

    def test_eval_in_content(self, security_reminder_hook):
        rule, _ = security_reminder_hook.check_patterns(
            "app.js", "const x = eval(input)"
        )
        assert rule == "eval_injection"

    def test_pickle_in_content(self, security_reminder_hook):
        rule, _ = security_reminder_hook.check_patterns(
            "model.py", "import pickle"
        )
        assert rule == "pickle_deserialization"

    def test_innerhtml_in_content(self, security_reminder_hook):
        rule, _ = security_reminder_hook.check_patterns(
            "ui.js", 'el.innerHTML = userInput'
        )
        assert rule == "innerHTML_xss"

    def test_os_system_in_content(self, security_reminder_hook):
        rule, _ = security_reminder_hook.check_patterns(
            "run.py", "os.system(cmd)"
        )
        assert rule == "os_system_injection"

    def test_dangerously_set_inner_html(self, security_reminder_hook):
        rule, _ = security_reminder_hook.check_patterns(
            "component.tsx", '<div dangerouslySetInnerHTML={{__html: data}} />'
        )
        assert rule == "react_dangerously_set_html"

    def test_clean_content_no_match(self, security_reminder_hook):
        rule, _ = security_reminder_hook.check_patterns(
            "app.js", "const x = 1 + 2"
        )
        assert rule is None

    def test_new_function_injection(self, security_reminder_hook):
        rule, _ = security_reminder_hook.check_patterns(
            "app.js", "const fn = new Function(code)"
        )
        assert rule == "new_function_injection"


class TestExtractContentFromInput:
    def test_write_tool(self, security_reminder_hook):
        result = security_reminder_hook.extract_content_from_input(
            "Write", {"content": "hello world"}
        )
        assert result == "hello world"

    def test_edit_tool(self, security_reminder_hook):
        result = security_reminder_hook.extract_content_from_input(
            "Edit", {"new_string": "replaced text"}
        )
        assert result == "replaced text"

    def test_multiedit_tool(self, security_reminder_hook):
        result = security_reminder_hook.extract_content_from_input(
            "MultiEdit",
            {"edits": [{"new_string": "aaa"}, {"new_string": "bbb"}]},
        )
        assert result == "aaa bbb"

    def test_unknown_tool_returns_empty(self, security_reminder_hook):
        result = security_reminder_hook.extract_content_from_input(
            "Bash", {"command": "ls"}
        )
        assert result == ""


class TestStateRoundTrip:
    def test_save_and_load(self, security_reminder_hook, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(
            security_reminder_hook,
            "get_state_file",
            lambda sid: str(state_file),
        )
        warnings = {"file1-rule1", "file2-rule2"}
        security_reminder_hook.save_state("test-session", warnings)
        loaded = security_reminder_hook.load_state("test-session")
        assert loaded == warnings

    def test_missing_file_returns_empty(self, security_reminder_hook, tmp_path, monkeypatch):
        monkeypatch.setattr(
            security_reminder_hook,
            "get_state_file",
            lambda sid: str(tmp_path / "nonexistent.json"),
        )
        loaded = security_reminder_hook.load_state("test")
        assert loaded == set()

    def test_corrupt_json_returns_empty(self, security_reminder_hook, tmp_path, monkeypatch):
        bad_file = tmp_path / "corrupt.json"
        bad_file.write_text("{invalid json")
        monkeypatch.setattr(
            security_reminder_hook,
            "get_state_file",
            lambda sid: str(bad_file),
        )
        loaded = security_reminder_hook.load_state("test")
        assert loaded == set()


class TestCleanupOldStateFiles:
    def test_removes_old_state_files(self, security_reminder_hook, tmp_path, monkeypatch):
        import os
        import time

        state_dir = tmp_path / ".claude"
        state_dir.mkdir()
        monkeypatch.setenv("HOME", str(tmp_path))

        old_file = state_dir / "security_warnings_state_old.json"
        fresh_file = state_dir / "security_warnings_state_fresh.json"
        unrelated_file = state_dir / "other_file.json"
        old_file.write_text("{}")
        fresh_file.write_text("{}")
        unrelated_file.write_text("{}")

        # Backdate old_file to 40 days ago
        forty_days_ago = time.time() - (40 * 24 * 60 * 60)
        os.utime(old_file, (forty_days_ago, forty_days_ago))

        security_reminder_hook.cleanup_old_state_files()

        assert not old_file.exists(), "old state file should be removed"
        assert fresh_file.exists(), "fresh state file should be kept"
        assert unrelated_file.exists(), "non-matching files should not be touched"

    def test_missing_state_dir_is_noop(self, security_reminder_hook, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        # No ~/.claude dir created. Should silently no-op, not raise.
        security_reminder_hook.cleanup_old_state_files()
