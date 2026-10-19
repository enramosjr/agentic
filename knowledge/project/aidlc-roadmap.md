---
type: Development Guide
title: Capability baseline approval boundary
description: Distinguish current implementation documentation from a human-approved structured capability baseline.
tags: []
status: draft
evidence: project-documentation
generated: { by: agent/gpt-6, at: 2026-10-19T19:37:17Z }
sources:
  - id: ai-lifecycle-md
    resource: ../../.ai/lifecycle.md
  - id: ai-agents-analyst-md
    resource: ../../.ai/agents/analyst.md
  - id: ai-scripts-tests-test-brownfield-deltas-py
    resource: ../../.ai/scripts/tests/test_brownfield_deltas.py
verified: { by: "process:python3 -m unittest discover -s .ai/scripts/tests -p test_brownfield_deltas.py", at: 2026-10-19T21:17:33Z }
---

# Capability baseline approval boundary

## Current boundary

The structured capability baseline remains on hold until a human explicitly approves it. Documenting existing code, restoring missing guides, or inventorying repository paths does not establish approved requirements for every existing feature.

The bootstrap specification has explicit approval for its bounded R1–R6 change. Other prose capability documents summarize cited implementation and executable checks. They must not be silently converted into namespaced living requirements or treated as approval for unrelated behavior changes.

## Brownfield work

Use `okf.py onboard` for draft path facts, then inspect implementation, configuration, and tests. An analyst drafts claim-level sources and requests human approval before establishing a structured baseline. Subsequent deltas bind operated IDs to that approved baseline with target pins. Existing prose and legacy specifications remain valid without automatic conversion. This note records the approval boundary, not an implementation roadmap or promise of additional features.
