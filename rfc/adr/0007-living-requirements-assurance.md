# ADR 0007: Living requirements with mechanical assurance; judgment is never evidence

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §8](../0001-agentic.md#8-requirement-assurance)

## Context

A requirement verified once can silently regress later. Spec-first workflows
usually verify at delivery and then forget. Reviewers and risk owners want to
record judgments, but if judgments can turn a failing check green, evidence
loses its meaning.

## Decision

- Structured capability requirements MAY declare one `- Verify:` command (or
  `manual` with a reason) and one `- Inputs:` glob set, plus optional
  `- Governed-by:` and `- Accept-risk:` lines.
- `lifecycle.py assure` derives the status of each requirement from the newest
  matching `req:<ID>` ledger entry in committed records and the active task:
  VERIFIED, STALE, FAILED, UNVERIFIED, INVALID, MANUAL or UNDECLARED. It runs
  nothing unless `--run` is given.
- Ordering uses UTC completion intervals with microsecond precision.
  Overlapping executions are UNVERIFIED, never an arbitrary winner.
- L2/L3 `stage verify` refuses touched requirements that are STALE, FAILED,
  UNVERIFIED or INVALID.
- Reviewer attestations of MANUAL requirements and `Accept-risk` lines are shown
  next to the status but never change a status, a count or an exit code.

## Consequences

- Regressions in declared obligations show up as STALE or FAILED on later
  changes, not just at the original delivery.
- Architectural rules can be enforced when `Governed-by` is paired with a real
  checker.
- VERIFIED covers only that command on those inputs, not the full intent of the
  requirement.
- Evidence on unmerged branches is invisible, and squash merges can make
  evidence STALE.
- A schema-valid hand-written record is accepted. Assurance detects drift, not
  forgery ([ADR 0009](0009-trusted-ci-separated-environments.md) addresses
  forgery).

## Alternatives considered

- **Verify-at-delivery only.** Rejected because it misses regressions.
- **Letting `Accept-risk` waive failures.** Rejected because it turns risk
  acceptance into a green check.
- **Running every obligation on every verify.** Rejected as too costly. Only
  touched obligations gate.

## Evidence

`.ai/scripts/assurance.py` (`INPUTS`, `RISK`, `GOVERNED`), `.ai/lifecycle.md` §Assurance status,
`.ai/scripts/assurance_demo.py`, `.ai/scripts/assurance_measure.py`,
`.ai/scripts/assurance_architecture_demo.py`, `.ai/scripts/tests/test_assurance*.py`.

## Revisit when

Measurement (`assurance_measure.py`) shows false-STALE or missed-requirement
rates that justify a different freshness model.
