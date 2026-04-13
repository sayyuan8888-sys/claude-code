"""Parse-ability tests for repo-level config files.

CLAUDE.md specifies that `marketplace.json`, `plugin.json`, `hooks.json`,
`devcontainer.json`, and every command's frontmatter must parse. The first
three are covered in `test_manifest_consistency.py` / `test_hooks_schema.py`;
this file adds:

  - `.devcontainer/devcontainer.json`
  - `.github/ISSUE_TEMPLATE/*.yml`

Broken issue templates silently break GitHub's issue form UI; a broken
devcontainer.json breaks every sandbox session launched from this repo.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEVCONTAINER_JSON = REPO_ROOT / ".devcontainer" / "devcontainer.json"
ISSUE_TEMPLATE_DIR = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"


class TestDevcontainerJson:
    def test_file_exists(self):
        assert DEVCONTAINER_JSON.is_file(), (
            f"Missing {DEVCONTAINER_JSON} — referenced by .devcontainer/Dockerfile"
        )

    def test_parses_as_json(self):
        data = json.loads(DEVCONTAINER_JSON.read_text())
        assert isinstance(data, dict)

    def test_has_name_field(self):
        data = json.loads(DEVCONTAINER_JSON.read_text())
        assert "name" in data, "devcontainer.json must declare a 'name'"


_ISSUE_TEMPLATES = sorted(ISSUE_TEMPLATE_DIR.glob("*.yml")) if ISSUE_TEMPLATE_DIR.exists() else []


class TestIssueTemplateDiscovery:
    def test_glob_finds_at_least_one_template(self):
        # The repo ships 4 issue forms (bug_report, documentation,
        # feature_request, model_behavior) plus config.yml. If the glob
        # returns nothing, the parametrized tests below silently pass.
        assert _ISSUE_TEMPLATES, (
            f"No issue templates found in {ISSUE_TEMPLATE_DIR}"
        )


@pytest.mark.parametrize("path", _ISSUE_TEMPLATES)
class TestIssueTemplates:
    def test_parses_as_yaml(self, path):
        yaml = pytest.importorskip("yaml")
        data = yaml.safe_load(path.read_text())
        assert data is not None, f"{path.name}: parsed to None (empty file?)"
        assert isinstance(data, dict), f"{path.name}: top-level must be a mapping"

    def test_form_templates_have_name_and_body(self, path):
        # GitHub issue forms (anything that isn't `config.yml`) must have
        # `name` and `body`. `config.yml` is the template chooser config and
        # doesn't follow the form schema.
        yaml = pytest.importorskip("yaml")
        if path.name == "config.yml":
            pytest.skip("config.yml uses a different schema")
        data = yaml.safe_load(path.read_text())
        for field in ("name", "description", "body"):
            assert field in data, f"{path.name}: missing required field {field!r}"
        assert isinstance(data["body"], list), (
            f"{path.name}: 'body' must be a list of form elements"
        )
