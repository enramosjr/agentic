# ADR 0009: Trusted CI as three separated environments with an independent authority

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance). The implementation is under qualification.
- **Recorded:** 2026-11-27
- **RFC:** [0001 §13](../0001-agentic.md#13-trusted-ci-and-merge-authorization)

## Context

Local gates cannot authorize a merge, because the coding environment writes
both the candidate and its evidence ([ADR 0008](0008-approvals-are-recorded-claims.md)).
Ordinary CI in the same repository is also inadequate: a candidate can modify
the workflow, the tests or the receipts that the check reads.

## Decision

Merge authorization is separated into three environments:

1. **Coding environment.** Edits and runs local checks. It has no authority
   write or admin access, no issuer keys and no bypass.
2. **Authority repository.** Independently administered. It runs approved
   host-side assertions against a snapshot of the candidate inside a restricted
   Linux container: Docker or Podman, nonroot, read-only root, no network, no
   capabilities, `no-new-privileges`, default seccomp, cgroup limits and a
   disk-backed bounded work volume.
3. **Publisher job.** A fresh job that validates artifact provenance and
   freshness and publishes the required check with a separate App token. It
   never checks out the candidate.

A strict policy pins identities, the immutable workflow and verifier SHAs, a
digest-pinned image, the checks and the resource limits. It is activated through
a protected target commit carrying `epoch` and `policy_digest`. Only the exact
synthetic merge SHA receives the check. The four built-in critical checks
(lifecycle denial, assurance failure, install preservation, authority
separation) cannot be overridden by adopter extensions.

## Consequences

- Candidate-controlled workflow changes, forged receipts and hostile writes
  cannot reach trusted files or check publication.
- Adopters must provision and administer a separate repository, Apps and
  ephemeral runners. The cost is theirs, and AGENTIC provides no hosted service.
- Enforcement may not be claimed until hosted positive and denial qualification
  passes and `trusted_ci.py verify-deployment --live` reports verified. No
  deployment is currently qualified.
- Authority administrators, kernel and runtime, the image and the approved
  checks remain trusted.

## Alternatives considered

- **Same-repository CI with branch protection.** Rejected because the candidate
  can alter what CI runs or reads.
- **Running candidate code on the controller host.** Rejected because it
  exposes credentials and trusted files.
- **A maintainer-operated hosted authority.** Rejected because of shared trust,
  funding and privacy concerns. Deployment is adopter-owned instead
  (`deploy/authority/`, v2, release-held).

## Evidence

`.ai/scripts/trusted_ci*.py`, `.ai/scripts/authority_*.py`, `.ai/trusted-ci/authority*.yml`,
`.ai/docs/trusted-ci.md`, `.ai/docs/trusted-ci-adopter-local.md`,
`.ai/docs/trusted-ci-bootstrap-preflight.md`, `deploy/authority/`.

## Revisit when

Hosted qualification completes, or a hosting platform offers equivalent
separated attestation natively.
