# ADR 0014: Human-gated learning: observations are advisory, rules require promotion

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §11](../0001-agentic.md#11-learning-loop)

## Context

Agents repeat the same mistakes across sessions because lessons die with the
conversation. If agents could write their own binding rules, however, a
mistaken or injected "lesson" would gain instruction precedence over the
project's real rules.

## Decision

- **Observations** (`lifecycle.py learn TEXT --evidence REF`) are inert data. At
  task declaration and SessionStart, up to five relevant entries
  (8,192 UTF-8 bytes) are surfaced, ranked by token overlap, recency and source.
  They carry no instruction precedence.
- **Retrospectives** must be closed explicitly before Verify, commit, PR or Ship
  at L1–L3. The agent either selects evidence-backed lessons or records why
  there are none. Capture alone does not close the gate, and lessons must not be
  invented to satisfy it.
- **Rules** come only from `promote RECORD#N --approved-by human:ID` and are
  removed only by `retire … --approved-by human:ID`. `decision:` actors are
  refused. Active rules have repository-instruction precedence and are injected
  at SessionStart (8,192-byte cap). Invalid rules produce a diagnostic and no
  partial injection.

## Consequences

- Lessons carry forward without silently changing governance.
- Prompt-injected text in a lesson stays advisory unless a human promotes it.
- The retrospective gate adds a small cost to every L1+ task.
- Human attribution is a claim, as everywhere locally ([ADR 0008](0008-approvals-are-recorded-claims.md)).

## Alternatives considered

- **No learning loop.** Rejected because mistakes repeat.
- **Agent-authored rules.** Rejected because of precedence escalation and the
  injection risk.
- **Unbounded observation injection.** Rejected because of context cost. Hence
  the byte caps and ranking.

## Evidence

`.ai/scripts/learning.py`, `.ai/scripts/lifecycle.py` (`learn`, `retrospect`, `observations`,
`promote`, `retire`), `.ai/docs/learning-loop.md`, `.ai/docs/learning-loop-playbook.md`,
`.ai/evals/lifecycle/17-retrospective-reuse.json`.

## Revisit when

Evaluation shows observation retrieval is too noisy to help, or rule volume
exceeds the injection cap in practice.
