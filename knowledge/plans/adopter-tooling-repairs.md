---
type: Plan
title: Adopter repair implementation plan
description: Port only documented repairs and protect lifecycle command evidence.
tags: [tooling, plan]
status: draft
evidence: project-documentation
generated: { by: agent/unknown, at: 2026-10-19T22:06:21Z }
---

# Adopter repair implementation plan

## Scope

Follow the user-authorized fixes-only scope in
[the spec](../specifications/adopter-tooling-repairs.md). No repository replacement.

## Steps and checks

1. R1, R2, R3, R4: Port only the existing five repaired test files first. Record
   RED for installed-template reuse, missing distributed references and nested
   bytecode. Then port the installer, runner, README, four distributed references
   and the AGENTS introduction (without wrapper markers). Check focused GREEN.
2. R5: Add failing real-CLI ledger regressions before implementation. Use an
   inherited JSON stack of resolved repository roots: run appends its root;
   lifecycle dispatch refuses mutating commands in an owned ancestor root before
   their bodies. Allow read-only commands and merge --dry-run. Preserve the stack
   through independent repository runs. Do not statically classify arbitrary argv
   or claim a security sandbox. Check prior state and side-effect preservation.
3. R1-R6: Refresh root README/lifecycle references to the new distributed docs.
   Sync only upstream-local OKF records, preserving .gitignore. Execute focused
   regressions and the complete source suite once on the final candidate through
   direct convergence. Run connected installed tests through that suite, verify
   exact repair diff scope and run records/sync-check.
4. R6, R7: Save independent two-pass review, record Verify, explicitly stage only
   repair paths and minimal task-specific records/audit. Commit, push branch,
   open and attach the authorized upstream PR. Never merge it.

## Evidence and boundaries

The original validated overlay is in Athenaeum commit 24e3b3c. Target base is
AGENTIC 16d9d99; work occurs in an isolated disk-backed checkout with full history,
so its upstream-history budget tests run. No adopter manifest or history is ported.
The additional lifecycle guard follows the planner's repository-scoped descendant
option, including indirect CLI calls, instead of incomplete argv matching.

## Open decisions

None.
