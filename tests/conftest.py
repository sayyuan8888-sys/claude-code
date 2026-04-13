"""Root conftest for the claude-code test suite.

Provides fixtures that load standalone Python scripts as importable modules
(scripts that aren't part of a Python package and lack __init__.py).

Note: the `security_reminder_hook` fixture lives in
`plugins/security-guidance/tests/conftest.py` (the plugin's local conftest),
since only plugin tests use it and keeping it there makes the plugin
self-contained.
"""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def bash_command_validator():
    """Import bash_command_validator_example.py as a module."""
    path = REPO_ROOT / "examples" / "hooks" / "bash_command_validator_example.py"
    spec = importlib.util.spec_from_file_location("bash_command_validator_example", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
