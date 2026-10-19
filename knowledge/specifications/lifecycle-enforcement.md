---
type: Specification
title: Lifecycle enforcement and evals
description: "Mechanical enforcement, traceability, evals and cross-harness reach for the AIDLC."
tags: [spec, lifecycle]
status: draft
evidence: project-documentation
generated: { by: agent/unknown, at: 2026-10-18T16:05:11Z }
sources:
  - id: ai-scripts-lifecycle-py
    resource: ../../.ai/scripts/lifecycle.py
  - id: ai-scripts-lifecycle-eval-py
    resource: ../../.ai/scripts/lifecycle_eval.py
  - id: ai-lifecycle-md
    resource: ../../.ai/lifecycle.md
---

# Lifecycle enforcement and evals

Mechanical enforcement, traceability, evals and cross-harness reach for the AIDLC. Scope was approved by the user's request to address every gap found in the comparison with Superpowers and Spec Kit.

## Problem and outcome

The lifecycle added in the previous change was prose only: nothing tested it, nothing enforced it, only Claude Code had stage skills, `AGENTS.md` was heavy at cold start, and spec to plan to test traceability was a rule with no check. The outcome is a lifecycle whose tier, stages, test-first rule and traceability are enforced by scripts and hooks in three harnesses and proven by tests.

## Users and scenarios

Agents in Claude Code, Codex and Cursor working one-off prompts (L0 to L2) and queued autonomous milestones (L3); maintainers changing lifecycle rules.

## Requirements

- R1: A hook in Claude Code, Codex and Cursor MUST deny source edits until a tier is declared and the stages that tier requires before Implement are recorded.
- R2: The same hook MUST deny `git commit` (other than `wip:`) and PR creation until Verify is recorded, and MUST inject the lifecycle router at session start.
- R3: Bug-fix and new-logic work MUST be refusable without red-then-green evidence, where red must fail and green must pass on a changed working tree.
- R4: A command MUST check that a spec is lint-clean and that its plan and tests cite every requirement ID, and stage recording MUST refuse a spec or plan that fails it.
- R5: A command MUST turn a lint-clean spec into valid work-queue entries so the L3 path starts from the spec.
- R6: A scenario eval runner and a corpus covering every tier MUST pass a scripted compliant agent and fail a non-compliant one, and MUST be runnable against a real agent.
- R7: The six stage skills MUST exist for Claude Code and Codex with identical content, and every documented `okf.py show` command MUST resolve.
- R8: The normative Gate 4 execution rules MUST move out of `AGENTS.md` verbatim so cold-start size falls without losing rules.

## Acceptance

- R1: `python3 -m unittest test_lifecycle.HookTests test_lifecycle_conformance.HarnessWiring` passes.
- R2: `python3 -m unittest test_lifecycle.HookTests.test_commit_needs_verify_but_wip_commit_does_not test_lifecycle.HookTests.test_session_start_injects_the_router_and_the_missing_tier` passes.
- R3: `python3 -m unittest test_lifecycle.RedGreenTests` passes.
- R4: `python3 -m unittest test_lifecycle.SpecTests test_lifecycle.StageTests` passes.
- R5: `python3 -m unittest test_lifecycle.SpecTests.test_queue_from_spec_entries_pass_okf_validation` passes.
- R6: `python3 -m unittest test_lifecycle_eval` passes.
- R7: `python3 -m unittest test_lifecycle_conformance.RolesAndSkills` passes.
- R8: `python3 -m unittest test_lifecycle_conformance.Relocation` passes, and a one-time comparison of the 16 relocated paragraphs against `git show HEAD~1:AGENTS.md` reports none missing.

## Constraints

Standard library only, Python 3.9+. Hooks fail open on any internal error and on unparseable input. Existing section numbers in `AGENTS.md` do not change.

## Non-goals

Proving human consent, enforcing the rules in harnesses without hooks, running real-agent evals in the unit suite, and rewriting existing Gate 4 policy text.

## Assumptions

Approval is a recorded claim from a user message, not a cryptographic proof. Markdown and `knowledge/` edits are exempt from the edit gate. Cursor loads `AGENTS.md` and hooks but its skill directory is unconfirmed, so it gets no stage skills.

## Open questions

None. The spec is ready for planning.
