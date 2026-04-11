# CLAUDE.md

Guidance for Claude (and other AI assistants) working in this repository.

## What this repository is

This is the public-facing repository for **Claude Code**, Anthropic's agentic coding CLI. Note that the Claude Code CLI itself is **not** open source — its source is not in this repo. What lives here is:

1. **Official Claude Code plugins** — a bundled marketplace of first-party plugins (`plugins/`, `.claude-plugin/marketplace.json`).
2. **Issue & PR automation** — GitHub Actions workflows plus TypeScript/Bash scripts that use Claude Code itself to triage issues, dedupe, and run lifecycle automation (`.github/workflows/`, `scripts/`, `.claude/commands/`).
3. **Examples and reference material** — sample settings files, hook examples, and a devcontainer (`examples/`, `.devcontainer/`).
4. **User-facing docs** — `README.md`, `CHANGELOG.md` (release notes for the CLI), `SECURITY.md`.

There is **no application source code to build or test** at the repo root. Do not look for a `package.json`, `tsconfig.json`, or a `src/` directory in the root — there isn't one. Anything that looks like a build target lives inside a specific plugin or script.

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
│   └── workflows/             # Claude-powered issue automation (see "GitHub automation")
├── CHANGELOG.md               # Release notes for the Claude Code CLI (not for this repo)
├── README.md                  # User-facing install + usage instructions
├── SECURITY.md                # HackerOne disclosure policy
├── Script/
│   └── run_devcontainer_claude_code.ps1   # PowerShell helper to launch the devcontainer on Windows
├── demo.gif                   # Used by README (11 MB; do not regenerate casually)
├── examples/
│   ├── hooks/                 # bash_command_validator_example.py (PreToolUse hook sample)
│   └── settings/              # settings-lax, settings-strict, settings-bash-sandbox
├── plugins/                   # The bundled plugins (see below)
└── scripts/                   # Automation scripts invoked from GitHub Actions and slash commands
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

When adding a new Claude-invoking workflow, follow the pattern in `claude-dedupe-issues.yml`: scoped permissions, pinned action version, explicit model, and `CLAUDE_CODE_SCRIPT_CAPS` for any scripts the workflow allows Claude to execute.

## `examples/`

Reference configurations users can copy:

- `examples/settings/` — `settings-lax.json`, `settings-strict.json`, `settings-bash-sandbox.json` with a comparison table in `README.md`. These are **community examples**; the README warns they may be incorrect — don't treat them as canonical.
- `examples/hooks/bash_command_validator_example.py` — A PreToolUse hook that rewrites `grep`→`rg` and `find -name`→`rg`. Uses exit code 2 to block, exit code 1 for user-visible errors.

## Conventions for AI assistants working here

### Don't

- **Don't invent build commands.** There is no root `npm install`, `npm test`, `pytest`, or equivalent for the repo itself. Individual plugins may have their own language/tooling (hookify uses Python stdlib only, ralph-wiggum uses shell), but no repo-wide build exists.
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

- **Plugin changes**: Validate by installing the plugin in a local Claude Code session (`/plugin` or by configuring the marketplace locally). There is no repo-level plugin test harness.
- **Slash command / script changes**: Manually run the script with representative input; the slash commands are exercised live from workflows on real issues, so be careful not to break `/triage-issue` or `/dedupe`.
- **Hook changes**: Pipe representative JSON into the hook on stdin (`echo '{...}' | python3 hook.py`) and check exit code + stderr.
- **JSON/YAML correctness**: `marketplace.json`, `plugin.json`, `hooks.json`, `devcontainer.json`, and every command's frontmatter must parse. A broken manifest breaks the whole marketplace.

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
