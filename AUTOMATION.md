# Automation map

How the Claude-driven issue automation in this repo fits together. Pair this
with `CLAUDE.md` (which covers repo conventions) and `plugins/README.md`
(which covers the bundled plugins).

There are three layers:

1. **GitHub Actions workflows** (`.github/workflows/*.yml`) — the triggers
2. **Slash commands** (`.claude/commands/*.md`) — what Claude runs for each trigger
3. **Scripts** (`scripts/*.sh`, `scripts/*.ts`) — the hardened tools the commands are allowed to call

Every Claude-driven workflow pins its model explicitly and constrains what
Claude can invoke via the command's `allowed-tools` frontmatter plus
`CLAUDE_CODE_SCRIPT_CAPS`. The non-Claude workflows are plain TypeScript
(via Bun) or inline `actions/github-script`.

## Workflow → command → scripts

| Workflow | Trigger | Invokes | Model | Scripts allowed |
|---|---|---|---|---|
| `claude.yml` | `@claude` mention in issues/PRs | free-form prompt | `claude-sonnet-4-5-20250929` | — |
| `claude-dedupe-issues.yml` | issue opened, manual | `/dedupe` | `claude-sonnet-4-5-20250929` | `gh.sh`, `comment-on-duplicates.sh` (cap 1) |
| `claude-issue-triage.yml` | issue opened, issue comment | `/triage-issue` | `claude-opus-4-6` (see below) | `gh.sh`, `edit-issue-labels.sh` (cap 2) |
| `auto-close-duplicates.yml` | cron 09:00 UTC | `scripts/auto-close-duplicates.ts` | n/a | — |
| `sweep.yml` | cron 10:00 + 22:00 UTC | `scripts/sweep.ts` | n/a | — |
| `issue-lifecycle-comment.yml` | issue labeled | `scripts/lifecycle-comment.ts` | n/a | — |
| `backfill-duplicate-comments.yml` | manual | `scripts/backfill-duplicate-comments.ts` | n/a | — |
| `lock-closed-issues.yml` | cron 14:00 UTC | inline `actions/github-script` | n/a | — |
| `remove-autoclose-label.yml` | issue comment | inline `actions/github-script` | n/a | — |
| `issue-opened-dispatch.yml` | issue opened | `gh api` dispatch to external repo | n/a | — |
| `log-issue-events.yml` | issue opened/closed | `curl` Statsig POST | n/a | — |
| `non-write-users-check.yml` | PR to `.github/**` | `gh` CLI (security gate) | n/a | — |
| `validate.yml` | pull_request, push | `bash scripts/run-tests.sh` | n/a | — |

### Why `claude-issue-triage.yml` uses Opus

Every other Claude-driven workflow pins Sonnet. Triage uses Opus because the
task is substantially more reasoning-heavy: it must read the issue and its
full comment thread, decide whether it's actually about Claude Code, pick
from an open-ended category label set, search for duplicates, and apply the
right lifecycle labels. If you add a workflow that does comparable analysis,
Opus is a defensible choice; otherwise, default to Sonnet.

## Slash commands (repo-scoped)

Under `.claude/commands/`, each command's `allowed-tools` frontmatter is a
**security boundary** — it narrowly permits only the script invocations the
command actually needs. Do not widen these without deliberate reason.

| Command | allowed-tools | Invoked from |
|---|---|---|
| `commit-push-pr.md` | git commands + `gh pr create` | manual (not a workflow) |
| `dedupe.md` | `./scripts/gh.sh:*`, `./scripts/comment-on-duplicates.sh:*` | `claude-dedupe-issues.yml` |
| `triage-issue.md` | `./scripts/gh.sh:*`, `./scripts/edit-issue-labels.sh:*` | `claude-issue-triage.yml` |

`scripts/gh.sh` is itself a hardened wrapper around the `gh` CLI: it only
permits `issue view`, `issue list`, `search issues`, and `label list`, with
a small allowlist of flags and no cross-repo search qualifiers. When a
slash command needs GitHub read access, it calls `gh.sh`, never `gh`
directly. See `scripts/gh.sh` and `tests/shell/test_gh_wrapper.sh` for the
exact subset.

## TypeScript lifecycle scripts

`scripts/issue-lifecycle.ts` is the single source of truth for the labels
that drive auto-close behavior (`invalid`, `needs-repro`, `needs-info`,
`stale`, `autoclose`) and the per-label timeout. `sweep.ts`,
`lifecycle-comment.ts`, and `auto-close-duplicates.ts` all import from it.
Change the lifecycle config there and the workflows pick it up.

`backfill-duplicate-comments.ts` is a manual tool that walks historical
issues (bounded by `MIN_ISSUE_NUMBER`/`MAX_ISSUE_NUMBER`) and dispatches
`claude-dedupe-issues.yml` for any that still lack a dedupe-bot comment.

## Standalone security-audit scripts (not automated)

`scripts/analyze_apk.py`, `scripts/security_audit.py`,
`scripts/router_audit.py`, `scripts/iphone_security_checklist.py`, and the
two `*_SECURITY_GUIDE.md` files are **reference material**, not part of any
workflow. They ship with smoke tests (`tests/python/test_security_scripts_smoke.py`)
only. If you add a new standalone utility, colocate its docs and make its
unwired status explicit.

## Tests

`scripts/run-tests.sh` is the gate. It supports `--shell`, `--ts`, or
`--python` for iterating on one stage; no flags runs everything (matching
`validate.yml`). Coverage by area:

- `tests/shell/` — `gh.sh`, `comment-on-duplicates.sh`, `edit-issue-labels.sh`, `ralph-wiggum/stop-hook.sh`
- `tests/ts/` — every TS script under `scripts/`
- `tests/python/` — `examples/hooks/bash_command_validator_example.py`, security-script smoke tests, SessionStart hooks for the two output-style plugins
- `tests/validate/` — manifest consistency, `hooks.json` schemas, command-frontmatter allowed-tools, and a snapshot of the full `allowed-tools` surface at `tests/validate/baselines/allowed-tools.expected.json`
- Plugin-specific: `plugins/hookify/tests/`, `plugins/security-guidance/tests/`

If you change `scripts/gh.sh`, the frontmatter of any `.claude/commands/`
file, or a plugin's `hooks.json`, the validation tests will catch drift.
When the allowed-tools surface changes intentionally, regenerate the
baseline — do not regenerate it reflexively to make a failing test pass.
