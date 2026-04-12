"""Snapshot test for allowed-tools frontmatter in repo-level commands.

Detects drive-by widening of the allowed-tools security boundary.

To update the baseline after an intentional change:
    UPDATE_BASELINES=1 pytest tests/validate/test_allowed_tools_snapshot.py
"""

import json
import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"
BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "allowed-tools.expected.json"


def _extract_allowed_tools() -> dict[str, str]:
    """Scan every .claude/commands/*.md and extract the allowed-tools line."""
    result = {}
    if not COMMANDS_DIR.exists():
        return result
    for f in sorted(COMMANDS_DIR.glob("*.md")):
        text = f.read_text()
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        frontmatter = parts[1]
        for line in frontmatter.splitlines():
            line = line.strip()
            if line.startswith("allowed-tools:"):
                value = line[len("allowed-tools:"):].strip()
                result[f.name] = value
                break
    return result


class TestAllowedToolsSnapshot:
    def test_matches_baseline(self):
        current = _extract_allowed_tools()

        if os.environ.get("UPDATE_BASELINES") == "1":
            BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
            BASELINE_PATH.write_text(json.dumps(current, indent=2) + "\n")
            pytest.skip("Baseline updated — re-run without UPDATE_BASELINES")

        if not BASELINE_PATH.exists():
            BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
            BASELINE_PATH.write_text(json.dumps(current, indent=2) + "\n")
            pytest.fail(
                "No baseline existed — one has been created. "
                "Review tests/validate/baselines/allowed-tools.expected.json "
                "and re-run."
            )

        expected = json.loads(BASELINE_PATH.read_text())
        if current != expected:
            diff_lines = []
            all_keys = sorted(set(list(current.keys()) + list(expected.keys())))
            for key in all_keys:
                cur = current.get(key)
                exp = expected.get(key)
                if cur != exp:
                    diff_lines.append(f"  {key}:")
                    diff_lines.append(f"    expected: {exp}")
                    diff_lines.append(f"    actual:   {cur}")
            diff_msg = "\n".join(diff_lines)
            pytest.fail(
                f"allowed-tools frontmatter has changed:\n{diff_msg}\n\n"
                "If this is intentional, run:\n"
                "  UPDATE_BASELINES=1 pytest tests/validate/test_allowed_tools_snapshot.py"
            )
