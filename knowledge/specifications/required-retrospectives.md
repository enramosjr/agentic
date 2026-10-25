---
type: Specification
title: Required retrospectives
description: Required closure and advisory reuse of project lessons
tags: [spec]
status: stable
evidence: project-documentation
generated: { by: agent/unknown, at: 2026-10-25T17:50:47Z }
sources:
  - id: ai-scripts-lifecycle-py
    resource: ../../.ai/scripts/lifecycle.py
  - id: ai-scripts-learning-py
    resource: ../../.ai/scripts/learning.py
verified: { by: "process:python3 .ai/scripts/lifecycle.py reuse worktree-hook-full-suite", at: 2026-10-25T18:52:40Z }
---

# Required retrospectives

## Problem and outcome

Optional lesson capture permits tasks to finish without reflection or reuse. Require
explicit closure and expose attributable observations to later repository tasks.

## Requirements

- R1: L1–L3 tasks MUST record a closing retrospective before Verify and delivery gates. Closure MUST select evidence-backed observations or no new lessons with a nonblank reason. L0 MUST remain exempt; learn alone MUST NOT close a retrospective.
- R2: Observation closure MUST reference existing active-task lessons with nonblank evidence. Invalid closure MUST fail without publishing success. Evidence MUST remain inert text.
- R3: Closure outcome, timestamp and lesson numbers MUST persist in the lifecycle audit record. Retries and stale-state recovery MUST preserve compatible data and reject conflicting closure.
- R4: Later task declarations and SessionStart MUST surface deterministic advisory observations with evidence and source references. Query or task-reason token overlap MUST rank results before recency and stable reference; absent matches MUST use a labeled recent fallback. Retrieval MUST be read-only and limited to five whole entries within 8,192 UTF-8 bytes.
- R5: Retrieved observations MUST remain advisory and MUST NOT change rule approval, retirement, or instruction precedence.
- R6: Legacy records without closure MUST remain auditable with stable lesson identities. Newly verifying or delivering an active legacy task MUST require closure. Malformed present closure MUST fail validation. Malformed historical records MUST yield attributable diagnostics while valid rules remain available.
- R7: Lifecycle, role, skill and harness guidance MUST instruct agents to close retrospectives and report the outcome. Missing closure MUST give executable guidance. Public CLI and installed-artifact tests MUST exercise closure and later retrieval.

## Acceptance

- R1: `python3 .ai/scripts/tests/test_retrospectives.py RetrospectiveTests.test_required_gate` passes.
- R2: `python3 .ai/scripts/tests/test_retrospectives.py RetrospectiveTests.test_evidence` passes.
- R3: `python3 .ai/scripts/tests/test_retrospectives.py RetrospectiveTests.test_durability` passes.
- R4: `python3 .ai/scripts/tests/test_retrospectives.py RetrospectiveTests.test_retrieval` passes.
- R5: `python3 .ai/scripts/tests/test_retrospectives.py RetrospectiveTests.test_authority` passes.
- R6: `python3 .ai/scripts/tests/test_retrospectives.py RetrospectiveTests.test_compatibility` passes.
- R7: `python3 .ai/scripts/tests/test_retrospectives.py RetrospectiveTests.test_installed_flow` passes.

## Constraints

Reuse stdlib-only lifecycle records and preserve stage order, verification gates,
stable lesson references, and explicit human approval for binding rules.

## Non-goals

Cross-project memory, conversation imports, automatic rule promotion, semantic
search, dashboards, and fabricated lessons.

## Assumptions

Closure precedes Verify so it is included in the committed audit record. Existing
evidence-free observations remain valid but cannot support new observation closure.
Case-insensitive lexical matching searches lesson text and evidence. Startup without
a task reason shows recent observations. Omit oversized whole entries; report omissions.
End hooks supplement lifecycle gates only where supported. Evidence text records a
claim; it does not authenticate its truth. The user's instruction to implement the
previous proposal approves this scope.

## Open questions

None. The spec is ready for planning.
