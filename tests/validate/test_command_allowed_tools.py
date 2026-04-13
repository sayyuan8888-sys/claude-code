"""Validate `.claude/commands/*.md` `allowed-tools` frontmatter.

The `allowed-tools` list is a security boundary enforced by the Claude Code
runtime — a regression here either breaks the slash command entirely (tools
get denied) or silently over-permits (tools get approved that shouldn't).

We verify:

  - Every repo-level command has valid `allowed-tools` frontmatter.
  - Every entry matches the expected `ToolName` or `ToolName(<prefix>:*)` shape.
  - Every `./scripts/*.sh` referenced in the body is covered by an entry.
  - Every `./scripts/*.sh` referenced in the body actually exists on disk.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
ALLOWED_TOOL_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9_-]*"        # ToolName
    r"(\(([^)]+)\))?$"                 # optional (pattern)
)
SCRIPT_REF_RE = re.compile(r"\./scripts/[A-Za-z0-9_.\-/]+\.sh")


def _command_files():
    if not COMMANDS_DIR.exists():
        return []
    return sorted(COMMANDS_DIR.glob("*.md"))


def _parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm_block = m.group(1)
    out = {}
    for line in fm_block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


def _split_allowed_tools(raw: str) -> list[str]:
    """Split an `allowed-tools` value like `Bash(./a.sh:*), Bash(./b.sh:*)`.

    Naive comma-splitting would break on commas inside `()`. We track paren
    depth instead.
    """
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


def _allow_prefixes(entries: list[str]) -> list[str]:
    """Extract command prefixes from `Bash(<prefix>:*)` entries."""
    prefixes = []
    for entry in entries:
        m = ALLOWED_TOOL_RE.match(entry)
        if not m or not m.group(2):
            continue
        inner = m.group(2)
        # Strip trailing ":*" (Claude Code's "any suffix" marker).
        if inner.endswith(":*"):
            inner = inner[:-2]
        prefixes.append(inner.strip())
    return prefixes


# ── Per-file tests ────────────────────────────────────────────────


COMMAND_FILES = _command_files()


@pytest.mark.skipif(not COMMAND_FILES, reason="no .claude/commands/ directory")
@pytest.mark.parametrize("path", COMMAND_FILES)
class TestAllowedToolsFrontmatter:
    def test_has_allowed_tools(self, path):
        fm = _parse_frontmatter(path.read_text())
        assert "allowed-tools" in fm, (
            f"{path.name}: missing 'allowed-tools' frontmatter"
        )
        assert fm["allowed-tools"], (
            f"{path.name}: 'allowed-tools' must not be empty"
        )

    def test_each_entry_is_well_formed(self, path):
        fm = _parse_frontmatter(path.read_text())
        entries = _split_allowed_tools(fm.get("allowed-tools", ""))
        assert entries, f"{path.name}: no allowed-tools entries parsed"
        for entry in entries:
            assert ALLOWED_TOOL_RE.match(entry), (
                f"{path.name}: malformed allowed-tools entry: {entry!r}"
            )

    def test_referenced_scripts_are_allowed(self, path):
        text = path.read_text()
        fm = _parse_frontmatter(text)
        body = text.split("---", 2)[2] if text.startswith("---") else text
        entries = _split_allowed_tools(fm.get("allowed-tools", ""))
        prefixes = _allow_prefixes(entries)

        referenced = set(SCRIPT_REF_RE.findall(body))
        for script_ref in referenced:
            covered = any(
                script_ref == pfx or script_ref.startswith(pfx)
                for pfx in prefixes
            )
            assert covered, (
                f"{path.name}: body invokes {script_ref} but no matching "
                f"allowed-tools prefix. Allowed prefixes: {prefixes}"
            )

    def test_referenced_scripts_exist(self, path):
        text = path.read_text()
        body = text.split("---", 2)[2] if text.startswith("---") else text
        for script_ref in set(SCRIPT_REF_RE.findall(body)):
            rel = script_ref.lstrip("./")
            assert (REPO_ROOT / rel).is_file(), (
                f"{path.name}: references missing script {script_ref}"
            )


# ── Parser unit tests (guards the test infra itself) ──────────────


class TestSplitAllowedTools:
    def test_simple_comma_split(self):
        assert _split_allowed_tools("Bash, Read, Grep") == ["Bash", "Read", "Grep"]

    def test_does_not_split_inside_parens(self):
        raw = "Bash(./scripts/gh.sh:*), Bash(./scripts/edit-issue-labels.sh:*)"
        assert _split_allowed_tools(raw) == [
            "Bash(./scripts/gh.sh:*)",
            "Bash(./scripts/edit-issue-labels.sh:*)",
        ]

    def test_handles_colon_inside_parens(self):
        # commit-push-pr.md uses `Bash(git checkout --branch:*)` style.
        raw = "Bash(git push:*), Bash(git commit:*)"
        assert _split_allowed_tools(raw) == [
            "Bash(git push:*)",
            "Bash(git commit:*)",
        ]
