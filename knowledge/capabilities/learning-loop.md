---
type: Capability
title: Optional lessons and approved project rules
description: Capture observations and promote or retire project rules with human approval.
tags: []
status: stable
evidence: implementation-and-current-specifications
generated: { by: agent/gpt-6, at: 2026-10-19T19:37:17Z }
sources:
  - id: ai-scripts-learning-py
    resource: ../../.ai/scripts/learning.py
  - id: ai-scripts-lifecycle-py
    resource: ../../.ai/scripts/lifecycle.py
  - id: ai-scripts-tests-test-learning-loop-py
    resource: ../../.ai/scripts/tests/test_learning_loop.py
  - id: ai-lifecycle-md
    resource: ../../.ai/lifecycle.md
verified: { by: "process:python3 .ai/scripts/okf.py records", at: 2026-10-19T19:37:49Z }
---

# Optional lessons and approved project rules

## Behavior

`lifecycle.py learn` records an observation in an active L1–L3 lifecycle record. Capture is optional and does not change project instructions or gate progression. Each observation keeps its number, text hash, and provenance in the task record.

`lifecycle.py promote` turns a captured lesson into a project rule only with explicit `human:ID` approval. `lifecycle.py retire` retires an existing rule with a reason and human approval. Approval flags record the claim; they do not authenticate consent. Lessons alone are observations, while active approved project rules have repository-instruction precedence.

SessionStart injects valid active rules within an 8,192-byte UTF-8 budget. Missing rules preserve behavior; invalid rules produce a diagnostic without partial injection. Promotion and retirement retries reconcile publication and logging rather than create duplicate operations.

`okf.py checkpoint --lessons-from RECORD` includes unpromoted observations in milestone retrospectives; repeat the argument for multiple source records. The source framework's lessons and rules are not installed into adopter projects.

## Evidence

The implementation is in learning.py and lifecycle.py; test_learning_loop.py covers capture, approvals, rules, retry/log behavior, injection, retrospectives, and installer exclusions. This is prose documentation of current behavior, not a newly approved structured requirements baseline.
