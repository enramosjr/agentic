# Spec: Trusted acceptance and merge authorization

Status: Draft; implementation has not been approved. Acceptance commands below
are proposed deliverables, not existing checks or recorded passing results.

## Problem and outcome

Local lifecycle records and candidate-controlled CI cannot independently establish
merge eligibility. AGENTIC and its adopters need critical acceptance verification
and merge authorization outside the modifying agent's write and administrative
access, while retaining local hooks for fast feedback.

Current evidence: [framework parity](../../.github/workflows/framework-parity.yml)
checks out and executes candidate-controlled tests and runner; its Qualification
job aggregates their results. [Lifecycle documentation](lifecycle.md) identifies
local approval attribution as a claim. On 2026-11-07, read-only GitHub API inspection
of `enramosjr/agentic` ruleset 25367654 found required Actions checks, zero required
approving reviews, and administrator pull-request bypass available to this session.
This describes the inspected configuration, not a permanent hosting guarantee.

## Users and scenarios

- Coding agents develop changes and receive local lifecycle feedback.
- Independent maintainers approve critical acceptance policy and administer merge
  controls using credentials unavailable to coding agents.
- Separately administered CI evaluates an exact candidate; its authoritative
  result is required by the hosting platform before merge eligibility.
- Adopter maintainers install the integration, provision the external authority,
  and verify effective deployment before claiming enforcement.
- Forged records, replaced tests, spoofed checks, missing approval, and stale
  results cannot authorize merge.

## Requirements

- R1: Critical acceptance obligations and their verifier MUST come from an
  independently approved, immutable policy/verifier revision outside the modifying
  agent's writable environment. A candidate MUST NOT weaken its own obligations.
- R2: Trusted CI MUST evaluate the identified candidate against those obligations.
  Local records, candidate-supplied reports, and candidate-controlled tests alone
  MUST NOT satisfy critical acceptance. Missing or empty required coverage MUST fail.
- R3: Candidate execution MUST be isolated from authoritative verifier inputs,
  authoritative result publication, and issuer or merge credentials. The privileged
  result issuer MUST NOT execute candidate code or candidate-selected commands.
- R4: Authoritative results MUST bind repository identity, candidate and evaluated
  target revisions, policy/verifier revisions, trusted execution identity and
  complete required outcomes. Missing, malformed, ambiguous, unsuccessful, or
  mismatched evidence MUST fail closed.
- R5: A changed candidate, evaluated target, or active policy MUST invalidate prior
  eligibility. Publication and authorization MUST reject results that became stale
  during execution; verification from another repository or execution source MUST
  NOT authorize the candidate.
- R6: Hosting controls outside coding-agent administrative access MUST require the
  separate verifier App's authoritative check and authenticated independent approval.
  Local approval claims, author self-approval, same-named checks from other issuers,
  direct pushes, and agent-accessible bypass MUST NOT authorize protected-branch
  updates. Passing checks MUST NOT instruct the coding agent to merge.
- R7: Existing local hooks and lifecycle commands MUST remain fast-feedback
  controls. Documentation and output MUST distinguish local completion from trusted
  verification and remote merge authorization.
- R8: A read-only deployment verification operation MUST check effective host
  protections, expected App identity, policy provenance, approval configuration and
  configured coding-agent access. Missing, inaccessible, inconsistent, or
  agent-bypassable configuration MUST fail. Unestablished credential separation
  MUST be reported as unverified rather than inferred from a local configuration.
- R9: Deployment qualification MUST include completed hosted positive and denial
  cases proving that replaced candidate checks, forged evidence, a spoofed check,
  missing approval and stale results cannot authorize merge. Unavailable hosted
  evidence MUST leave deployment incomplete.
- R10: AGENTIC MUST deliver installable adopter support as well as its own reference
  deployment. Fresh installation and upgrade MUST preserve local hooks and existing
  host protections, prepare the external-verifier integration, and identify required
  external provisioning. Installation MUST NOT provision credentials into the coding
  environment or report undeployed enforcement as active.

