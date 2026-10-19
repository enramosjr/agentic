---
type: Development Guide
title: AGENTS.md cold-start budget
description: "AGENTS.md stays under 30,000 bytes; reference material lives verbatim in .ai/agents-reference.md and a test guards every normative sentence."
tags: [governance, tokens]
status: stable
evidence: validated-runtime
generated: { by: agent/cursor, at: 2026-10-19T20:57:01Z }
sources:
  - id: agents-md
    resource: ../../AGENTS.md
  - id: ai-agents-reference-md
    resource: ../../.ai/agents-reference.md
  - id: ai-scripts-tests-test-lifecycle-conformance-py
    resource: ../../.ai/scripts/tests/test_lifecycle_conformance.py
verified: { by: "process:python3 -m unittest discover -s .ai/scripts/tests -p test_lifecycle_conformance.py", at: 2026-10-19T21:16:44Z }
---

# AGENTS.md cold-start budget

AGENTS.md stays under 30,000 bytes; reference material lives verbatim in .ai/agents-reference.md and a test guards every normative sentence.

Every session loads `AGENTS.md` (`CLAUDE.md` imports it), so its size is a per-session token cost. On 2026-10-19 it went from 45,982 to 29,871 bytes (29,988 after merging the evidence-ledger rules from `cc75e1a`) by moving reference material verbatim into `.ai/agents-reference.md`, loaded by section: subagent harness details, bundle layout, script commands, harness tool map and shell-guard detail, trigger matrix, frontmatter template, startup notes, E2E minimums, and autonomous-execution detail. `AGENTS.md` keeps every heading and points to the section it relies on. This follows the earlier move of Gate 4 execution rules to `.ai/validation-policy.md`.

`test_lifecycle_conformance.AgentsBudget` enforces three things:

- `AGENTS.md` is under 30,000 bytes.
- Every heading of `AGENTS.md` at commits `9e13fce` and `cc75e1a` survives.
- Every sentence of those versions containing MUST, SHOULD or MAY appears verbatim in `AGENTS.md` or in a `.ai/` document it links (skipped where the commit is absent, such as an installed adopter).

Moving a rule is allowed; deleting or rewording one fails the test.
