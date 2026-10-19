---
type: Playbook
title: Record lessons and manage project rules
description: Human-approved promotion and retirement of captured engineering lessons.
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
verified: { by: "process:python3 -m unittest discover -s .ai/scripts/tests -p test_learning_loop.py", at: 2026-10-19T21:17:15Z }
---

# Record lessons and manage project rules

## Capture and review

During an active L1–L3 task, run `python3 .ai/scripts/lifecycle.py learn "Observation"`. Optional `--stage` and `--evidence` add context. Capture is inert; review the resulting `knowledge/history/lifecycle/RECORD.json#N` reference before considering it a project rule.

## Human approval

After a human explicitly approves promotion, use `python3 .ai/scripts/lifecycle.py promote RECORD#N --approved-by human:ID`. Do not invent an approval. To retire an active rule after human approval, use `python3 .ai/scripts/lifecycle.py retire RULE_ID --reason "Reason" --approved-by human:ID`. Retrying an identical operation repairs interrupted publication without duplicating the log entry.

Rules live in project knowledge. SessionStart injects active valid rules within an 8,192-byte UTF-8 budget. If rules are invalid or exceed the budget, repair the document instead of relying on partial injection. An ordinary observation does not gain instruction authority merely because it was captured.

## Milestone close

Use `python3 .ai/scripts/okf.py checkpoint --lessons-from RECORD` for each relevant milestone record, repeating `--lessons-from` when needed. The retrospective includes observations that were not promoted. Run the records check after changes. This guide documents the existing optional workflow; it does not approve any particular rule.
