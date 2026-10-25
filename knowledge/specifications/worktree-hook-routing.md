---
type: Specification
title: Lifecycle hook worktree routing
description: Enforce lifecycle gates in the operation execution worktree
tags: [lifecycle, spec]
status: stable
evidence: project-documentation
generated: { by: agent/unknown, at: 2026-10-25T18:35:15Z }
sources:
  - id: ai-scripts-lifecycle-py
    resource: ../../.ai/scripts/lifecycle.py
verified: { by: "process:python3 .ai/scripts/lifecycle.py reuse worktree-hook-full-suite", at: 2026-10-25T18:52:40Z }
---

# Lifecycle hook worktree routing

## Problem and outcome

The hook ignores the tool execution workdir and prefers session project hints to
payload cwd. A commit in the verified isolated worktree was blocked using the
original checkout's lifecycle state. A live diagnostic also confirmed the Codex
adapter forwards command text without the tool workdir. Enforce gates where the
operation executes, including an explicit Git -C target in that event shape.

## Requirements

- R1: Guarded tool operations MUST use explicit tool_input.workdir before session project hints, and Git commit checks MUST honor an explicit Git -C directory relative to that execution context. This MUST also work when the adapter forwards only command text and session cwd.
- R2: Without tool workdir, operation cwd MUST precede project environment and workspace hints, which remain fallbacks before process cwd.
- R3: Relative workdirs MUST resolve against operation context; relative edit paths MUST resolve against the selected execution directory.
- R4: Commit, PR and source edit decisions MUST use the selected worktree state and audit record. Ready targets MUST proceed despite unready outer checkouts, and unready targets MUST be denied despite ready outer checkouts.
- R5: Invalid explicit workdirs or Git -C directories MUST deny guarded operations with actionable diagnostics instead of falling back or reaching the generic fail-open exception handler.
- R6: SessionStart MUST preserve existing project-context selection and emission, independently of tool-operation workdir overrides.
- R7: The supported outer hook entry point MUST enforce worktree routing through public JSON events and permit a real disposable commit only when the target audit is ready and staged. Hook output formats and event normalization MUST remain compatible.

## Acceptance

- R1: `python3 .ai/scripts/tests/test_worktree_hooks.py WorktreeHookTests.test_tool_workdir_overrides_session_project` passes.
- R2: `python3 .ai/scripts/tests/test_worktree_hooks.py WorktreeHookTests.test_cwd_precedence_and_legacy_fallbacks` passes.
- R3: `python3 .ai/scripts/tests/test_worktree_hooks.py WorktreeHookTests.test_relative_workdir_and_edit_paths` passes.
- R4: `python3 .ai/scripts/tests/test_worktree_hooks.py WorktreeHookTests.test_commit_pr_and_edit_use_target_state` passes.
- R5: `python3 .ai/scripts/tests/test_worktree_hooks.py WorktreeHookTests.test_invalid_explicit_workdir_denies_guarded_operation` passes.
- R6: `python3 .ai/scripts/tests/test_worktree_hooks.py WorktreeHookTests.test_session_start_preserves_project_context` passes.
- R7: `python3 .ai/scripts/tests/test_worktree_hooks.py WorktreeHookTests.test_outer_hook_entrypoint_routes_to_target_worktree` passes.

## Constraints

Preserve the staged retrospective changes, lifecycle gates, stdlib-only tooling
and human approval requirements. Use real Git worktrees with conflicting states
for regression coverage. The user authorized fixing the active outer hook and
committing verified changes. Any temporary bootstrap correction in the original
checkout must be narrowly scoped, tested, and restored after delivery; its main
SHA must remain 886392ce512c8ff6f1eb24a94833ab1fc57e25dc.

## Non-goals

Parsing arbitrary shell cd commands, shell grammar, or redesigning registrations.
Git -C handling is bounded to a directly invoked Git command, not shell evaluation.

## Assumptions

The effective worktree follows structured execution-directory fields when present
and a directly invoked Git -C target when supplied. Explicit relative workdir is
relative to payload cwd. Unsupported shell directory overrides remain outside this
bounded change. SessionStart keeps its prior hints.
The final real commit includes both the verified retrospective implementation and
this routing correction, without pushing or merging into the default branch.

## Open questions

None. The spec is ready for planning.
