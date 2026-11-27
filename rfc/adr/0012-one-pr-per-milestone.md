# ADR 0012: One pull request per milestone; agents never merge the default branch

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §12.7](../0001-agentic.md#127-version-control-authority)

## Context

Autonomous agents left to themselves open a PR per task, per worker or per run
update. That floods reviewers, fragments context and lets partially integrated
work look mergeable. Rebases, squashes and force-pushes by multiple agents
destroy ancestry and other agents' work.

## Decision

- Milestones, not tasks or sessions, define PR scope. Each milestone gets
  exactly one PR, titled `M<N>: <Title>`, on a `milestone/m<N>` integration
  branch. Existing PRs are reused across tasks and sessions.
- The PR body lists every milestone task as a checklist. An item is checked only
  after it is integrated, reviewed and validated on the integrated head.
- The PR stays a draft until every task and exit criterion passes on the
  integrated head and `gh pr view --json mergeable` reports `MERGEABLE`.
- Work is combined only by merging. Agents never cherry-pick, squash or rebase
  published commits, never force-push, and never use a bare `git stash`.
  `pr_sync.py` merges the base into behind PRs before each driver session.
- The work queue, archive and status have one writer, on the run branch.
- Agents MAY push branches and open or update the milestone PR. They MUST NOT
  merge into the default branch, rewrite published history, delete branches
  they did not create, or publish releases without explicit human authorization.

## Consequences

- Reviewers see one coherent, checklist-tracked unit per milestone.
- Ancestry and evidence reuse remain valid, because `git diff` against the
  tested commit stays meaningful.
- Milestone PRs can grow large, so review relies on per-task review inside the
  run.
- Interactive (non-L3) work follows the ordinary Ship stage, where the user
  chooses PR, keep or discard.

## Alternatives considered

- **A PR per task.** Rejected because of reviewer flood and partial
  integration.
- **Agents merging after green CI.** Rejected because merge is an outward,
  hard-to-reverse action reserved for humans or a trusted authority
  ([ADR 0009](0009-trusted-ci-separated-environments.md)).

## Evidence

`.ai/autonomous-execution.md` §9.9, `.ai/agents-reference.md` §Autonomous execution,
`.ai/scripts/pr_sync.py`, `okf.py git-setup`, `AGENTS.md` §9.

## Revisit when

Hosting platforms offer stacked or grouped PR primitives that preserve the
single-merge-signal property.
