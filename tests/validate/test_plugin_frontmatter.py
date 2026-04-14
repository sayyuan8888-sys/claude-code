"""Schema validation for YAML frontmatter inside plugin markdown files.

Existing tests in ``test_manifest_consistency.py`` check that plugin command,
agent, and skill files *have* frontmatter (a ``---`` block at the top). They
do NOT parse the YAML or verify required fields. A typo like
``descripton:`` (missing an ``i``) or a dropped ``name:`` currently slips
through — the plugin installs, but the agent/command/skill silently fails to
register at runtime.

This module fills that gap:

- Every ``plugins/*/agents/*.md`` must have a parseable YAML frontmatter
  block with ``name`` and ``description``, and ``name`` must match the
  filename stem.
- Every ``plugins/*/skills/*/SKILL.md`` must have a parseable YAML
  frontmatter block with ``name`` and ``description``.
- Every ``plugins/*/commands/*.md`` must have a parseable YAML frontmatter
  block with a ``description``. If ``allowed-tools`` is present, every
  entry must match the ``ToolName`` or ``ToolName(<prefix>)`` shape.

Skill ``name`` fields are also checked for uniqueness across the repo —
duplicates cause the Claude Code runtime to pick one arbitrarily.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
# ToolName or ToolName(<anything>). Accepts MCP-style names like
# ``mcp__github_inline_comment__create_inline_comment``.
ALLOWED_TOOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*(\(([^)]+)\))?$")


def _parse_frontmatter(path: Path) -> dict:
    """Extract ``key: value`` pairs from a markdown frontmatter block.

    Uses a permissive line-based scan (not strict YAML) because description
    fields in this repo routinely contain unquoted colons and parentheses.
    This matches the Claude Code runtime's own frontmatter handling.

    Rules:
      - A line starting with ``[A-Za-z][A-Za-z0-9_-]*:`` begins a new key.
      - Following indented lines are appended to the previous key's value
        (continuation), preserving multi-line descriptions.
      - List-style values (``- ...``) are collected into a list.
      - Returns an empty dict if no frontmatter block is present or if the
        block closing ``---`` is missing.
    """
    text = path.read_text()
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    block = match.group(1)
    key_re = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*)$")

    result: dict = {}
    current_key: str | None = None
    current_list: list | None = None

    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Continuation of a list value.
        if current_key is not None and stripped.startswith("- ") and (
            line.startswith(" ") or line.startswith("\t")
        ):
            if current_list is None:
                current_list = []
                result[current_key] = current_list
            current_list.append(stripped[2:].strip())
            continue
        # Indented continuation of a scalar value.
        if current_key is not None and (line.startswith(" ") or line.startswith("\t")):
            if isinstance(result.get(current_key), str):
                result[current_key] = result[current_key] + " " + stripped
            continue
        # New key.
        m = key_re.match(line)
        if not m:
            continue
        current_key = m.group(1)
        current_list = None
        value = m.group(2).strip()
        # Strip surrounding quotes on scalar values.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        # Inline list: ["A", "B"].
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                result[current_key] = []
            else:
                items = []
                depth = 0
                buf = []
                for ch in inner:
                    if ch in "([":
                        depth += 1
                        buf.append(ch)
                    elif ch in ")]":
                        depth -= 1
                        buf.append(ch)
                    elif ch == "," and depth == 0:
                        items.append("".join(buf).strip())
                        buf = []
                    else:
                        buf.append(ch)
                if buf:
                    items.append("".join(buf).strip())
                cleaned = []
                for item in items:
                    if len(item) >= 2 and item[0] == item[-1] and item[0] in ('"', "'"):
                        item = item[1:-1]
                    cleaned.append(item)
                result[current_key] = cleaned
            current_key = None
            continue
        result[current_key] = value
    return result


def _split_allowed_tools(raw) -> list[str]:
    """Normalize ``allowed-tools`` into a list of entry strings.

    The field is written two ways in this repo:
      - YAML list:   ``allowed-tools: ["Bash", "Read"]``
      - Bare string: ``allowed-tools: Bash(git add:*), Bash(git status:*)``
    """
    if isinstance(raw, list):
        return [str(e).strip() for e in raw if str(e).strip()]
    if not isinstance(raw, str):
        return []
    entries = []
    depth = 0
    buf = []
    for ch in raw:
        if ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            entries.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        entries.append("".join(buf).strip())
    return [e for e in entries if e]


# ── Discovery ────────────────────────────────────────────────────


AGENT_FILES = sorted(PLUGINS_DIR.glob("*/agents/*.md"))
SKILL_FILES = sorted(PLUGINS_DIR.glob("*/skills/*/SKILL.md"))
PLUGIN_COMMAND_FILES = sorted(PLUGINS_DIR.glob("*/commands/*.md"))


class TestDiscovery:
    """Guard against the parametrized tests below silently collecting zero
    cases if the glob patterns drift."""

    def test_agents_glob_is_nonempty(self):
        assert AGENT_FILES, "No plugin agent files found"

    def test_skills_glob_is_nonempty(self):
        assert SKILL_FILES, "No plugin SKILL.md files found"

    def test_commands_glob_is_nonempty(self):
        assert PLUGIN_COMMAND_FILES, "No plugin command files found"


# ── Agents ───────────────────────────────────────────────────────


@pytest.mark.parametrize("path", AGENT_FILES)
class TestAgentFrontmatter:
    def test_frontmatter_parses_as_yaml(self, path):
        fm = _parse_frontmatter(path)
        assert fm, f"{path.relative_to(REPO_ROOT)}: empty or missing frontmatter"

    def test_has_required_fields(self, path):
        fm = _parse_frontmatter(path)
        for field in ("name", "description"):
            assert field in fm, (
                f"{path.relative_to(REPO_ROOT)}: missing required field "
                f"{field!r}"
            )
            assert isinstance(fm[field], str) and fm[field].strip(), (
                f"{path.relative_to(REPO_ROOT)}: field {field!r} must be a "
                f"non-empty string"
            )

    def test_name_matches_filename(self, path):
        fm = _parse_frontmatter(path)
        assert fm.get("name") == path.stem, (
            f"{path.relative_to(REPO_ROOT)}: name={fm.get('name')!r} does "
            f"not match filename stem {path.stem!r}"
        )


# ── Skills ───────────────────────────────────────────────────────


@pytest.mark.parametrize("path", SKILL_FILES)
class TestSkillFrontmatter:
    def test_frontmatter_parses_as_yaml(self, path):
        fm = _parse_frontmatter(path)
        assert fm, f"{path.relative_to(REPO_ROOT)}: empty or missing frontmatter"

    def test_has_required_fields(self, path):
        fm = _parse_frontmatter(path)
        for field in ("name", "description"):
            assert field in fm, (
                f"{path.relative_to(REPO_ROOT)}: missing required field "
                f"{field!r}"
            )
            assert isinstance(fm[field], str) and fm[field].strip(), (
                f"{path.relative_to(REPO_ROOT)}: field {field!r} must be a "
                f"non-empty string"
            )


class TestSkillNameUniqueness:
    def test_skill_names_are_unique(self):
        """Duplicate skill names cause Claude Code to pick one arbitrarily."""
        seen: dict[str, Path] = {}
        collisions = []
        for path in SKILL_FILES:
            fm = _parse_frontmatter(path)
            name = fm.get("name")
            if not isinstance(name, str):
                continue
            if name in seen:
                collisions.append(
                    f"{name!r}: {seen[name].relative_to(REPO_ROOT)} vs "
                    f"{path.relative_to(REPO_ROOT)}"
                )
            else:
                seen[name] = path
        assert not collisions, "Duplicate skill names:\n  " + "\n  ".join(collisions)


# ── Plugin commands ──────────────────────────────────────────────


@pytest.mark.parametrize("path", PLUGIN_COMMAND_FILES)
class TestPluginCommandFrontmatter:
    def test_frontmatter_parses_as_yaml(self, path):
        fm = _parse_frontmatter(path)
        assert fm, f"{path.relative_to(REPO_ROOT)}: empty or missing frontmatter"

    def test_has_description(self, path):
        fm = _parse_frontmatter(path)
        assert "description" in fm, (
            f"{path.relative_to(REPO_ROOT)}: missing required field "
            f"'description'"
        )
        assert isinstance(fm["description"], str) and fm["description"].strip(), (
            f"{path.relative_to(REPO_ROOT)}: 'description' must be a "
            f"non-empty string"
        )

    def test_allowed_tools_entries_are_well_formed(self, path):
        """Skip if ``allowed-tools`` is absent; otherwise every entry must
        match the ``ToolName`` or ``ToolName(...)`` shape. A malformed entry
        is silently treated as "no tools allowed" by the runtime."""
        fm = _parse_frontmatter(path)
        if "allowed-tools" not in fm:
            pytest.skip("no allowed-tools frontmatter")
        entries = _split_allowed_tools(fm["allowed-tools"])
        assert entries, (
            f"{path.relative_to(REPO_ROOT)}: 'allowed-tools' is present but "
            f"parsed to no entries"
        )
        for entry in entries:
            assert ALLOWED_TOOL_RE.match(entry), (
                f"{path.relative_to(REPO_ROOT)}: malformed allowed-tools "
                f"entry: {entry!r}"
            )


# ── Helper unit tests (guard the test infra itself) ──────────────


class TestSplitAllowedTools:
    def test_list_form(self):
        assert _split_allowed_tools(["Bash", "Read"]) == ["Bash", "Read"]

    def test_string_form_with_parens(self):
        raw = "Bash(git add:*), Bash(git status:*)"
        assert _split_allowed_tools(raw) == [
            "Bash(git add:*)",
            "Bash(git status:*)",
        ]

    def test_non_string_non_list_returns_empty(self):
        assert _split_allowed_tools(None) == []
        assert _split_allowed_tools(42) == []
