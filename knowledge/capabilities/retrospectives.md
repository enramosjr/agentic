---
type: Capability
title: Task retrospectives and advisory observations
description: Evidence-backed closure and bounded retrieval across repository tasks
tags: [lifecycle, learning]
status: stable
evidence: validated-runtime
generated: { by: agent/unknown, at: 2026-10-25T18:01:38Z }
sources:
  - resource: ../../.ai/scripts/learning.py
  - resource: ../../.ai/scripts/lifecycle.py
  - resource: ../../.ai/scripts/tests/test_retrospectives.py
  - resource: ../../.ai/scripts/tests/test_learning_loop.py
  - resource: ../../.ai/scripts/tests/test_lifecycle.py
  - resource: ../../.ai/scripts/tests/test_lifecycle_eval.py
  - resource: ../../.ai/scripts/tests/test_ledger.py
  - resource: ../../.ai/scripts/tests/test_scan_diff.py
  - resource: ../../.ai/scripts/tests/test_sync_check.py
  - resource: ../../.ai/scripts/tests/test_brownfield_deltas.py
  - resource: ../../.ai/scripts/tests/pressure_agent.py
  - resource: ../../.ai/evals/checks/retrospective.py
  - resource: ../../.ai/evals/checks/retrospective.json
  - resource: ../../.ai/evals/lifecycle/17-retrospective-reuse.json
verified: { by: "process:python3 .ai/scripts/lifecycle.py reuse worktree-hook-full-suite", at: 2026-10-25T18:52:40Z }
---

# Task retrospectives and advisory observations

Evidence-backed closure and bounded retrieval across repository tasks

## Completion contract

L1–L3 Verify and delivery gates require an explicit retrospective. `retrospect
--lessons 1 2` selects existing evidence-backed observations; `retrospect
--no-new-lessons REASON` records an explicit explanation. Capture with `learn`
alone cannot satisfy closure. L0 is exempt. Closure is validated and persisted
with the lifecycle JSON audit record; identical retries preserve its timestamp,
and reconciliation rejects conflicting published outcomes. Legacy absent closure
remains audit-valid but does not authorize a newly attempted completion gate.

## Advisory recall

`observations --query TEXT`, task declarations and SessionStart retrieve lifecycle
observations with evidence and source references. Case-insensitive token overlap
ranks before recency and stable identity. No matches use a labeled recent
fallback. Up to five complete entries fit in an 8,192-byte UTF-8 block; omitted
entries and corrupt history produce diagnostics. Approved rules retain a separate
budget and remain available when observation records are malformed. Recall does
not promote observations or grant instruction precedence.

## Verification surface

The retrospective acceptance tests drive public commands, actual installation,
gates, recovery, bounded retrieval and rule authority. The retrospective-reuse
lifecycle evaluation uses a frozen checker to inspect a real agent's durable
closure and saved retrieval output. Execution outcomes are recorded in the log;
the existence of these checks alone does not establish a passing run.
