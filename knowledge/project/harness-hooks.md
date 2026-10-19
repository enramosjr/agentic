---
type: Architecture
title: Harness hook wiring
description: "Which hook files each harness loads, and how the shell and lifecycle guards run once per event under Cursor."
tags: [hooks, architecture]
status: stable
evidence: implementation-and-current-specifications
generated: { by: agent/cursor, at: 2026-10-19T20:57:01Z }
sources:
  - id: claude-settings-json
    resource: ../../.claude/settings.json
  - id: cursor-hooks-json
    resource: ../../.cursor/hooks.json
  - id: codex-hooks-json
    resource: ../../.codex/hooks.json
  - id: ai-scripts-shell-guard-py
    resource: ../../.ai/scripts/shell_guard.py
  - id: ai-scripts-lifecycle-py
    resource: ../../.ai/scripts/lifecycle.py
verified: { by: "process:python3 -m unittest discover -s .ai/scripts/tests -p test_[ea]*.py", at: 2026-10-19T21:19:16Z }
---

# Harness hook wiring

Which hook files each harness loads, and how the shell and lifecycle guards run once per event under Cursor.

## Registrations

| Harness | Loads | Guards |
|---------|-------|--------|
| Claude Code | `.claude/settings.json` | `shell_guard.py --skip-in-cursor` and `lifecycle.py hook --skip-in-cursor` on `Bash`; `lifecycle.py hook --skip-in-cursor` on edits and `SessionStart`; `autonomy_hook.py` on `SessionStart` and `Stop` |
| Cursor | `.cursor/hooks.json` and, with the default "Include Third-Party Plugins, Skills, and Other Configs" setting, `.claude/settings.json` too | `shell_guard.py` and `lifecycle.py hook` on `beforeShellExecution`; `lifecycle.py hook` on `preToolUse` (`Write\|Delete`) and `sessionStart` |
| Codex | `.codex/hooks.json` (trusted layer only) | `shell_guard.py` and `lifecycle.py hook` on `Bash`; `lifecycle.py hook` on edits and `SessionStart` |

Cursor runs every matching hook from every source, so before 2026-10-19 each shell command ran both guards twice and the session-start router was injected twice.

## `--skip-in-cursor`

With the flag, `shell_guard.py` and `lifecycle.py hook` exit 0 with no output when the event payload has `cursor_version` and the project root (`CLAUDE_PROJECT_DIR`, else the first workspace root, else `cwd`) has `.cursor/hooks.json`. Then the `.cursor/hooks.json` entry makes the same decision. Claude Code payloads have no `cursor_version`, so the flag never changes a Claude Code decision. If Cursor ever omits `cursor_version`, the flagged hooks run as before (duplicate work, no lost enforcement). `autonomy_hook.py` is registered only in `.claude/settings.json` and carries no flag.

## Lifecycle hook fast path

`lifecycle.py hook` allows a shell command that is neither `git commit` (`HOOK_COMMIT`) nor `gh pr create|ready` (`HOOK_PR`) before resolving the repository, and `brownfield`, `okf` and `learning` load lazily (`importlib.util.LazyLoader`). An ordinary shell command never imports them.

Verified: `python3 -m unittest discover -s .ai/scripts/tests -p test_efficiency.py -k HookDedupe -k HookFastPath` passes (6 tests) and fails against the previous scripts.
