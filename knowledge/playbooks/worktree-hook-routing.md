---
type: Playbook
title: Lifecycle hooks across worktrees
description: "Execution context, adapter limitations and verified worktree delivery"
tags: [lifecycle, hooks]
status: stable
evidence: project-documentation
generated: { by: agent/unknown, at: 2026-10-25T18:40:49Z }
sources:
  - id: ai-scripts-lifecycle-py
    resource: ../../.ai/scripts/lifecycle.py
  - id: ai-docs-lifecycle-md
    resource: ../../.ai/docs/lifecycle.md
verified: { by: "process:python3 .ai/scripts/lifecycle.py reuse worktree-hook-full-suite", at: 2026-10-25T18:52:40Z }
---

# Lifecycle hooks across worktrees

Execution context, adapter limitations and verified worktree delivery

## Selecting the target

Provide structured `workdir` when the harness preserves it. Otherwise event cwd
selects the operation context before session hints. For adapters that omit the
tool workdir, use a direct `git -C WORKTREE commit`; the explicit Git target is
the context both the process and lifecycle guard use. Do not disable guards or
mark another checkout verified to authorize the target.

Relative workdirs use the event context, and relative edit paths use the selected
execution directory. SessionStart remains attached to its session project. Fix
invalid explicit paths when the hook denies them instead of silently falling back.

## Active-hook upgrade

When the currently installed outer hook predates worktree routing, apply only the
same tested routing correction temporarily after recording the authorized intent
and plan there. Verify the target normally, stage its audit record, and perform
the hook-mediated commit with an explicit target. Restore the original outer-hook
contents after delivery and confirm the original default branch SHA is unchanged.
The durable correction belongs in the reviewed implementation branch.
