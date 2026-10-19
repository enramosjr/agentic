---
type: Historical Record
title: Lifecycle enforcement plan
description: "Implementation plan and delivery record for lifecycle enforcement, evals and cross-harness reach."
tags: [plan, lifecycle]
status: draft
evidence: project-documentation
generated: { by: agent/unknown, at: 2026-10-18T16:05:36Z }
sources:
  - id: ai-scripts-lifecycle-py
    resource: ../../.ai/scripts/lifecycle.py
  - id: eval
    resource: ../../.ai/scripts/lifecycle_eval.py
  - id: spec
    resource: ../specifications/lifecycle-enforcement.md
---

# Lifecycle enforcement plan

Implementation plan for [the enforcement spec](../specifications/lifecycle-enforcement.md), kept as the delivery record.

## Steps

### Step 1: R3, R4, R5 state machine, red/green, trace and queue-from-spec
`.ai/scripts/lifecycle.py` (new) with `tier`, `stage`, `gate`, `status`, `redgreen`, `trace`, `queue-from-spec`. Verified by `test_lifecycle.SpecTests`, `StageTests`, `RedGreenTests`, plus a mutation check that breaking the stage-completion test fails four tests.

### Step 2: R1, R2 hooks
`lifecycle.py hook` normalizes Claude, Codex (`apply_patch`) and Cursor (`preToolUse`, `beforeShellExecution`, `sessionStart`) payloads. Wired in `.claude/settings.json`, `.codex/hooks.json`, `.cursor/hooks.json`. Verified by `test_lifecycle.HookTests` and `test_lifecycle_conformance.HarnessWiring`.

### Step 3: R6 evals
`.ai/scripts/lifecycle_eval.py` and six scenarios in `.ai/evals/lifecycle/` covering L0 to L3. Verified by `test_lifecycle_eval`: a scripted compliant agent passes all six, an agent that ignores the lifecycle and an agent that declares a tier but skips the work both fail.

### Step 4: R7 skills for Codex
Mirror `.claude/skills` to `.agents/skills`; conformance test asserts identical trees and that every documented `okf.py show` command resolves.

### Step 5: R8 cold-start size
Move the Gate 4 execution rules verbatim to `.ai/validation-policy.md`; `AGENTS.md` §8.4 keeps the table and a MUST-load pointer. Verified by `test_lifecycle_conformance.Relocation` and a one-time line comparison against `git show HEAD~1:AGENTS.md`.

### Step 6: Documentation and knowledge sync
`AGENTS.md` §2.5, §3.1, §8.4, §8.6, Gate 4; `.ai/lifecycle.md`; analyst, planner, reviewer, implementer roles; README; `knowledge/project/lifecycle.md`; log.

## Validation

`python3 -m unittest discover -s .ai/scripts/tests` and `python3 .ai/scripts/okf.py records`.
