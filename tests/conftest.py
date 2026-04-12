"""Root conftest for the claude-code test suite.

Provides fixtures that load standalone Python scripts as importable modules
(scripts that aren't part of a Python package and lack __init__.py).
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def security_reminder_hook():
    """Import security_reminder_hook.py as a module."""
    path = REPO_ROOT / "plugins" / "security-guidance" / "hooks" / "security_reminder_hook.py"
    spec = importlib.util.spec_from_file_location("security_reminder_hook", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def bash_command_validator():
    """Import bash_command_validator_example.py as a module."""
    path = REPO_ROOT / "examples" / "hooks" / "bash_command_validator_example.py"
    spec = importlib.util.spec_from_file_location("bash_command_validator_example", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
