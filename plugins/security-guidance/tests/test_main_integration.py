"""Integration tests for security_reminder_hook.main().

Drives the script as a subprocess with real stdin JSON, verifying the
exit-code contract (0=allow, 2=block) and stderr output.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = PLUGIN_ROOT / "hooks" / "security_reminder_hook.py"


def _run_hook(stdin_payload: str, home: Path, extra_env=None):
    """Run the hook with HOME redirected to a tmp dir so state files are sandboxed."""
    env = os.environ.copy()
    env["HOME"] = str(home)
    # Make cleanup deterministic: disable the 10%-chance cleanup by seeding random
    env["PYTHONHASHSEED"] = "0"
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.fixture()
def fake_home(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    return tmp_path


class TestMainExitContract:
    def test_malformed_json_exits_zero(self, fake_home):
        rc, _, _ = _run_hook("not-json{", fake_home)
        assert rc == 0

    def test_non_file_tool_exits_zero(self, fake_home):
        payload = json.dumps({
            "session_id": "s1",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        })
        rc, _, _ = _run_hook(payload, fake_home)
        assert rc == 0

    def test_missing_file_path_exits_zero(self, fake_home):
        payload = json.dumps({
            "session_id": "s1",
            "tool_name": "Write",
            "tool_input": {"content": "eval(user_input)"},
        })
        rc, _, _ = _run_hook(payload, fake_home)
        assert rc == 0

    def test_clean_content_exits_zero(self, fake_home):
        payload = json.dumps({
            "session_id": "s1",
            "tool_name": "Write",
            "tool_input": {"file_path": "app.py", "content": "print('hello')"},
        })
        rc, stderr, _ = _run_hook(payload, fake_home)
        # stdout/stderr swapped in helper: returns (rc, stdout, stderr)
        assert rc == 0

    def test_disabled_via_env_exits_zero_without_processing(self, fake_home):
        payload = json.dumps({
            "session_id": "s1",
            "tool_name": "Write",
            "tool_input": {"file_path": ".github/workflows/ci.yml", "content": ""},
        })
        rc, _, stderr = _run_hook(payload, fake_home, extra_env={"ENABLE_SECURITY_REMINDER": "0"})
        assert rc == 0
        assert stderr == ""


class TestMainBlocksAndWarns:
    def test_github_workflow_edit_blocks_with_stderr(self, fake_home):
        payload = json.dumps({
            "session_id": "sess-block-1",
            "tool_name": "Write",
            "tool_input": {
                "file_path": ".github/workflows/ci.yml",
                "content": "name: ci\n",
            },
        })
        rc, _, stderr = _run_hook(payload, fake_home)
        assert rc == 2
        assert "GitHub Actions" in stderr or "github" in stderr.lower()

    def test_eval_in_python_blocks(self, fake_home):
        payload = json.dumps({
            "session_id": "sess-block-2",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "app.py",
                "new_string": "result = eval(user_input)",
            },
        })
        rc, _, stderr = _run_hook(payload, fake_home)
        assert rc == 2
        assert stderr != ""

    def test_same_warning_deduplicates_within_session(self, fake_home):
        payload = json.dumps({
            "session_id": "sess-dedup",
            "tool_name": "Write",
            "tool_input": {
                "file_path": ".github/workflows/ci.yml",
                "content": "",
            },
        })
        # First invocation should block (new warning)
        rc1, _, _ = _run_hook(payload, fake_home)
        assert rc1 == 2
        # Second invocation for same file+rule in same session should NOT block
        rc2, _, stderr2 = _run_hook(payload, fake_home)
        assert rc2 == 0
        assert stderr2 == ""

    def test_different_session_sees_warning_again(self, fake_home):
        base = {
            "tool_name": "Write",
            "tool_input": {"file_path": ".github/workflows/ci.yml", "content": ""},
        }
        rc1, _, _ = _run_hook(json.dumps({**base, "session_id": "s-a"}), fake_home)
        rc2, _, _ = _run_hook(json.dumps({**base, "session_id": "s-b"}), fake_home)
        assert rc1 == 2
        assert rc2 == 2
