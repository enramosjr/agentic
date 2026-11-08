# Spec: Managed trusted verification with automated GitHub onboarding

Status: Approved by the user on 2026-11-07; lifecycle intent approval recorded as
`human:enram`. No managed service is implemented or deployed. Acceptance commands
are proposed deliverables.

Superseded scope on 2026-11-07: the user rejected AGENTIC-funded service operation
and requested nearly automated adopter-owned setup, retaining AGENTIC-maintained
AWS and Azure adapters deployed into each adopter's infrastructure. The historical
approval above does not authorize the rejected service architecture.

## Problem and outcome

The existing trusted-CI adapter requires each adopter to configure an authority
repository, App, secrets, runners and host controls. The user rejected that
end-user setup and selected one-time consent with a managed service.

The proposed flow is: Connect GitHub → select repositories → review and authorize
proposed protections → automatic setup and qualification → protected development.
AGENTIC's operator owns the service infrastructure and App registration once;
customers do not create or configure those resources.

This proposes replacing per-adopter deployment assumptions in
[the original spec](trusted-ci-spec.md), while preserving independently controlled
critical acceptance, isolation, exact-revision evidence and remote authorization.
The earlier tested adapter remains a reusable baseline, not managed-service proof.

## Users and scenarios

- Repository owners connect through standard platform consent and repository selection.
- Organization owners grant platform-required installation access.
- Maintainers approve initial protection changes and later policy changes in AGENTIC.
- Coding tasks receive restricted credentials without human/admin keys or sessions.
- Partial setup, revoked access or stale evidence leaves enforcement inactive/blocked.
- The AGENTIC operator provisions production infrastructure for all adopters.

## Requirements

- R1: End-user onboarding MUST require only one initial connection journey,
  repository selection and required permission/protection approvals. It MUST NOT
  require manual App registration, keys, authority repositories, workflow settings,
  secrets, runners, rules or qualification fixtures in GitHub.
- R2: AGENTIC MUST operate the independent verifier, immutable approved policy
  registry, execution fleet and evidence store. Each repository MUST have nonempty
  critical coverage. A candidate MUST NOT replace or weaken its own obligations.
- R3: Provisioning, coding, verification and publication MUST have isolated
  credential domains. Root/signing and administrative credentials MUST remain in
  the control plane. Coding credentials MUST lack administration, bypass,
  checks-write and statuses-write. Publishers MUST lack administrative credentials
  and keys capable of minting them, and MUST NOT execute candidate content.
  Installation/job tokens MUST be scoped to authorized repositories and purposes.
- R4: After authenticated consent, setup MUST automatically discover capabilities,
  present exact changes, provision approved controls and verify effective readback.
  Interrupted retries MUST be idempotent. Bootstrap MUST avoid marker/check
  deadlocks without weakening existing protections or granting an agent bypass.
- R5: Strong enforcement MUST require a credential-isolated coding environment
  whose access AGENTIC can establish. Protected v1 tasks MUST run in managed
  workers without ambient human/admin credentials or browser sessions. External
  agents with unestablished separation MUST receive a narrower-assurance status.
- R6: Managed evidence MUST bind tenant, installation, repository, candidate,
  target, policy/verifier/runtime revisions, authenticated provider execution and
  complete outcomes. Changed bindings or authorization MUST invalidate eligibility.
  Local, candidate-supplied and legacy Actions evidence alone MUST NOT satisfy the
  versioned managed protocol.
- R7: Tenant authorization MUST apply to callbacks, provisioning, dispatch,
  artifacts, publication and recovery. Cross-tenant substitutions, callback replay
  and candidate-selected authorities, commands or credential scopes MUST be rejected.
- R8: The service MUST distinguish connected, setup, qualification, active,
  blocked and revoked states. Active enforcement MUST require completed setup,
  effective controls, established credential separation and current qualification.
  Partial failure, drift, revocation and missing evidence MUST fail closed.
- R9: The service MUST automate real hosted positive and intended-denial
  qualification before advertising enforcement. Bad acceptance, replaced checks,
  forged evidence, spoofed issuers, missing approval, direct updates and stale
  bindings MUST be exercised. Generic errors and skipped checks MUST NOT count.
