# Security Guidance Plugin

A Claude Code plugin that provides security reminders when editing files. It monitors for common vulnerability patterns and warns before potentially insecure code is written.

## Hook

- **PreToolUse** — Monitors `Edit`, `Write`, and `MultiEdit` tool calls for 9 security patterns:
  - GitHub Actions workflow injection
  - `child_process.exec` command injection
  - `new Function()` code injection
  - `eval()` usage
  - `dangerouslySetInnerHTML` XSS
  - `document.write()` XSS
  - `.innerHTML =` XSS
  - `pickle` deserialization
  - `os.system` injection

## Behavior

- Warnings are shown once per file-pattern combination per session.
- The hook uses exit code 2 to block the tool call and surface the warning to Claude.
- Set `ENABLE_SECURITY_REMINDER=0` to disable.

## Installation

This plugin is included in the Claude Code repository. Install it via the `/plugin` command or configure it in your project's `.claude/settings.json`.
