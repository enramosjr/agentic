---
type: Review Report
title: "Review: efficiency pass"
description: Independent reviewer findings and verdict for the efficiency-pass change (R1-R5).
tags: [review]
status: stable
evidence: project-documentation
generated: { by: agent/cursor, at: 2026-10-19T21:03:30Z }
sources:
  - id: ai-scripts-tests-test-efficiency-py
    resource: ../../.ai/scripts/tests/test_efficiency.py
---

# Review: efficiency pass

Independent reviewer findings and verdict for the efficiency-pass change (R1-R5).

Reviewer: `reviewer` subagent (read-only), persona Python principal engineer. Two rounds.

## Findings

1. **Medium (fixed):** the R3 fast-path test passed with the fast path deleted. `-X importtime` does not report `LazyLoader` execution, and an empty fixture never reaches `learning`. Fix: `HookFastPath.test_an_active_task_does_not_load_heavy_modules_for_ordinary_commands` sets up an active task with an audit record and asserts `okf`, `brownfield`, `learning` stay `_LazyModule` after an in-process hook call. With the fast path disabled it fails (learning becomes `module`); restored, it passes.
2. **Low (deferred):** `--skip-in-cursor` checks only that `.cursor/hooks.json` exists, not that it registers the same guard. The installer restores kit entries; hardening would change approved R2 wording.
3. **Low (fixed):** `project/harness-hooks.md` claimed `validated-runtime`; now `implementation-and-current-specifications` with the `cursor_version` assumption stated.
4. **Low (deferred):** `AgentsBudget` preservation checks skip when commit `9e13fce` is absent (shallow clone or installed adopter).
5. **Low (deferred):** `run_tests.py` loads by `module.Class`, which bypasses a module-level `load_tests` and repeats `setUpModule` per class; the current suite has neither.
6. **Low (fixed):** the playbook states the test cache directory is assumed to be outside any git work tree.
7. **Low (deferred):** `AGENTS.md` pointers say "section `X`" relying on the convention stated once near the top; 129 bytes of budget headroom remain.
8. **Low (fixed, round 2):** the new probe did not strip `LIFECYCLE_GUARD` / `OKF_AUTONOMOUS` / `OKF_SHELL_GUARD`; it now uses the same filtered environment as `run_script`.

## Validation Reviewed

- `python3 .ai/scripts/lifecycle.py converge knowledge/specifications/efficiency-pass.md`: R1–R5 PASS, 0 MANUAL.
- Red evidence: R2–R4 tests failed before implementation; `HookDedupe`/`HookFastPath` failed against the stashed previous scripts; `AgentsBudget` failed at 45,982 bytes; the preservation test fails when one MUST sentence is removed; R1 fails with `XDG_CACHE_HOME=/tmp/xdg`; the active-task fast-path test fails with the fast path disabled.
- Pass 1: R1–R5 present, nothing extra beyond non-normative notes about `run_tests.py`; hook decisions unchanged; `install.py` and `scratch.py` untouched.
- Pass 2: no Critical or High findings. Claude Code payloads carry no `cursor_version`, so the skip cannot fire there.

## Verdict

Approved
