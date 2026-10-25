---
type: Capability
title: Worktree-aware lifecycle enforcement
description: Select lifecycle and audit state from the guarded operation worktree
tags: [lifecycle, hooks]
status: stable
evidence: validated-runtime
generated: { by: agent/unknown, at: 2026-10-25T18:40:49Z }
sources:
  - id: ai-scripts-lifecycle-py
    resource: ../../.ai/scripts/lifecycle.py
  - id: ai-scripts-tests-test-worktree-hooks-py
    resource: ../../.ai/scripts/tests/test_worktree_hooks.py
verified: { by: "process:python3 .ai/scripts/lifecycle.py reuse worktree-hook-full-suite", at: 2026-10-25T18:52:40Z }
---

# Worktree-aware lifecycle enforcement

Select lifecycle and audit state from the guarded operation worktree

## Contract

Guarded operations select structured tool workdir before event cwd, then legacy
session hints. Relative workdir resolves from the operation context, and relative
source paths resolve from the execution directory. The selected Git root supplies
branch lifecycle state and audit-record inclusion checks. An invalid explicit
directory denies a guarded operation rather than falling back to an eligible
outer checkout. SessionStart keeps its established project-context selection.

A directly invoked `git -C WORKTREE commit` declares the Git execution directory,
including when a Codex adapter forwards only command text and session cwd. The
hook resolves this bounded argv form without shell evaluation and keeps existing
Verify, retrospective, red/green and audit-inclusion requirements. Cross-worktree
readiness cannot authorize an unready target. Shell cd grammar is not inferred.

## Evidence

Public JSON tests create actual linked Git worktrees with opposing lifecycle
states. They test commit, PR and source edit decisions, relative paths, invalid
locations, fallback compatibility, startup context, and an actual disposable
commit with its audit record. Command outcomes are recorded in the task log and
audit record; test existence alone is not a runtime claim.
