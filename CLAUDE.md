# CLAUDE.md

Guidance for Claude (and other AI assistants) working in this repository.

## What this repository is

This is the public-facing repository for **Claude Code**, Anthropic's agentic coding CLI. Note that the Claude Code CLI itself is **not** open source — its source is not in this repo. What lives here is:

1. **Official Claude Code plugins** — a bundled marketplace of first-party plugins (`plugins/`, `.claude-plugin/marketplace.json`).
2. **Issue & PR automation** — GitHub Actions workflows plus TypeScript/Bash scripts that use Claude Code itself to triage issues, dedupe, and run lifecycle automation (`.github/workflows/`, `scripts/`, `.claude/commands/`).
3. **Examples and reference material** — sample settings files, hook examples, and a devcontainer (`examples/`, `.devcontainer/`).
4. **User-facing docs** — `README.md`, `CHANGELOG.md` (release notes for the CLI), `SECURITY.md`.
5. **Test suite** for the automation and hook scripts (`tests/`, `pytest.ini`, `scripts/run-tests.sh`, `.github/workflows/validate.yml`).

There is **no application source code to build** at the repo root — no `package.json`, `tsconfig.json`, or `src/` directory. Anything that looks like a build target lives inside a specific plugin or script. However, there **is** a test suite that covers the automation scripts and reference hooks; see "Testing" below.

## Top-level layout

```
claude-code/
├── .claude/
│   └── commands/              # Repo-scoped slash commands (commit-push-pr, dedupe, triage-issue)
├── .claude-plugin/
│   └── marketplace.json       # Marketplace manifest listing all bundled plugins
├── .devcontainer/             # Dev container definition used by the CLI's sandbox mode
│   ├── Dockerfile
│   ├── devcontainer.json
│   └── init-firewall.sh
├── .github/
│   ├── ISSUE_TEMPLATE/        # bug_report, feature_request, documentation, model_behavior
│   └── workflows/             # Claude-powered issue automation + validate.yml (see "GitHub automation")
├── .vscode/
│   └── extensions.json        # Recommended VS Code extensions (eslint, prettier, remote-containers, gitlens)
├── CHANGELOG.md               # Release notes for the Claude Code CLI (not for this repo)
├── CLAUDE.md                  # This file
├── README.md                  # User-facing install + usage instructions
├── SECURITY.md                # HackerOne disclosure policy
├── Script/
│   └── run_devcontainer_claude_code.ps1   # PowerShell helper to launch the devcontainer on Windows
├── demo.gif                   # Used by README (11 MB; do not regenerate casually)
├── examples/
│   ├── hooks/                 # bash_command_validator_example.py (PreToolUse hook sample)
│   └── settings/              # settings-lax, settings-strict, settings-bash-sandbox
├── plugins/                   # The bundled plugins (see below)
├── pytest.ini                 # Pytest config (testpaths + pythonpath for the test suite)
├── scripts/                   # Automation scripts invoked from GitHub Actions and slash commands
└── tests/                     # Shell / TypeScript / Python / validation test suite
```

## Bundled plugins (`plugins/`)

Every plugin in `plugins/` is also registered in `.claude-plugin/marketplace.json`. When adding, removing, or renaming a plugin, update **both** places — the marketplace manifest is the source of truth for what ships.

