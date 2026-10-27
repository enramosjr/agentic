---
type: Development Guide
title: Installed governance size budget
description: Shorten nonnormative prose to retain the unchanged installed size limit
tags: [tooling]
status: stable
evidence: implementation-and-current-specifications
generated: { by: agent/unknown, at: 2026-10-26T18:13:24Z }
sources:
  - id: agents-md
    resource: ../../AGENTS.md
  - id: ai-scripts-tests-test-lifecycle-conformance-py
    resource: ../../.ai/scripts/tests/test_lifecycle_conformance.py
verified: { by: "process:python3 .ai/scripts/lifecycle.py reuse portable-governance-full-suite", at: 2026-10-26T18:17:05Z }
---

# Installed governance size budget

Shorten nonnormative prose to retain the unchanged installed size limit

## Problem and correction

Upstream AGENTS.md was 29,986 bytes. The installer's managed-block markers pushed
an otherwise exact downstream installation above the existing 30,000-byte cold
start test. Athenaeum's retained upstream-follow-up record already identified this
packaging issue. Shorten one nonnormative rationale paragraph while preserving
every heading and normative sentence; keep the budget test and installer intact.

## Verification and scope

`python3 -B -m unittest discover -s .ai/scripts/tests -p test_lifecycle_conformance.py`
passed through lifecycle evidence label portable-governance-conformance. It checks
the size limit and retained normative requirements. The frozen source full suite
and exact downstream installations supply final delivery evidence in the log.
No runtime contract changes, new logic or budget-test relaxation are introduced.
This L0 prose change is exempt from test-first and retrospective closure.
