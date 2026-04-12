"""Tests for hookify RuleEngine: operators, tool matching, field extraction, blocking."""

import os
import tempfile

import pytest

from hookify.core.config_loader import Condition, Rule
from hookify.core.rule_engine import RuleEngine


@pytest.fixture()
def engine():
    return RuleEngine()


# ── Operators ─────────────────────────────────────────────────────


class TestOperators:
    def test_regex_match_positive(self, engine):
        cond = Condition(field="command", operator="regex_match", pattern=r"rm\s+-rf")
        assert engine._check_condition(cond, "Bash", {"command": "rm -rf /tmp"}, {})

    def test_regex_match_negative(self, engine):
        cond = Condition(field="command", operator="regex_match", pattern=r"rm\s+-rf")
        assert not engine._check_condition(cond, "Bash", {"command": "ls -la"}, {})

    def test_contains(self, engine):
        cond = Condition(field="command", operator="contains", pattern="sudo")
        assert engine._check_condition(cond, "Bash", {"command": "sudo rm file"}, {})

    def test_contains_negative(self, engine):
        cond = Condition(field="command", operator="contains", pattern="sudo")
        assert not engine._check_condition(cond, "Bash", {"command": "ls"}, {})

    def test_equals(self, engine):
        cond = Condition(field="command", operator="equals", pattern="ls")
        assert engine._check_condition(cond, "Bash", {"command": "ls"}, {})

    def test_equals_negative(self, engine):
        cond = Condition(field="command", operator="equals", pattern="ls")
        assert not engine._check_condition(cond, "Bash", {"command": "ls -la"}, {})

    def test_not_contains(self, engine):
        cond = Condition(field="command", operator="not_contains", pattern="sudo")
        assert engine._check_condition(cond, "Bash", {"command": "ls"}, {})

    def test_not_contains_negative(self, engine):
        cond = Condition(field="command", operator="not_contains", pattern="sudo")
        assert not engine._check_condition(cond, "Bash", {"command": "sudo ls"}, {})

    def test_starts_with(self, engine):
        cond = Condition(field="command", operator="starts_with", pattern="rm")
        assert engine._check_condition(cond, "Bash", {"command": "rm file"}, {})

    def test_ends_with(self, engine):
        cond = Condition(field="command", operator="ends_with", pattern=".py")
        assert engine._check_condition(cond, "Bash", {"command": "python test.py"}, {})

    def test_unknown_operator_returns_false(self, engine):
        cond = Condition(field="command", operator="magic_match", pattern="x")
        assert not engine._check_condition(cond, "Bash", {"command": "x"}, {})


# ── Tool matching ─────────────────────────────────────────────────


class TestToolMatching:
    def test_wildcard_matches_any(self, engine):
        assert engine._matches_tool("*", "Bash")
        assert engine._matches_tool("*", "Write")

    def test_exact_match(self, engine):
        assert engine._matches_tool("Bash", "Bash")
        assert not engine._matches_tool("Bash", "Write")

    def test_alternation(self, engine):
        assert engine._matches_tool("Edit|Write", "Edit")
        assert engine._matches_tool("Edit|Write", "Write")
        assert not engine._matches_tool("Edit|Write", "Bash")


# ── Field extraction ──────────────────────────────────────────────


class TestFieldExtraction:
    def test_bash_command(self, engine):
        result = engine._extract_field("command", "Bash", {"command": "ls"}, {})
        assert result == "ls"

    def test_write_content(self, engine):
        result = engine._extract_field("content", "Write", {"content": "hello"}, {})
        assert result == "hello"

    def test_write_file_path(self, engine):
        result = engine._extract_field("file_path", "Write", {"file_path": "/tmp/f"}, {})
        assert result == "/tmp/f"

    def test_edit_new_string(self, engine):
        result = engine._extract_field("new_text", "Edit", {"new_string": "new"}, {})
        assert result == "new"

    def test_edit_old_string(self, engine):
        result = engine._extract_field("old_text", "Edit", {"old_string": "old"}, {})
        assert result == "old"

    def test_multiedit_concatenation(self, engine):
        tool_input = {
            "file_path": "/tmp/f",
            "edits": [{"new_string": "aaa"}, {"new_string": "bbb"}],
        }
        result = engine._extract_field("content", "MultiEdit", tool_input, {})
        assert result == "aaa bbb"

    def test_stop_reason(self, engine):
        input_data = {"reason": "Task done", "hook_event_name": "Stop"}
        result = engine._extract_field("reason", "", {}, input_data)
        assert result == "Task done"

    def test_user_prompt(self, engine):
        input_data = {"user_prompt": "Hello", "hook_event_name": "UserPromptSubmit"}
        result = engine._extract_field("user_prompt", "", {}, input_data)
        assert result == "Hello"

    def test_transcript_file(self, engine, tmp_path):
        f = tmp_path / "transcript.txt"
        f.write_text("conversation content here")
        input_data = {"transcript_path": str(f)}
        result = engine._extract_field("transcript", "", {}, input_data)
        assert result == "conversation content here"

    def test_transcript_missing_file(self, engine):
        input_data = {"transcript_path": "/nonexistent/file.txt"}
        result = engine._extract_field("transcript", "", {}, input_data)
        assert result == ""

    def test_unknown_field_returns_none(self, engine):
        result = engine._extract_field("nonexistent", "Bash", {"command": "ls"}, {})
        assert result is None