| Plugin | Entry points | Notes |
|---|---|---|
| `agent-sdk-dev` | `/new-sdk-app` command; `agent-sdk-verifier-py`, `agent-sdk-verifier-ts` agents | Scaffolds new Claude Agent SDK apps in Python/TS. |
| `claude-opus-4-5-migration` | `claude-opus-4-5-migration` skill | Migrates code/prompts from Sonnet 4.x / Opus 4.1 to Opus 4.5. |
| `code-review` | `/code-review` command | Runs 5 parallel Sonnet review agents over a PR. |
| `commit-commands` | `/commit`, `/commit-push-pr`, `/clean_gone` | Git workflow helpers. |
| `explanatory-output-style` | `SessionStart` hook | Injects educational context (mimics deprecated Explanatory style). |
| `feature-dev` | `/feature-dev` command; `code-explorer`, `code-architect`, `code-reviewer` agents | 7-phase feature workflow (discovery → summary). |
| `frontend-design` | `frontend-design` skill | Auto-invoked for frontend work; pushes away from generic AI aesthetics. |
| `hookify` | `/hookify`, `/hookify:list`, `/hookify:configure`, `/hookify:help`; `conversation-analyzer` agent; `writing-rules` skill | Python hook engine driven by markdown rule files (`.claude/hookify.*.local.md`). Has its own `core/`, `matchers/`, `utils/`, `hooks/`, `examples/`. |
| `learning-output-style` | `SessionStart` hook | Interactive learning mode. |
| `plugin-dev` | `/plugin-dev:create-plugin` command; `agent-creator`, `plugin-validator`, `skill-reviewer` agents; 7 skills | Toolkit for authoring new plugins. The skills under `plugins/plugin-dev/skills/` are the canonical reference for how hooks, commands, agents, MCP integration, and plugin structure should be authored in this repo. |
| `pr-review-toolkit` | `/pr-review-toolkit:review-pr` command; 6 specialized review agents | `comment-analyzer`, `pr-test-analyzer`, `silent-failure-hunter`, `type-design-analyzer`, `code-reviewer`, `code-simplifier`. |
| `ralph-wiggum` | `/ralph-loop`, `/cancel-ralph` commands; `Stop` hook | Self-referential iteration loop. |
| `security-guidance` | `PreToolUse` hook (`security_reminder_hook.py`) | Warns about injection/XSS/eval/pickle/os.system patterns during edits. |

### Standard plugin layout

```
plugins/<name>/
├── .claude-plugin/plugin.json   # Plugin metadata (optional per-plugin)
├── commands/                    # Slash commands (markdown with YAML frontmatter)
├── agents/                      # Subagent definitions (markdown with YAML frontmatter)
├── skills/                      # Skills, each with a SKILL.md
├── hooks/                       # hooks.json + handler scripts
├── .mcp.json                    # External MCP server config (optional)
└── README.md                    # Always present; user-facing docs for the plugin
```

Not every plugin uses every subdirectory — follow what the existing plugin does. `hookify` is the one outlier with extra Python package dirs (`core/`, `matchers/`, `utils/`) because it implements a rule engine.

### Rules for modifying a plugin

- Keep each plugin self-contained. A plugin should never reach into another plugin's directory at runtime.
- When touching a plugin's public surface (command names, agent names, skill names, hook events), update that plugin's `README.md` in the same change.
- `.claude-plugin/marketplace.json` lists every plugin with `name`, `description`, `version`, `author`, `source`, `category`. Adding a plugin means appending a new entry here; removing means deleting it.
- Plugin READMEs are the user-facing docs — they link from the repo-level `plugins/README.md` table. If you add/remove a plugin, update that table too.

## Repo-level slash commands (`.claude/commands/`)

These commands are scoped to this repo and are invoked from GitHub Actions workflows via `anthropics/claude-code-action`:

- **`/commit-push-pr`** — Creates a branch if on `main`, commits, pushes, and opens a PR via `gh pr create`. `allowed-tools` frontmatter restricts it to specific git/gh invocations.
- **`/dedupe`** — Finds up to 3 likely duplicates for a given issue. Uses only `./scripts/gh.sh` (not raw `gh`) and `./scripts/comment-on-duplicates.sh`. Runs from `.github/workflows/claude-dedupe-issues.yml` on issue open.
- **`/triage-issue`** — Reads labels with `./scripts/gh.sh label list`, then applies via `./scripts/edit-issue-labels.sh`. Two modes based on `EVENT`: new issues (apply category + lifecycle labels) vs. comments (update lifecycle labels only). Never posts comments.

When editing these commands, respect the `allowed-tools` frontmatter — it's enforced by the Claude Code runtime and is intentionally narrow.

## `scripts/`

