"""Conftest for security-guidance tests."""

import importlib.util
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def security_reminder_hook():
    """Import security_reminder_hook.py as a module."""
    path = PLUGIN_ROOT / "hooks" / "security_reminder_hook.py"
    spec = importlib.util.spec_from_file_location("security_reminder_hook", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
