"""Conftest for hookify tests."""
import pytest
from hookify.core.config_loader import Condition, Rule


@pytest.fixture()
def sample_rule():
    """A basic rule for testing."""
    return Rule(
        name="test-rm",
        enabled=True,
        event="bash",
        conditions=[
            Condition(field="command", operator="regex_match", pattern=r"rm\s+-rf")
        ],
        action="warn",
        message="Dangerous rm command detected!",
    )


@pytest.fixture()
def blocking_rule():
    """A blocking rule for testing."""
    return Rule(
        name="block-rm",
        enabled=True,
        event="bash",
        conditions=[
            Condition(field="command", operator="regex_match", pattern=r"rm\s+-rf")
        ],
        action="block",
        message="Blocked: dangerous rm command!",
    )
