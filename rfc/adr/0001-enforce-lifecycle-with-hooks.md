# ADR 0001: Enforce the lifecycle with harness hooks, not instructions

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §5.6](../0001-agentic.md#56-hook-enforcement-contract)

## Context

Agents lose instructions over long sessions and compactions, and under pressure
("the customer is waiting"). A process that depends on the agent remembering it
fails silently: the spec, the test or the review gets skipped, and the final
summary still reads as complete. Every supported harness (Claude Code, Codex,
Cursor) can run a command before a tool call and refuse that call.

## Decision

Lifecycle order is enforced at the tool boundary. `lifecycle.py hook` is wired
to the pre-tool and SessionStart events of every supported harness. It:

- denies source edits until a tier is declared and the stages required before
  Implement are recorded;
- denies `git commit` (other than `wip:`) and PR creation until Verify is
  recorded and the retrospective is closed;
- denies a commit that would leave the task's audit record untracked or
  unstaged;
- injects the lifecycle Router and approved project rules at session start.

Each `stage` command validates its artifact before recording it: a spec that
passes `analyze`, a plan that cites every requirement ID, an Approved canonical
review, a current passing ledger and convergence, and passing `records`.

Markdown and `knowledge/` edits are exempt so that intent and planning can be
written before code. A human can disable the tool gates with
`LIFECYCLE_GUARD=off`. Driver sessions (`OKF_AUTONOMOUS=1`) are gated by the
work queue instead.

## Consequences

- Skipping a stage is refused at once, with the missing stage named, instead of
  being discovered in review.
- The hook raises the cost of skipping a stage. It does not prove consent or
  stop arbitrary shell writes ([ADR 0008](0008-approvals-are-recorded-claims.md)).
- Each tool call pays for a hook process (10-second timeout). The scripts are
  stdlib-only to keep this cheap ([ADR 0005](0005-project-local-stdlib-kit.md)).
- Harnesses without hooks get the same rules by instruction only, and are weaker
  for it.

## Alternatives considered

- **Instructions only** (rules files, templates). Rejected because this is
  exactly the failure mode described under Context.
- **CI-only enforcement.** Rejected as the sole mechanism because feedback
  arrives after the work is done. Kept as a separate authority boundary
  ([ADR 0009](0009-trusted-ci-separated-environments.md)).
- **Git hooks only.** Rejected because they cannot see edits before commit and
  are easily bypassed with `--no-verify`.

## Evidence

`.ai/scripts/lifecycle.py` (`REQUIRED`, `EDIT_TOOLS`, `hook`), `.claude/settings.json`,
`.codex/hooks.json`, `.cursor/hooks.json`, `.ai/scripts/tests/test_lifecycle_conformance.py`
(`HarnessWiring`), `.ai/evals/lifecycle/13-pressure-bypass.json`.

## Revisit when

A harness offers a native, policy-level stage gate that can replace per-call
hooks without losing the artifact validation.
