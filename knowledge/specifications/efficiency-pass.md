---
type: Specification
title: "Efficiency pass: faster tests and hooks, smaller always-loaded instructions"
description: "Cut test wall time, duplicate and slow hook work, and AGENTS.md cold-start tokens without weakening any check or rule."
tags: [spec, performance, tokens]
status: stable
evidence: project-documentation
generated: { by: agent/cursor, at: 2026-10-19T20:50:06Z }
sources:
  - id: agents-md
    resource: ../../AGENTS.md
  - id: ai-scripts-lifecycle-py
    resource: ../../.ai/scripts/lifecycle.py
  - id: ai-scripts-shell-guard-py
    resource: ../../.ai/scripts/shell_guard.py
  - id: claude-settings-json
    resource: ../../.claude/settings.json
verified: { by: "process:python3 -m unittest discover -s .ai/scripts/tests -p test_[ea]*.py", at: 2026-10-19T21:19:16Z }
---

# Spec: Efficiency pass: faster tests and hooks, smaller always-loaded instructions

## Problem and outcome

Measured on 2026-10-19 (Linux, 32 cores, `/tmp` on tmpfs):

- The script test suite fails 202 tests because fixtures land in `/tmp`, which `scratch.py` rejects. With a disk `TMPDIR` it takes 182 s, run serially.
- Cursor runs hooks from both `.cursor/hooks.json` and `.claude/settings.json` (third-party hooks are on by default), so every shell command runs the shell guard and the lifecycle hook twice and the session-start router is injected twice.
- `lifecycle.py hook` takes about 65 ms per shell command, about half of it importing `okf`, `brownfield`, and `learning`, which a non-commit command never needs.
- `AGENTS.md` (45,982 bytes, about 11k tokens) is loaded into every session; about 15 KB of it is reference material (command tables, autonomous-mode detail, a box-drawing diagram).

When this ships, the suite passes on a tmpfs `/tmp`, runs in parallel, each hook runs once per event under Cursor, ordinary shell commands skip the heavy imports, and `AGENTS.md` is under 30,000 bytes with every normative rule preserved.

## Users and scenarios

- Agents and humans running the script test suite locally (Gate 4 for `.ai/scripts/**`).
- Agents in Cursor, Claude Code, and Codex, whose every shell command and edit passes through the hooks.
- Every agent session, which loads `AGENTS.md` at start; adopters receive the same files through `install.py`.

## Requirements

- R1: When `scratch.require_disk` rejects the system temporary directory, test fixtures MUST be created on a disk-backed directory outside any git repository; when it accepts it, the temporary directory MUST be left unchanged.
- R2: `shell_guard.py` and `lifecycle.py hook` invoked with `--skip-in-cursor` MUST exit 0 with no output when the event payload contains `cursor_version` and the project has `.cursor/hooks.json`, and MUST decide exactly as without the flag otherwise. `.claude/settings.json` MUST pass that flag to both scripts; `.cursor/hooks.json` and `.codex/hooks.json` MUST keep their current registrations.
- R3: `lifecycle.py hook` for a shell command that is neither a `git commit` nor a `gh pr create|ready` MUST return its allow decision without importing `okf`, `brownfield`, or `learning`; all other hook decisions MUST be unchanged.
- R4: `python3 .ai/scripts/run_tests.py [-j N] [-s DIR]` MUST run every test that `python3 -m unittest discover -s DIR` runs (default `.ai/scripts/tests`), split by test class across at most N worker processes (default: CPU count), print the total count and each failing or erroring test id with its output, and exit 0 only when no test failed or errored.
- R5: `AGENTS.md` MUST be under 30,000 bytes; every sentence in the previous `AGENTS.md` that contains MUST, MUST NOT, SHOULD, SHOULD NOT, or MAY MUST appear verbatim in `AGENTS.md` or in a `.ai/` document that `AGENTS.md` links; every numbered section heading (§1–§9, Gates 1–4) MUST remain in `AGENTS.md` so existing citations resolve.

## Acceptance

- R1: `python3 -m unittest discover -s .ai/scripts/tests -p test_efficiency.py -k DiskTmp` passes; it fails if a fixture temp directory under the redirect is rejected by `scratch.require_disk` or if an accepted temp directory is changed.
- R2: `python3 -m unittest discover -s .ai/scripts/tests -p test_efficiency.py -k HookDedupe` passes; it fails if a flagged hook prints or blocks under a Cursor payload with `.cursor/hooks.json` present, if it skips a Claude Code payload or a project without `.cursor/hooks.json`, or if `.claude/settings.json` lacks the flag.
- R3: `python3 -m unittest discover -s .ai/scripts/tests -p test_efficiency.py -k HookFastPath` passes; it fails if `python3 -X importtime .ai/scripts/lifecycle.py hook` imports `okf`, `brownfield`, or `learning` for a non-commit shell payload, or if a commit is no longer gated.
- R4: `python3 -m unittest discover -s .ai/scripts/tests -p test_efficiency.py -k Runner` passes; it fails if the runner's count differs from `unittest discover` on a fixture directory, if a failing or erroring test is not named, or if the exit status is 0 with a failure.
- R5: `python3 -m unittest discover -s .ai/scripts/tests -p test_lifecycle_conformance.py -k AgentsBudget` passes; it fails if `AGENTS.md` is 30,000 bytes or larger, if a normative sentence of `AGENTS.md` at commit 9e13fce is missing from `AGENTS.md` and its linked `.ai/` documents, or if a numbered section heading is gone.

## Constraints

- Scripts stay stdlib-only and Python 3.9+ compatible.
- No hook decision changes for any harness: the same commands are allowed and denied with the same messages.
- `scratch.py`'s refusal of system temporary storage stays as is.
- `python3 -m unittest discover -s .ai/scripts/tests` keeps working unchanged as the reference command.
- Installer behavior (`install.py`) is unchanged; moved `AGENTS.md` content lives under `.ai/`, which the installer already ships.

## Non-goals

- Rewriting or speeding up individual slow tests (for example the 6 s heartbeat tests).
- Changing which checks the governance requires, or any rule's wording beyond moving it.
- Fixing the five documentation tests that need template-only `knowledge/` documents.

## Assumptions

- Cursor sends `cursor_version` in every hook payload, including hooks loaded from `.claude/settings.json` (Cursor Hooks docs, "Common schema"). If it does not, the flagged hooks run as before: duplicate work, but no lost enforcement.
- Test classes are independent of each other; module-level and class-level parallel runs on 2026-10-19 passed with the same results as the serial run.

## Open questions

None. The spec is ready for planning.
