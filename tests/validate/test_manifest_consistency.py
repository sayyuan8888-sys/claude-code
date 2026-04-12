"""Tests that validate marketplace.json, plugin directories, and README consistency."""

import glob
import json
import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PLUGINS_DIR = REPO_ROOT / "plugins"
PLUGINS_README = PLUGINS_DIR / "README.md"


class TestMarketplaceJson:
    def test_parses_as_valid_json(self):
        data = json.loads(MARKETPLACE_JSON.read_text())
        assert isinstance(data, dict)

    def test_has_plugins_array(self):
        data = json.loads(MARKETPLACE_JSON.read_text())
        assert "plugins" in data
        assert isinstance(data["plugins"], list)
        assert len(data["plugins"]) > 0

    def test_every_plugin_has_required_fields(self):
        data = json.loads(MARKETPLACE_JSON.read_text())
        required = {"name", "description", "source", "category"}
        for plugin in data["plugins"]:
            missing = required - set(plugin.keys())
            assert not missing, f"Plugin '{plugin.get('name', '?')}' missing fields: {missing}"

    def test_every_source_path_exists(self):
        data = json.loads(MARKETPLACE_JSON.read_text())
        for plugin in data["plugins"]:
            source = plugin["source"]
            # source is relative to repo root, e.g. "./plugins/agent-sdk-dev"
            abs_path = (REPO_ROOT / source).resolve()
            assert abs_path.is_dir(), f"Source path does not exist: {source}"


class TestPluginDirectoryConsistency:
    @staticmethod
    def _get_plugin_dirs():
        """Get all plugin directory names (excluding non-directory entries)."""
        return sorted(
            d.name
            for d in PLUGINS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

    @staticmethod
    def _get_marketplace_names():
        data = json.loads(MARKETPLACE_JSON.read_text())
        return sorted(p["name"] for p in data["plugins"])

    def test_every_plugin_dir_in_marketplace(self):
        dirs = self._get_plugin_dirs()
        manifest = self._get_marketplace_names()
        missing = set(dirs) - set(manifest)
        assert not missing, f"Plugin dirs missing from marketplace.json: {missing}"

    def test_every_marketplace_entry_has_dir(self):
        dirs = self._get_plugin_dirs()
        manifest = self._get_marketplace_names()
        missing = set(manifest) - set(dirs)
        assert not missing, f"Marketplace entries with no plugin dir: {missing}"

    def test_every_plugin_has_readme(self):
        for d in PLUGINS_DIR.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                readme = d / "README.md"
                assert readme.exists(), f"Plugin {d.name} missing README.md"


class TestPluginsReadmeTable:
    def test_every_plugin_mentioned_in_readme(self):
        readme_text = PLUGINS_README.read_text()
        dirs = sorted(
            d.name
            for d in PLUGINS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )
        for name in dirs:
            assert name in readme_text, (
                f"Plugin '{name}' not mentioned in plugins/README.md"
            )


class TestHooksJsonValid:
    def test_all_hooks_json_parse(self):
        pattern = str(PLUGINS_DIR / "**" / "hooks.json")
        for path in glob.glob(pattern, recursive=True):
            data = json.loads(Path(path).read_text())
            assert isinstance(data, (dict, list)), f"Invalid hooks.json: {path}"


class TestCommandFrontmatter:
    @staticmethod
    def _has_valid_frontmatter(path: Path) -> bool:
        """Check that a .md file starts with --- and has a closing ---."""
        text = path.read_text()
        if not text.startswith("---"):
            return False
        parts = text.split("---", 2)
        return len(parts) >= 3

    def test_repo_commands_have_frontmatter(self):
        cmd_dir = REPO_ROOT / ".claude" / "commands"
        if not cmd_dir.exists():
            pytest.skip("No .claude/commands directory")
        for f in cmd_dir.glob("*.md"):
            assert self._has_valid_frontmatter(f), (
                f"Command {f.name} has invalid frontmatter"
            )

    def test_plugin_commands_have_frontmatter(self):
        for cmd_file in PLUGINS_DIR.glob("*/commands/*.md"):
            assert self._has_valid_frontmatter(cmd_file), (
                f"Plugin command {cmd_file} has invalid frontmatter"
            )

    def test_plugin_agents_have_frontmatter(self):
        for agent_file in PLUGINS_DIR.glob("*/agents/*.md"):
            assert self._has_valid_frontmatter(agent_file), (
                f"Plugin agent {agent_file} has invalid frontmatter"
            )
