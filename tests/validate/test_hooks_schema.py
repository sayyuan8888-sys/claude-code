"""Schema validation for plugins/*/hooks/hooks.json.

Goes beyond TestHooksJsonValid in test_manifest_consistency.py (which only checks
the files parse). Here we verify:

- Top-level shape: {"hooks": {<EventName>: [...]}} or a bare {<EventName>: [...]}
- Every event name is a known Claude Code hook event
- Every entry in an event list has a "hooks" array of handler specs
- Every handler spec is {"type": "command", "command": "<...>"}
- Any `${CLAUDE_PLUGIN_ROOT}/...` path inside a command points to a file that exists
"""

import glob
import json
import re
import stat
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"

# Known Claude Code hook event names.
KNOWN_EVENTS = {
    "PreToolUse",
    "PostToolUse",
    "UserPromptSubmit",
    "Stop",
    "SubagentStop",
    "SessionStart",
    "SessionEnd",
    "Notification",
    "PreCompact",
}


def _hooks_files():
    return sorted(glob.glob(str(PLUGINS_DIR / "*" / "hooks" / "hooks.json")))


def _event_map(doc):
    """Return the event→entries mapping regardless of top-level shape."""
    if isinstance(doc, dict) and "hooks" in doc and isinstance(doc["hooks"], dict):
        return doc["hooks"]
    if isinstance(doc, dict):
        # Some plugins may put events at the top level.
        return {k: v for k, v in doc.items() if k in KNOWN_EVENTS}
    return {}


@pytest.mark.parametrize("path", _hooks_files())
class TestHooksJsonSchema:
    def test_top_level_is_object(self, path):
        doc = json.loads(Path(path).read_text())
        assert isinstance(doc, dict), f"{path}: top-level must be a JSON object"

    def test_event_names_are_known(self, path):
        doc = json.loads(Path(path).read_text())
        events = _event_map(doc)
        assert events, f"{path}: no hook events declared"
        unknown = set(events.keys()) - KNOWN_EVENTS
        assert not unknown, f"{path}: unknown hook event(s): {unknown}"

    def test_each_event_has_hook_entries(self, path):
        doc = json.loads(Path(path).read_text())
        for event, entries in _event_map(doc).items():
            assert isinstance(entries, list) and entries, (
                f"{path}: event {event} must be a non-empty list"
            )
            for entry in entries:
                assert isinstance(entry, dict), (
                    f"{path}: entry under {event} must be an object"
                )
                assert "hooks" in entry and isinstance(entry["hooks"], list), (
                    f"{path}: entry under {event} missing 'hooks' array"
                )
                assert entry["hooks"], (
                    f"{path}: 'hooks' array under {event} must be non-empty"
                )

    def test_handlers_have_required_fields(self, path):
        doc = json.loads(Path(path).read_text())
        for event, entries in _event_map(doc).items():
            for entry in entries:
                for handler in entry["hooks"]:
                    assert handler.get("type") == "command", (
                        f"{path}: handler under {event} must have type='command'"
                    )
                    assert isinstance(handler.get("command"), str) and handler["command"], (
                        f"{path}: handler under {event} missing 'command' string"
                    )
                    if "timeout" in handler:
                        assert isinstance(handler["timeout"], int), (
                            f"{path}: timeout under {event} must be an integer"
                        )

    def test_referenced_handler_paths_exist(self, path):
        """Every ${CLAUDE_PLUGIN_ROOT}/<relpath> inside a command resolves."""
        doc = json.loads(Path(path).read_text())
        plugin_root = Path(path).parent.parent  # plugins/<name>/
        pattern = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s'\"]+)")
        for event, entries in _event_map(doc).items():
            for entry in entries:
                for handler in entry["hooks"]:
                    for match in pattern.finditer(handler["command"]):
                        rel = match.group(1)
                        resolved = plugin_root / rel
                        assert resolved.is_file(), (
                            f"{path}: command under {event} references missing "
                            f"file: {rel} (expected at {resolved})"
                        )
                        # Shell scripts should be executable; Python scripts are
                        # invoked via `python3` so no exec bit needed.
                        if rel.endswith(".sh"):
                            mode = resolved.stat().st_mode
                            assert mode & stat.S_IXUSR, (
                                f"{path}: shell handler {rel} is not executable"
                            )