# ── Blocking precedence ──────────────────────────────────────────


class TestBlockingPrecedence:
    def test_block_rule_wins_over_warn(self, engine, sample_rule, blocking_rule):
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "hook_event_name": "PreToolUse",
        }
        result = engine.evaluate_rules([sample_rule, blocking_rule], input_data)
        assert "permissionDecision" in result.get("hookSpecificOutput", {})
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_multiple_blocks_combine_messages(self, engine):
        r1 = Rule(
            name="block1", enabled=True, event="bash",
            conditions=[Condition(field="command", operator="contains", pattern="rm")],
            action="block", message="Block 1",
        )
        r2 = Rule(
            name="block2", enabled=True, event="bash",
            conditions=[Condition(field="command", operator="contains", pattern="rm")],
            action="block", message="Block 2",
        )
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf"},
            "hook_event_name": "PreToolUse",
        }
        result = engine.evaluate_rules([r1, r2], input_data)
        assert "Block 1" in result["systemMessage"]
        assert "Block 2" in result["systemMessage"]

    def test_warn_only_returns_system_message(self, engine, sample_rule):
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "hook_event_name": "PreToolUse",
        }
        result = engine.evaluate_rules([sample_rule], input_data)
        assert "systemMessage" in result
        assert "hookSpecificOutput" not in result


# ── Event-specific output shape ───────────────────────────────────


class TestEventOutputShape:
    def test_pretooluse_block_has_permission_deny(self, engine, blocking_rule):
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "hook_event_name": "PreToolUse",
        }
        result = engine.evaluate_rules([blocking_rule], input_data)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert result["hookSpecificOutput"]["hookEventName"] == "PreToolUse"

    def test_stop_block_has_decision_block(self, engine):
        rule = Rule(
            name="stop-block", enabled=True, event="stop",
            conditions=[Condition(field="reason", operator="contains", pattern="done")],
            action="block", message="Not done yet!",
        )
        input_data = {
            "reason": "Task done",
            "hook_event_name": "Stop",
        }
        result = engine.evaluate_rules([rule], input_data)
        assert result.get("decision") == "block"

    def test_other_event_block_has_bare_system_message(self, engine):
        rule = Rule(
            name="prompt-block", enabled=True, event="all",
            conditions=[Condition(field="user_prompt", operator="contains", pattern="hack")],
            action="block", message="Blocked!",
        )
        input_data = {
            "user_prompt": "hack the planet",
            "hook_event_name": "UserPromptSubmit",
        }
        result = engine.evaluate_rules([rule], input_data)
        assert "systemMessage" in result
        assert "hookSpecificOutput" not in result
        assert "decision" not in result


# ── Edge cases ────────────────────────────────────────────────────


class TestEdgeCases:
    def test_no_matches_returns_empty(self, engine, sample_rule):
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "hook_event_name": "PreToolUse",
        }
        result = engine.evaluate_rules([sample_rule], input_data)
        assert result == {}

    def test_invalid_regex_returns_false(self, engine):
        cond = Condition(field="command", operator="regex_match", pattern="[invalid")
        assert not engine._check_condition(cond, "Bash", {"command": "[invalid"}, {})

    def test_rule_with_no_conditions_does_not_match(self, engine):
        rule = Rule(
            name="empty", enabled=True, event="bash",
            conditions=[], action="warn", message="Should not match",
        )
        input_data = {"tool_name": "Bash", "tool_input": {"command": "anything"}}
        result = engine.evaluate_rules([rule], input_data)
        assert result == {}

    def test_tool_matcher_filters(self, engine):
        rule = Rule(
            name="write-only", enabled=True, event="file",
            tool_matcher="Write",
            conditions=[Condition(field="content", operator="contains", pattern="bad")],
            action="warn", message="Bad content!",
        )
        # Bash should not match the tool_matcher
        input_data = {"tool_name": "Bash", "tool_input": {"content": "bad"}}
        result = engine.evaluate_rules([rule], input_data)
        assert result == {}

        # Write should match
        input_data2 = {
            "tool_name": "Write",
            "tool_input": {"content": "bad stuff"},
            "hook_event_name": "PreToolUse",
        }
        result2 = engine.evaluate_rules([rule], input_data2)
        assert "systemMessage" in result2
