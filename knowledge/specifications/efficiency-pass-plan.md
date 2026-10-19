---
type: Implementation Plan
title: "Plan: efficiency pass"
description: Implementation plan for the efficiency-pass spec (R1-R5).
tags: [plan, performance]
status: draft
evidence: project-documentation
generated: { by: agent/cursor, at: 2026-10-19T20:50:28Z }
sources:
  - id: ai-scripts-tests-disk-tmp-py
    resource: ../../.ai/scripts/tests/disk_tmp.py
---

# Implementation Plan: efficiency pass

## Objective

Deliver spec `knowledge/specifications/efficiency-pass.md` (R1–R5): a passing, parallel test suite; one hook run per event under Cursor; a cheap lifecycle hook for ordinary shell commands; and a smaller `AGENTS.md` with every normative rule preserved.

## Success criteria

- R1–R4: the matching `test_efficiency.py` classes (`DiskTmp`, `HookDedupe`, `HookFastPath`, `Runner`) pass and fail closed.
- R5: `test_lifecycle_conformance.py` class `AgentsBudget` passes.
- The full suite via `python3 -m unittest discover -s .ai/scripts/tests` shows no new failures (only the five pre-existing template-doc errors).

## Current state

- `scratch.require_disk` (`.ai/scripts/scratch.py`) rejects `/tmp`, `/var/tmp`, `/dev/shm`, and tmpfs. `tests/disk_tmp.py` (uncommitted, from the L1 fix) redirects `tempfile` when needed and is imported by six base test modules.
- `.cursor/hooks.json` registers `shell_guard.py` and `lifecycle.py hook`. `.claude/settings.json` registers the same two plus `autonomy_hook.py`. Cursor runs both files.
- `lifecycle.py` imports `scratch`, `brownfield`, `okf`, and `learning` at module top. `cmd_hook` resolves the repository (git) and loads state before checking whether a shell command is a commit or PR (`HOOK_COMMIT`, `HOOK_PR`).
- `shell_guard.main` reads the payload and has no arguments.
- `AGENTS.md` is 45,982 bytes. `test_lifecycle_conformance.Relocation` already enforces a 46,000-byte budget and the move of validation rules to `.ai/validation-policy.md`.

## Proposed approach

- R1: keep `tests/disk_tmp.py`; add tests.
- R2: add `--skip-in-cursor` to both scripts. It exits 0 with no output when the payload has `cursor_version` and `<project>/.cursor/hooks.json` exists. Add the flag to the two `.claude/settings.json` registrations.
- R3: in `cmd_hook`, return the allow decision for a shell event whose command matches neither `HOOK_COMMIT` nor `HOOK_PR`, before resolving the repository. Load `brownfield`, `okf`, and `learning` with `importlib.util.LazyLoader`, so they execute only on first attribute use. Every call site stays unchanged.
- R4: new `.ai/scripts/run_tests.py`. The parent discovers tests with `unittest.TestLoader` and groups them by `module.Class`; a load failure is its own group. Each group runs in a `python3 run_tests.py --worker ID` subprocess that prints a JSON result line. A thread pool of size `-j` drives the subprocesses. The runner prints a summary and the failures, and the exit status reflects the results.
- R5: move reference material out of `AGENTS.md` into a new `.ai/agents-reference.md`, loaded by section: the §3.1 command table, the §5.1 frontmatter template, and the §8.3 E2E table. Collapse §9 to its binding core plus a pointer to `.ai/autonomous-execution.md`, moving the remaining §9 sentences there if they are not already present verbatim. Replace the box-drawing gate diagram with a list. Keep every numbered heading. Add `AgentsBudget` tests: a 30,000-byte cap; preservation of normative sentences against `git show 9e13fce:AGENTS.md`, skipped when that commit is unavailable; and heading presence. Replace the 46,000 budget test.

## Boundaries and invariants

- Hook allow and deny decisions and messages stay identical. A guard error still never blocks work.
- Scripts stay stdlib-only and Python 3.9+ compatible.
- `scratch.py` stays unchanged.
- `install.py` stays unchanged. The new `.ai/` file ships through the existing `.ai/` kit entry.

## Implementation steps

### Step 1: R1 has fail-closed tests
Files: `.ai/scripts/tests/test_efficiency.py` (class `DiskTmp`). A subprocess with `TMPDIR=/tmp` imports `disk_tmp` and passes `scratch.require_disk(gettempdir())`. A subprocess with an accepted disk `TMPDIR` keeps it. Verify: `-k DiskTmp`.

### Step 2: R2, flagged hooks stand down under Cursor
Files: `.ai/scripts/shell_guard.py`, `.ai/scripts/lifecycle.py` (`cmd_hook`, parser), `.claude/settings.json`, tests `HookDedupe`. Verify: `-k HookDedupe`, `test_shell_guard.py`, `test_lifecycle_conformance.py -k HarnessWiring`, `test_install.py`.

### Step 3: R3, the shell fast path and lazy imports
Files: `.ai/scripts/lifecycle.py`, tests `HookFastPath` (`-X importtime` check, and a commit is still denied without a tier). Verify: `-k HookFastPath`, `test_lifecycle.py`, `test_brownfield_deltas.py`, `test_learning_loop.py`.

### Step 4: R4, the parallel runner
Files: `.ai/scripts/run_tests.py`, tests `Runner`, which use a fixture test directory with a pass, a failure, an error, a skip, and an import error. Verify: `-k Runner`, then `python3 .ai/scripts/run_tests.py` on the real suite, with the count compared to discover.

### Step 5: R5, `AGENTS.md` under budget with rules preserved
Files: `AGENTS.md`, `.ai/agents-reference.md`, `.ai/autonomous-execution.md` (only for moved §9 sentences), `test_lifecycle_conformance.py` (`AgentsBudget` replaces the budget test). Verify: `test_lifecycle_conformance.py`, plus `okf.py show` resolution through `test_every_documented_okf_show_command_resolves`.

## Testing strategy

Write each requirement's test first and see it fail (red) against the current code, then implement. Existing suites guard against regressions in hook decisions, the installer, and the lifecycle.

## Validation commands

- Focused checks per step, as listed above.
- Converge: `python3 .ai/scripts/lifecycle.py converge knowledge/specifications/efficiency-pass.md`.
- Full gate, once on the frozen candidate: `python3 -m unittest discover -s .ai/scripts/tests` (the reference) and `python3 .ai/scripts/run_tests.py` (same count, faster). Then `python3 .ai/scripts/okf.py records`.

## OKF impact

- `knowledge/playbooks/run-script-tests.md`: how to run the suite (the runner, `-j`, the disk temp behavior).
- `knowledge/project/` hook-wiring note covering the Cursor dual-load and `--skip-in-cursor`.
- A `knowledge/log.md` entry for each.
- Set the spec status to stable once the change is verified.

## Risks and mitigations

- **Cursor omits `cursor_version` for `.claude` hooks:** the flagged hooks then run as before. Duplicate work returns, but no enforcement is lost.
- **`LazyLoader` and `mock.patch` interplay in tests:** patching triggers the load. The existing lifecycle suites cover this.
- **Hidden order dependence between test classes:** both the serial and the parallel reference runs are part of the full gate.
- **`AGENTS.md` citations:** headings and § numbers stay, and the show-command test resolves every documented `okf.py show`.

## Out of scope

The items listed as non-goals in the spec.

## Open decisions

None. The plan is ready for implementation.
