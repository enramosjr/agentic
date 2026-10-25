---
type: Plan
title: Worktree hook routing plan
description: "Test execution-directory routing, repair the active hook, and commit verified work"
tags: [plan]
status: draft
evidence: project-documentation
generated: { by: agent/unknown, at: 2026-10-25T18:36:40Z }
verified: { by: "process:python3 .ai/scripts/lifecycle.py reuse worktree-hook-full-suite", at: 2026-10-25T18:52:40Z }
---

# Worktree hook routing plan

## Steps

Requirement coverage: R1, R2, R3, R4, R5, R6, R7.

1. R1–R7: Write public-hook regressions in `.ai/scripts/tests/test_worktree_hooks.py` using real Git worktrees with conflicting state. Record red for the workdir regression before changing production code. Assert both allow and deny directions, audit staging, relative directories/edits, invalid explicit directories, old fallbacks and SessionStart compatibility. Acceptance: the seven named spec tests.
2. R1–R6: Add a bounded context resolver in `.ai/scripts/lifecycle.py`. Guarded operations prefer structured tool workdir, then payload cwd, then legacy hints. Preserve SessionStart routing and shell fast paths. Resolve relative edit paths against effective execution directory. Deny known invalid directory input explicitly. Record green for the same reproduction; no arbitrary shell parsing or guard bypass.
3. R1–R7: Synchronize the capability/playbook and log; run current convergence, full framework suite and a real-agent lifecycle evaluation on the frozen combined candidate. Independent review must approve the routing change and retained retrospective behavior. Close this task's own retrospective and Verify.
4. R7: Preserve original lifecycle.py and main SHA. Temporarily apply the same tested routing correction to the active outer hook, with intent/plan recorded there. Exercise the actual tool path, stage all candidate and lifecycle/OKF records, and commit on codex/required-retrospectives-impl. Immediately restore the original hook contents. Assert original main SHA unchanged, original tracked tree clean, and isolated worktree clean with the intended commit.

## Decisions

Live hook reproduction showed Codex drops tool workdir from its Bash event and
forwards only command text with session cwd. R1, R5 and R7 additionally cover a
direct `git -C WORKTREE commit` command, resolving that explicit Git location
without shell evaluation. The final hook-mediated commit will use this declared
target so Git and the guard select the same worktree.

User authorization covers this fix and the final commit. The original hook update
is a temporary bootstrap, not a separate default-branch change. No open decisions
remain. Existing staged retrospective changes and audit records are preserved.
