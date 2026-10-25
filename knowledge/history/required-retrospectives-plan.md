---
type: Plan
title: Required retrospective implementation plan
description: "Implement approved R1–R7 with test-first validation"
tags: [plan]
status: draft
evidence: project-documentation
generated: { by: agent/unknown, at: 2026-10-25T17:53:18Z }
verified: { by: "process:python3 .ai/scripts/lifecycle.py reuse retrospective-full-suite-final", at: 2026-10-25T18:18:16Z }
---

# Required retrospective implementation plan

## Steps

1. R1, R2, R3, R6: Write failing retrospective CLI/gate/persistence/compatibility tests in `.ai/scripts/tests/test_retrospectives.py`. Extend `.ai/scripts/learning.py` with closure validation/reconciliation and `.ai/scripts/lifecycle.py` with `retrospect --lessons N...` or `retrospect --no-new-lessons REASON`. Require closure independently at Verify, commit and ship; legacy absence remains audit-valid. Validate with the spec's R1–R3 and R6 tests.
2. R4, R5: Write failing retrieval/authority tests. Add read-only `observations [--query TEXT]`, bounded advisory rendering and startup/tier context. Match case-insensitive tokens against lesson/evidence, rank by overlap then recency and reference, and use recent fallback. Preserve approved rule injection when historical observations are malformed. Validate R4–R5 acceptance.
3. R7: Update lifecycle, implementer/reviewer/orchestrator and skill guidance plus learning docs and supported existing router hooks. Add installed CLI coverage and update old fixture workflows to explicitly close retrospectives rather than bypass gates. Validate R7 acceptance and focused existing learning/lifecycle tests.
4. R1–R7: Synchronize OKF capability/playbook/spec and evidence log. Run all acceptance tests once via converge, independent review, full script suite once on the frozen candidate, and a real-agent lifecycle evaluation. Record Verify only after this task's own evidence-backed retrospective. Deliver the isolated branch with exact outcomes.

## Decisions

No new closing hook event is required: existing SessionStart and delivery guards route the workflow. Historical records remain immutable. Closing metadata is stored alongside observations in the audit JSON; no second store. No open decisions remain.