- R10: The installed client MUST support connection/status while preserving local
  hooks and runtimes. It MUST NOT contain service keys or require privileged local
  storage. Policy approval and code review MUST remain explicit human decisions;
  connection consent MUST NOT approve future candidate changes.

## Acceptance

- R1: `python3 .ai/scripts/tests/test_managed_authority.py OnboardingConsent`
  completes a clean-tenant connection with standard consent/selection actions only.
- R2: `python3 .ai/scripts/tests/test_managed_authority.py ApprovedPolicy`
  rejects candidate substitutions, empty coverage and unapproved policy changes.
- R3: `python3 .ai/scripts/tests/test_managed_authority.py CredentialDomains`
  drives real broker/worker boundaries and denies escalation or other-repository access.
- R4: `python3 .ai/scripts/tests/test_managed_authority.py AutomatedProvisioning`
  verifies fresh/retried setup and preserved existing protections without bypass.
- R5: `python3 .ai/scripts/tests/test_managed_authority.py CodingIsolation`
  verifies managed isolation and rejects strong status for unverified external agents.
- R6: `python3 .ai/scripts/tests/test_managed_authority.py ManagedProvenance`
  rejects stale, substituted, incomplete and legacy-only execution evidence.
- R7: `python3 .ai/scripts/tests/test_managed_authority.py TenantAuthorization`
  rejects replay and cross-tenant attempts through actual service interfaces.
- R8: `python3 .ai/scripts/tests/test_managed_authority.py EnforcementLifecycle`
  verifies failure, recovery, drift, revocation and outage states fail closed.
- R9: `python3 .ai/scripts/managed_authority.py qualify --live`
  completes hosted clean-tenant onboarding and positive/denial qualification; missing
  service, consent or evidence fails rather than producing a qualification claim.
- R10: `python3 .ai/scripts/tests/test_managed_authority.py InstalledClient`
  exercises installed connection/status and local hooks without manual infrastructure.

## Constraints

- One connection journey may contain platform-required consent screens; no promise
  of one literal dialog or automatic organization-owner approval is made.
- Provisioning privileges stay in the managed broker. GitHub ruleset creation and
  updates require Administration write; bypass inventories may be hidden from
  callers lacking ruleset write access. A read-only token is not proof of no bypass.
- A publisher receives only scoped publication credentials, never the provider root
  key. Coding credentials cannot publish the check accepted by hosting controls.
  App count is a later implementation decision, not a customer configuration task.
- Tenant-supplied approved checkers are isolated from other tenants and the control
  plane; approval within a tenant does not make customer code globally trusted.
- Unsupported permissions/account capabilities leave setup unverified, without a
  hidden fallback asking customers to configure GitHub manually.
- Preserve Python 3.9 client compatibility and existing qualification requirements.
- Service operators own hosting, registration and key management. Operator bootstrap
  remains necessary; it is not repeated by each end user.

## Non-goals

Universal Git hosting, exhaustive application correctness, automatic human review,
and strong claims for arbitrary administrator-capable external coding agents.

## Assumptions

- The user selected one-time consent and a managed service on 2026-11-07.
- AGENTIC will operate the service; no production endpoint exists yet.
- The user selected managed tasks for strong enforcement on 2026-11-07; external
  agents with unestablished separation receive narrower assurance.
- Existing policy/controller/isolation code may be reused after adapter/schema work.
  The 35-job CI PASS and original 9/10 acceptance do not verify managed behavior.

## Open questions

None. The approved spec is ready for implementation planning.

## Evidence

- Existing implementation: `trusted_ci_policy.py` binds Actions-specific identities;
  `trusted_ci_deployment.py` reads per-authority variables and manual attestations;
  `.ai/trusted-ci/authority.yml` requires per-adopter secrets and infrastructure.
- [Scoped GitHub installation tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app)
- [GitHub repository rules API and readback limitations](https://docs.github.com/en/rest/repos/rules)
- [Standard App installation consent](https://docs.github.com/en/apps/using-github-apps/installing-a-github-app-from-a-third-party)