Mixed bag of automation used by workflows and slash commands. Two notable groups:

**GitHub automation** (invoked from `.github/workflows/`):
- `gh.sh` — **Hardened wrapper** around `gh`. Only permits `issue view`, `issue list`, `search issues`, `label list`, and only a tiny set of flags (`--comments`, `--state`, `--limit`, `--label`). Blocks `repo:`/`org:`/`user:` qualifiers in search queries. **Always call this wrapper instead of `gh` directly** — the slash commands in `.claude/commands/` assume it.
- `edit-issue-labels.sh` — Add/remove labels (issue number read from workflow event).
- `comment-on-duplicates.sh` — Posts the canonical duplicate-detected comment.
- `auto-close-duplicates.ts`, `backfill-duplicate-comments.ts`, `issue-lifecycle.ts`, `lifecycle-comment.ts`, `sweep.ts` — TypeScript helpers run from workflows.

**Security audit scripts** (standalone, not invoked by workflows):
- `analyze_apk.py`, `iphone_security_checklist.py`, `router_audit.py`, `security_audit.py` plus `SECURITY_GUIDE.md`, `ROUTER_SECURITY_GUIDE.md`. These are example/utility scripts that aren't wired into any workflow.

When modifying a script that's referenced from a slash command, re-read the command's `allowed-tools` frontmatter to confirm the invocation shape is still permitted.

## GitHub Actions (`.github/workflows/`)

Most workflows invoke Claude Code itself via `anthropics/claude-code-action@v1` and pin the model via `claude_args: "--model claude-sonnet-4-5-20250929"`.

- `claude.yml` — Responds to `@claude` mentions in issues, PR reviews, and comments.
- `claude-dedupe-issues.yml` — Runs `/dedupe` on issue open. Also emits a Statsig event.
- `claude-issue-triage.yml` — Runs `/triage-issue` on issue open and issue comments.
- `auto-close-duplicates.yml`, `backfill-duplicate-comments.yml` — Duplicate-comment lifecycle.
- `issue-lifecycle-comment.yml`, `lock-closed-issues.yml`, `remove-autoclose-label.yml`, `log-issue-events.yml`, `sweep.yml` — Lifecycle maintenance.
- `issue-opened-dispatch.yml` — Central dispatcher fired on issue open.
- `non-write-users-check.yml` — Guards workflows against untrusted input.
- `validate.yml` — **CI for this repo.** Runs on every `pull_request` and `push`: installs Bun + Python 3.12 and executes `bash scripts/run-tests.sh` (shell → TypeScript → Python tests). This is the only workflow that is not Claude-driven; it's the gate that keeps the automation scripts and hooks from regressing.

When adding a new Claude-invoking workflow, follow the pattern in `claude-dedupe-issues.yml`: scoped permissions, pinned action version, explicit model, and `CLAUDE_CODE_SCRIPT_CAPS` for any scripts the workflow allows Claude to execute.

## Tests (`tests/`, `pytest.ini`, `scripts/run-tests.sh`)

The repo has a real test suite that covers the automation scripts and reference hooks. `scripts/run-tests.sh` is the single entrypoint and runs three stages in order:

1. **Shell tests** — `bash tests/shell/run.sh`
   - `test_gh_wrapper.sh`, `test_edit_issue_labels.sh`, `test_comment_on_duplicates.sh`
   - Uses `tests/shell/stubs/gh` (a fake `gh` on `$PATH`) and `tests/shell/fixtures/event-payload.json`
   - Helpers live in `tests/shell/helpers.sh`
2. **TypeScript tests** — `bun test tests/ts/`
   - Covers `scripts/auto-close-duplicates.ts`, `backfill-duplicate-comments.ts`, `issue-lifecycle.ts`, `lifecycle-comment.ts`, `sweep.ts`
   - Requires `bun` on `$PATH` (the `validate.yml` workflow installs it via `oven-sh/setup-bun@v2`)
