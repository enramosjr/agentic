# ADR 0002: One lifecycle, right-sized by four tiers

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §5.2–§5.3](../0001-agentic.md#52-tiers)

## Context

A single heavyweight process makes typo fixes absurd and pushes people to bypass
it. Separate processes for "small" and "large" work make the boundary between
them a negotiation, and an agent will tend to pick the cheaper one. Single
prompts and unattended runs need the same guarantees, with different parties
answering the questions.

## Decision

Every task follows the same lifecycle (Intent, Plan, Implement, Review, Verify &
Sync, Ship). A tier sets how much ceremony each stage gets:

| Tier | Recorded stages |
|------|-----------------|
| L0 trivial | none (focused check and `okf.py affected`) |
| L1 small | intent (three-line note), plan (light), verify |
| L2 feature | intent (approved spec), plan (full), review (independent), verify |
| L3 milestone | the same as L2, with the queue as the artifact set |

The agent MUST choose the lowest tier whose conditions hold and state it with a
reason. It MUST escalate on discovering a contract, schema, persistence,
security or dependency effect. A user-set tier cannot be lowered. Tiers scale
breadth. They never relax the completeness prohibitions or the evidence rules.
Test-first is keyed to the task kind (`bugfix`, `logic`), not to the tier.

## Consequences

- One mental model, from a one-line prompt to an autonomous milestone.
- Because tier selection is itself a judgment, scripted evaluations cover
  escalation and tier lowering under pressure.
- L0 declarations expire at the next commit, so L0 cannot be used to slip in a
  behavior change.

## Alternatives considered

- **A fixed process for all work.** Rejected as too costly for small changes.
- **No tiers, with reviewer discretion.** Rejected because it cannot be
  enforced mechanically.
- **Size-based tiers (lines changed).** Rejected because risk follows effect
  (contracts, persistence, security), not diff size.

## Evidence

`.ai/scripts/lifecycle.py` (`TIERS`, `REQUIRED`, `KINDS`, `TEST_FIRST_KINDS`),
`AGENTS.md` §2.5, `.ai/lifecycle.md` §Tiers in practice,
`.ai/evals/lifecycle/01-typo-l0.json` … `06-queue-l3.json`, `12-pressure-tier-lowering.json`.

## Revisit when

Evaluation data shows systematic mis-tiering that a mechanical signal (for
example touched schema or lockfile paths) could detect.
