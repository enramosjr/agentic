---
type: Development Guide
title: Agent lifecycle and right-sizing
description: "The single lifecycle, tiers L0-L3, stage artifacts, and where each is defined."
tags: [governance, lifecycle]
status: stable
evidence: project-documentation
generated: { by: agent/unknown, at: 2026-10-18T15:33:47Z }
sources:
  - id: agents-md
    resource: ../../AGENTS.md
  - id: ai-lifecycle-md
    resource: ../../.ai/lifecycle.md
  - id: ai-agents-analyst-md
    resource: ../../.ai/agents/analyst.md
  - id: ai-agents-planner-md
    resource: ../../.ai/agents/planner.md
  - id: ai-agents-reviewer-md
    resource: ../../.ai/agents/reviewer.md
  - id: ai-agents-implementer-md
    resource: ../../.ai/agents/implementer.md
  - id: claude-agents-analyst-md
    resource: ../../.claude/agents/analyst.md
  - id: codex-agents-analyst-toml
    resource: ../../.codex/agents/analyst.toml
  - id: claude-skills-spec-skill-md
    resource: ../../.claude/skills/spec/SKILL.md
  - id: claude-skills-plan-skill-md
    resource: ../../.claude/skills/plan/SKILL.md
  - id: claude-skills-implement-skill-md
    resource: ../../.claude/skills/implement/SKILL.md
  - id: claude-skills-review-skill-md
    resource: ../../.claude/skills/review/SKILL.md
  - id: claude-skills-debug-skill-md
    resource: ../../.claude/skills/debug/SKILL.md
  - id: claude-skills-ship-skill-md
    resource: ../../.claude/skills/ship/SKILL.md
  - id: readme-md
    resource: ../../README.md
  - id: lifecycle-py
    resource: ../../.ai/scripts/lifecycle.py
  - id: lifecycle-eval-py
    resource: ../../.ai/scripts/lifecycle_eval.py
  - id: lifecycle-tests
    resource: ../../.ai/scripts/tests/test_lifecycle.py
  - id: lifecycle-eval-tests
    resource: ../../.ai/scripts/tests/test_lifecycle_eval.py
  - id: lifecycle-conformance-tests
    resource: ../../.ai/scripts/tests/test_lifecycle_conformance.py
  - id: eval-scenarios
    resource: ../../.ai/evals/lifecycle/01-typo-l0.json
  - id: validation-policy
    resource: ../../.ai/validation-policy.md
  - id: claude-settings
    resource: ../../.claude/settings.json
  - id: codex-hooks
    resource: ../../.codex/hooks.json
  - id: cursor-hooks
    resource: ../../.cursor/hooks.json
  - id: codex-skills-link
    resource: ../../.agents/skills
  - id: eval-bugfix
    resource: ../../.ai/evals/lifecycle/02-bugfix-l1.json
  - id: eval-feature
    resource: ../../.ai/evals/lifecycle/03-feature-l2.json
  - id: eval-escalation
    resource: ../../.ai/evals/lifecycle/04-escalation-l2.json
  - id: eval-user-tier
    resource: ../../.ai/evals/lifecycle/05-user-tier-held.json
  - id: eval-queue
    resource: ../../.ai/evals/lifecycle/06-queue-l3.json
verified: { by: "process:python3 -m unittest discover -s .ai/scripts/tests", at: 2026-10-18T16:30:00Z }
---

# Agent lifecycle and right-sizing

Every task follows one lifecycle: Intent, Plan, Implement, Review, Verify & Sync, Ship. The stages and artifacts are identical for a one-off prompt and an autonomous run; the tier sets the ceremony.

| Tier | Intent | Plan | Review |
|------|--------|------|--------|
| L0 trivial | none | none | own diff |
| L1 small | three-line note | light plan | self-review |
| L2 feature | approved spec (`analyst`) | full plan (`planner`) | independent `reviewer` |
| L3 milestone | queue objective and frozen `Acceptance` | batch plan | reviewer gates DONE |

## Where each rule lives

- Tier selection and escalation: [AGENTS.md §2.5](../../AGENTS.md).
- Stage exit checks, Stage 5 delivery options, and the debugging flow: [.ai/lifecycle.md](../../.ai/lifecycle.md).
- Spec structure and clarification rules: [.ai/agents/analyst.md](../../.ai/agents/analyst.md). L2 specs persist as `draft` docs under `knowledge/specifications/` and describe intent, not shipped behavior.
- Test-first and root-cause rules: AGENTS.md §8.6, applied by the implementer and checked in the reviewer's Pass 1.
- Entry points: stage skills in `.claude/skills/` (Claude Code) and `.agents/skills/` (Codex), a symlink to `../.claude/skills` so there is one copy, and the `analyst` subagent in `.claude/agents/` and `.codex/agents/`. Cursor gets hooks and `AGENTS.md` but no skills, because its skill directory is unconfirmed.
- Enforcement: `.ai/scripts/lifecycle.py` records the tier and stages per branch, validates each artifact (`stage`), records test-first evidence (`redgreen`), checks spec to plan to test coverage (`trace`), and emits queue entries from a spec (`queue-from-spec`). Its `hook` command runs in Claude Code, Codex and Cursor: source edits are denied until a tier is declared and the stages it requires are recorded, `git commit` (not `wip:`) and PR creation are denied until Verify is recorded or no tier is active, and the router is injected at session start. Markdown and `knowledge/` edits are exempt. `LIFECYCLE_GUARD=off` and `OKF_AUTONOMOUS=1` bypass it.
- Evals: `.ai/scripts/lifecycle_eval.py` runs six scenarios (L0 to L3) against any agent command and checks the outcome.
- Cold start: the Gate 4 execution rules moved verbatim to `.ai/validation-policy.md`, loaded on demand.

## Limits

Approvals and red/green evidence are recorded claims; the guard raises the cost of skipping a stage and does not prove human consent or that a red run failed for the reported reason. Edits made through the shell are not gated. Cursor's payload shapes and the Codex hook behavior were taken from vendor documentation and are covered by scripted payloads, not by a live harness.

## Evidence

`python3 -m unittest discover -s .ai/scripts/tests` covers the state machine, hooks (Claude, Codex `apply_patch`, and Cursor payload shapes), red/green, traceability, queue-from-spec validated by `okf.py validate`, the eval runner against compliant and non-compliant scripted agents, and document, registration, skill and hook-wiring consistency. No real agent has been run through `lifecycle_eval.py run`, so adherence by real models is unmeasured. The structural check for records is `python3 .ai/scripts/okf.py records`.
