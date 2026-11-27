# ADR 0010: Structured repository tools over raw shell

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §15.3](../0001-agentic.md#153-shell-guard)

## Context

Agents habitually explore with `cat`, `grep -r`, `find` and `ls -R`, and edit
with heredocs or `sed -i`. Unbounded output inflates context, and every later
turn re-sends it. Shell edits bypass the edit hooks that enforce the lifecycle
([ADR 0001](0001-enforce-lifecycle-with-hooks.md)). Acceptance commands that
touch the user's live display or input devices are nondeterministic and
intrusive.

## Decision

- `shell_guard.py` runs before every shell command in every harness. It rejects
  file reads, listings, searches and writes done through the shell (`ls`,
  `find`, `tree`, `cat`, `head`, `tail`, `sed`, `awk`, `grep`, `rg`,
  `git ls-files`, `git grep`, heredocs, `echo >`), and any shell read of
  `knowledge/` or `.ai/**.md`.
- Each rejection names the replacement: harness `Read`/`Edit`/`Write`,
  `repo.py read|grep|files` (bounded, `.gitignore`-aware, binary-skipping), or
  `okf.py show|search`.
- It rejects live display selectors (`DISPLAY=:0`/`:1`, `WAYLAND_DISPLAY`).
- Rephrasing a command to evade the guard is prohibited. Only a human may
  disable the guard (`OKF_SHELL_GUARD=off`).
- Documents are loaded by outline and section, never whole.

## Consequences

- Smaller, bounded context and fewer turns, which directly reduces cost
  ([ADR 0011](0011-supervised-autonomy-driver.md) §context economy).
- Edits flow through tools that the lifecycle hook can see.
- Some legitimate one-off shell use is refused and must use the replacement.
  Piping a command's output through `head` or `tail` is still allowed.
- The guard recognizes literal command patterns, so it is not a sandbox
  against deliberate evasion.

## Alternatives considered

- **Advisory guidance only.** Rejected because agents revert to habit.
- **Blocking the shell entirely.** Rejected because builds, tests, Git and
  scripts need it.

## Evidence

`.ai/scripts/shell_guard.py`, `.ai/scripts/repo.py`, `.ai/agents-reference.md` §Harness tools,
`AGENTS.md` §3.1, `.ai/scripts/tests/test_shell_guard*.py`.

## Revisit when

Harnesses provide bounded native read and search tools universally, including
Codex.
