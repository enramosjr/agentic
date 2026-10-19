---
type: Development Guide
title: Lifecycle gates and evidence
description: "Current lifecycle stages, committed audit records, and validation commands."
tags: []
status: stable
evidence: implementation-and-current-specifications
generated: { by: agent/gpt-6, at: 2026-10-19T19:37:17Z }
sources:
  - id: ai-scripts-lifecycle-py
    resource: ../../.ai/scripts/lifecycle.py
  - id: ai-lifecycle-md
    resource: ../../.ai/lifecycle.md
  - id: ai-scripts-tests-test-lifecycle-py
    resource: ../../.ai/scripts/tests/test_lifecycle.py
  - id: ai-scripts-tests-test-lifecycle-conformance-py
    resource: ../../.ai/scripts/tests/test_lifecycle_conformance.py
verified: { by: "process:python3 .ai/scripts/okf.py records", at: 2026-10-19T19:37:49Z }
---

# Lifecycle gates and evidence

## Stages

The repository lifecycle is Intent, Plan, Implement, Review, Verify and sync, then Ship. Tier selection controls artifact depth. L0 covers trivial edits; L1 uses intent and plan notes; L2 requires a human-approved spec, traced plan, independent review, and passing acceptance; L3 follows the autonomous queue. The normative workflow lives in `.ai/lifecycle.md` and AGENTS.md.

## Records and checks

`lifecycle.py` stores branch-local scratch state and publishes L1–L3 audit records under `knowledge/history/lifecycle/`. Referenced spec, plan, and review bodies are hashed. `python3 .ai/scripts/lifecycle.py audit` detects changed or missing approved artifacts; commit the audit record with the change.

`python3 .ai/scripts/lifecycle.py analyze SPEC` checks requirement and acceptance consistency before approval. `python3 .ai/scripts/lifecycle.py trace SPEC --plan PLAN --tests TESTS` checks ID coverage. After implementation and OKF synchronization, `python3 .ai/scripts/lifecycle.py converge SPEC` executes the approved acceptance commands with closed stdin and disk-backed scratch. L2+ verification requires a current passing result, with manual checks explicitly reviewed.

Use `lifecycle.py run LABEL -- CMD` for recorded validation and `lifecycle.py reuse LABEL` before repeating a check. Review and Verify also scan added lines for unfinished behavior. Verify checks the evidence ledger, approved references, convergence, OKF synchronization, and records; it derives its note from executed evidence at L2+. Ship closes the task after the selected delivery action. These commands record claims and evidence, not authenticated human consent.
