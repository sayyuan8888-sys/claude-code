"""Tests for hookify config_loader: extract_frontmatter, Rule.from_dict, load_rule_file."""

import os
import tempfile

import pytest

from hookify.core.config_loader import Condition, Rule, extract_frontmatter, load_rule_file


# ── extract_frontmatter ──────────────────────────────────────────


class TestExtractFrontmatter:
    def test_simple_key_value(self):
        content = "---\nname: test\nevent: bash\n---\nBody text"
        fm, body = extract_frontmatter(content)
        assert fm["name"] == "test"
        assert fm["event"] == "bash"
        assert body == "Body text"

    def test_boolean_coercion(self):
        content = "---\nenabled: true\nother: false\n---\n"
        fm, _ = extract_frontmatter(content)
        assert fm["enabled"] is True
        assert fm["other"] is False

    def test_quoted_values(self):
        content = '---\nname: "my rule"\npattern: \'rm -rf\'\n---\n'
        fm, _ = extract_frontmatter(content)
        assert fm["name"] == "my rule"
        assert fm["pattern"] == "rm -rf"

    def test_simple_list(self):
        content = "---\ntags:\n- one\n- two\n- three\n---\n"
        fm, _ = extract_frontmatter(content)
        assert fm["tags"] == ["one", "two", "three"]

    def test_inline_dict_list(self):
        content = "---\nconditions:\n- field: command, operator: regex_match, pattern: rm\n---\n"
        fm, _ = extract_frontmatter(content)
        assert len(fm["conditions"]) == 1
        assert fm["conditions"][0]["field"] == "command"
        assert fm["conditions"][0]["operator"] == "regex_match"

    def test_multiline_dict_list(self):
        content = (
            "---\nconditions:\n"
            "- field: command\n"
            "    operator: regex_match\n"
            "    pattern: rm\n"
            "---\n"
        )
        fm, _ = extract_frontmatter(content)
        assert len(fm["conditions"]) == 1
        assert fm["conditions"][0]["field"] == "command"
        assert fm["conditions"][0]["operator"] == "regex_match"

    def test_missing_frontmatter_delimiters(self):
        content = "No frontmatter here"
        fm, body = extract_frontmatter(content)
        assert fm == {}
        assert body == content

    def test_single_delimiter(self):
        content = "---\nname: test"
        fm, body = extract_frontmatter(content)
        assert fm == {}

    def test_empty_content(self):
        content = ""
        fm, body = extract_frontmatter(content)
        assert fm == {}
        assert body == ""

    def test_comments_ignored(self):
        content = "---\nname: test\n# this is a comment\nevent: bash\n---\n"
        fm, _ = extract_frontmatter(content)
        assert fm["name"] == "test"
        assert fm["event"] == "bash"
        assert "#" not in fm

    def test_body_preserved(self):
        content = "---\nname: test\n---\n\n## Warning\n\nDangerous command!"
        fm, body = extract_frontmatter(content)
        assert "## Warning" in body
        assert "Dangerous command!" in body


# ── Rule.from_dict ────────────────────────────────────────────────


class TestRuleFromDict:
    def test_legacy_pattern_converted_to_condition(self):
        fm = {"name": "test", "enabled": True, "event": "bash", "pattern": "rm -rf"}
        rule = Rule.from_dict(fm, "Warning!")
        assert len(rule.conditions) == 1
        assert rule.conditions[0].field == "command"
        assert rule.conditions[0].operator == "regex_match"
        assert rule.conditions[0].pattern == "rm -rf"

    def test_explicit_conditions_list(self):
        fm = {
            "name": "test",
            "enabled": True,
            "event": "file",
            "conditions": [
                {"field": "new_text", "operator": "contains", "pattern": "eval("}
            ],
        }
        rule = Rule.from_dict(fm, "Warning!")
        assert len(rule.conditions) == 1
        assert rule.conditions[0].field == "new_text"
        assert rule.conditions[0].operator == "contains"

    def test_event_to_field_inference_bash(self):
        fm = {"name": "test", "event": "bash", "pattern": "danger"}
        rule = Rule.from_dict(fm, "")
        assert rule.conditions[0].field == "command"

    def test_event_to_field_inference_file(self):
        fm = {"name": "test", "event": "file", "pattern": "danger"}
        rule = Rule.from_dict(fm, "")
        assert rule.conditions[0].field == "new_text"

    def test_event_to_field_inference_other(self):
        fm = {"name": "test", "event": "all", "pattern": "danger"}
        rule = Rule.from_dict(fm, "")
        assert rule.conditions[0].field == "content"

    def test_enabled_defaults_true(self):
        fm = {"name": "test", "event": "bash"}
        rule = Rule.from_dict(fm, "")
        assert rule.enabled is True

    def test_action_defaults_warn(self):
        fm = {"name": "test", "event": "bash"}
        rule = Rule.from_dict(fm, "")
        assert rule.action == "warn"

    def test_message_stripped(self):
        rule = Rule.from_dict({"name": "t", "event": "bash"}, "  hello  \n  ")
        assert rule.message == "hello"


# ── load_rule_file ────────────────────────────────────────────────


class TestLoadRuleFile:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "hookify.test.local.md"
        f.write_text("---\nname: test\nenabled: true\nevent: bash\npattern: rm\n---\nWarning!")
        rule = load_rule_file(str(f))
        assert rule is not None
        assert rule.name == "test"

    def test_missing_frontmatter_returns_none(self, tmp_path):
        f = tmp_path / "bad.md"
        f.write_text("No frontmatter")
        rule = load_rule_file(str(f))
        assert rule is None

    def test_nonexistent_file_returns_none(self):
        rule = load_rule_file("/nonexistent/file.md")
        assert rule is None

    def test_disabled_rule_still_loaded(self, tmp_path):
        f = tmp_path / "disabled.md"
        f.write_text("---\nname: off\nenabled: false\nevent: bash\n---\nOff")
        rule = load_rule_file(str(f))
        assert rule is not None
        assert rule.enabled is False