## Acceptance

- R1: `python3 -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_policy.py`
  rejects candidate replacement of policy, verifier and acceptance obligations;
  approved policy remains the source of obligations for that candidate.
- R2: `python3 -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_acceptance.py`
  drives the actual verification entry point against working and violating candidates;
  forged local PASS and candidate-only tests cannot rescue the violating candidate,
  and empty coverage fails.
- R3: `python3 -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_isolation.py`
  drives the actual isolation path with hostile candidate writes and credential
  access attempts; trusted inputs/results remain protected and the issuer never
  executes candidate code. Configuration presence alone does not satisfy this check.
- R4: `python3 -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_provenance.py`
  accepts complete exact trusted evidence and rejects missing fields, ambiguity,
  failure, cancellation, skipped checks and identity/revision substitutions.
- R5: `python3 -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_freshness.py`
  proves head, target and policy changes invalidate eligibility, including updates
  between execution and publication or authorization.
- R6: `python3 -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_authorization.py`
  rejects absent independent approval, self-approval, local attribution, spoofed
  issuers, direct updates and coding-agent bypass; only exact trusted PASS and
  configured independent authorization satisfy the policy.
- R7: `python3 -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_compatibility.py`
  exercises retained hook feedback and establishes that local lifecycle completion
  cannot produce trusted remote authorization.
- R8: `python3 -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_deployment.py`
  drives the actual read-only operation against controlled host responses and
  asserts failure for inaccessible configuration, wrong issuers, missing rules,
  bypass access and unverified credential separation. It performs no remote writes.
- R9: `python3 .ai/scripts/trusted_ci.py verify-deployment --live`
  verifies effective deployed configuration and completed hosted positive/denial
  evidence for the configured repository. It fails if required evidence is absent.
  Hosted tests use an independently administered qualification target, never an
  unauthorized merge into AGENTIC's default branch. Test actual host refusal,
  rather than only the local evaluator's opinion of merge eligibility.
- R10: `python3 -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_install.py`
  exercises fresh adopter installation and upgrade through the installer, retains
  local hook behavior, preserves existing protections, and reports external
  provisioning and deployment state without granting access or exposing credentials.

## Constraints

- Preserve Python 3.9 support and existing platform qualification requirements.
- Use a separately administered verifier/GitHub App. Issuer keys, policy approval
  authority and host administration/bypass credentials are unavailable to coding
  agents, including their local CLIs and candidate CI jobs.
- Policy updates require independent approval before activation and cannot approve
  themselves. Candidate code cannot write trusted tests or authoritative outcomes
  merely because execution occurs on a remote runner.
- Retain existing protection requirements during migration. Do not silently mutate
  repository rules, create external services, or grant permissions during install.
- Final authority is trusted CI plus hosting authorization; local evidence remains
  useful diagnostic and provenance material without authenticating human approval.
- Framework source documentation stays in existing locations; create no source
  `knowledge/` bundle. Adopter operational documentation follows its OKF conventions.

## Non-goals

- Universal CI/hosting provider support in this slice; GitHub is the first provider.
- Proving all behavior correct or discovering every missing acceptance requirement.
- Defending against compromised trusted administrators, verifier infrastructure or
  hosting provider.
- Automatic merging or weakening rules to enable a qualification run.

## Assumptions

- The user selected separate verifier credentials and installable adopter support
  on 2026-11-07. Both are in scope alongside AGENTIC's own deployment.
- An independent maintainer will provision the App, approved policy and scoped
  coding identity outside this chat's writable/credential environment. Exact
  deployment identifiers are configuration, not implicit authority grants.
- Implementation tests may use controlled fixtures; only completed hosted tests
  and effective configuration readback establish deployed enforcement.

## Open questions

None. The spec is ready for planning.