3. **Python tests** — `pytest` (config in `pytest.ini`)
   - `testpaths = tests plugins/hookify/tests plugins/security-guidance/tests`
   - `pythonpath = plugins` so hookify's package imports resolve
   - `tests/conftest.py` exposes `security_reminder_hook` and `bash_command_validator` fixtures that load the two standalone hook scripts as modules
   - `tests/validate/` contains **manifest-level checks**: `test_manifest_consistency.py`, `test_hooks_schema.py`, `test_command_allowed_tools.py`, `test_allowed_tools_snapshot.py` (snapshot in `tests/validate/baselines/allowed-tools.expected.json`)

### When modifying automation

- Changing `scripts/gh.sh`, `edit-issue-labels.sh`, or `comment-on-duplicates.sh` → re-run `bash tests/shell/run.sh`.
- Changing any `scripts/*.ts` → re-run `bun test tests/ts/`.
- Changing a hook in `examples/hooks/` or `plugins/*/hooks/` → re-run `pytest tests/python` (plus the plugin's own tests under `plugins/hookify/tests` / `plugins/security-guidance/tests`).
- Changing **anything about a command's `allowed-tools` frontmatter**, a plugin's `hooks.json`, or the marketplace manifest → `pytest tests/validate` will catch drift. If you legitimately change the `allowed-tools` surface, regenerate the snapshot in `tests/validate/baselines/allowed-tools.expected.json` in the same commit.

Before opening a PR, run `bash scripts/run-tests.sh` locally — that's exactly what `validate.yml` runs in CI.

## `examples/`

Reference configurations users can copy:

- `examples/settings/` — `settings-lax.json`, `settings-strict.json`, `settings-bash-sandbox.json` with a comparison table in `README.md`. These are **community examples**; the README warns they may be incorrect — don't treat them as canonical.
- `examples/hooks/bash_command_validator_example.py` — A PreToolUse hook that rewrites `grep`→`rg` and `find -name`→`rg`. Uses exit code 2 to block, exit code 1 for user-visible errors.

## Conventions for AI assistants working here

### Don't

- **Don't invent build commands.** There is no root `npm install` or `npm test` — this repo is not a Node package. The test entrypoint is `bash scripts/run-tests.sh` (which in turn runs shell tests, `bun test tests/ts/`, and `pytest`). Individual plugins may have their own language/tooling (hookify uses Python stdlib only, ralph-wiggum uses shell), but no repo-wide **build** exists — just the test suite.
- **Don't create a `CLAUDE.md` inside a plugin** unless the user asks — plugins communicate through their `README.md`.
- **Don't touch `demo.gif`** — it's 11 MB and checked in. Regenerating it bloats history.
- **Don't add raw `gh` calls** to slash commands or scripts that are invoked from workflows. Use `./scripts/gh.sh`. The wrapper exists specifically to keep Claude Code–driven automation inside a safe subset of the GitHub API.
- **Don't create new plugins via ad hoc copy/paste.** Use the `plugin-dev` plugin's `/plugin-dev:create-plugin` command and its skills, or at minimum mirror the structure of an existing plugin exactly.
- **Don't forget the marketplace manifest** when adding/removing/renaming a plugin — `.claude-plugin/marketplace.json` must stay in sync.
- **Don't skip the `plugins/README.md` table** update when the plugin roster changes.

### Do

- Edit plugin READMEs in the same commit as the plugin code they describe. They're the primary user-facing docs.
- Preserve `allowed-tools` frontmatter narrowness in `.claude/commands/*.md` — it's a security boundary, not a convenience.
- Match the conventions of neighboring files. Commands and agents are markdown with YAML frontmatter (`description:`, `allowed-tools:`, etc.). Hooks are either `hooks.json` + a handler script, or Python scripts that read JSON from stdin and use exit codes to signal behavior (0 = allow, 1 = error to user, 2 = block with message to Claude — see `examples/hooks/bash_command_validator_example.py`).
- When writing Python hooks, follow `examples/hooks/bash_command_validator_example.py` and `plugins/security-guidance/hooks/security_reminder_hook.py` — stdlib only, exit codes for signaling, JSON on stdin.
- When shelling out in workflows, prefer the existing hardened wrappers (`scripts/gh.sh`, `scripts/edit-issue-labels.sh`, `scripts/comment-on-duplicates.sh`).
- Keep changes scoped. Don't refactor unrelated plugins, don't "drive-by" fix CHANGELOG.md (it's release notes for the CLI itself, maintained separately), and don't alter workflow action pins without an explicit reason.

### Searching this repo

Ripgrep/Grep is the right tool. Useful starting points:

- Plugin manifest: `.claude-plugin/marketplace.json`
- All plugin entry points: `plugins/*/commands/*.md`, `plugins/*/agents/*.md`, `plugins/*/skills/*/SKILL.md`, `plugins/*/hooks/hooks.json`
- Workflow-driven commands: `.claude/commands/*.md`
- GitHub automation scripts: `scripts/*.sh`, `scripts/*.ts`

### Testing changes

- **Default**: run `bash scripts/run-tests.sh` from the repo root. That's the same thing `.github/workflows/validate.yml` runs in CI (shell → TypeScript → Python).
- **Plugin changes (behavior)**: Validate by installing the plugin in a local Claude Code session (`/plugin` or by configuring the marketplace locally). Most plugins have no runtime harness; `plugins/hookify/` and `plugins/security-guidance/` do have pytest suites that run as part of the root `pytest` invocation.
- **Slash command / script changes**: The shell tests (`tests/shell/`) cover `gh.sh`, `edit-issue-labels.sh`, and `comment-on-duplicates.sh`. TypeScript scripts are covered by `tests/ts/`. Beyond that, the slash commands are exercised live from workflows on real issues — be careful not to break `/triage-issue` or `/dedupe`.
- **Hook changes**: Unit-test with the `security_reminder_hook` / `bash_command_validator` fixtures in `tests/conftest.py`, or pipe representative JSON into the hook on stdin (`echo '{...}' | python3 hook.py`) and check exit code + stderr.
- **Manifest / frontmatter changes**: `tests/validate/` parses every `plugin.json`, `hooks.json`, `marketplace.json`, and command frontmatter, and snapshots the full `allowed-tools` surface. If `pytest tests/validate` fails, fix the manifest — don't blindly regenerate the snapshot unless the surface change is intentional.
- **JSON/YAML correctness**: `marketplace.json`, `plugin.json`, `hooks.json`, `devcontainer.json`, and every command's frontmatter must parse. A broken manifest breaks the whole marketplace (and the validation tests will catch it).

## Quick reference: where to look first

| Task | Start here |
|---|---|
| Add a new bundled plugin | `plugins/plugin-dev/` + `.claude-plugin/marketplace.json` + `plugins/README.md` |
| Change issue triage behavior | `.claude/commands/triage-issue.md` + `.github/workflows/claude-issue-triage.yml` |
| Change dedupe behavior | `.claude/commands/dedupe.md` + `.github/workflows/claude-dedupe-issues.yml` + `scripts/comment-on-duplicates.sh` |
| Add/restrict a new `gh` operation | `scripts/gh.sh` (update the allowed subcommands / flags) |
| Add an example settings profile | `examples/settings/` + update the comparison table in `examples/settings/README.md` |
| Add a reference hook | `examples/hooks/` |
| Modify the devcontainer | `.devcontainer/` (Dockerfile, devcontainer.json, init-firewall.sh) |
| Run the full test suite | `bash scripts/run-tests.sh` (same as CI `validate.yml`) |
| Add tests for a shell script | `tests/shell/` (fixture in `fixtures/`, stub `gh` in `stubs/`, helpers in `helpers.sh`) |
| Add tests for a TS script | `tests/ts/` — `bun test tests/ts/` |
| Add tests for a hook / Python script | `tests/python/` (plus fixtures in `tests/conftest.py`) |
| Fix a manifest validation failure | `tests/validate/` — regenerate `baselines/allowed-tools.expected.json` only if the surface change is intentional |
