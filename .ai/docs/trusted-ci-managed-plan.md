# Plan: Managed trusted verification and automatic GitHub onboarding

Status: Withdrawn on 2026-11-07. The user rejected AGENTIC-funded hosting and
requested automated adopter-owned setup plus AWS/Azure self-deployment adapters.
This historical proposal does not authorize implementation. No managed service
is implemented or deployed.
The user approved [the managed spec](trusted-ci-managed-spec.md) on 2026-11-07.

Tier: L2, because this introduces persistent service state, security boundaries,
hosted execution and public protocols. Primary persona: Python principal engineer.
Preserve the Python 3.9 client floor, validate inputs at boundaries and verify real
HTTP, database, credential and isolation behavior.

## Objective and completion criteria

Deliver AGENTIC-operated critical verification and managed coding tasks through
one customer connection journey. AGENTIC itself and installed adopters use the
same path. Customers consent, select repositories and approve proposed protections;
they never register Apps or configure keys, authority repositories, workflows,
runners, rules or qualification fixtures manually.

Completion requires all R1–R10 acceptance criteria, independently reviewed code,
real hosted positive and intended-denial qualification, and a passing frozen gate.
Legacy CI and local qualification remain useful baseline evidence, not proof of
the new managed service. Strong enforcement applies to managed tasks; arbitrary
external agents with owner credentials receive no stronger assurance.

## Reference architecture selected by plan approval

Use AWS for the first operator deployment:

- ECS Fargate runs the trusted API, reconciler, credential broker, session
  coordinator and publisher under distinct IAM roles and network policies.
- RDS PostgreSQL holds durable control state, memberships, approvals and leases.
- S3 holds digest-addressed immutable policy, source and evidence artifacts.
- SQS and a PostgreSQL transactional outbox provide durable scheduling.
- Each coding or verification job gets a dedicated ephemeral Linux EC2 host,
  pinned image and hard-sized ext4 work disk. Destroy hosts after each job;
  never share a daemon, writable workspace or host between tenants.
- Secrets Manager holds operator App and model/session credentials. Evidence
  signing permissions remain outside all job hosts and publishers.

Fargate hosts trusted services, not the nested Docker verifier. Its restricted
runtime cannot directly host the existing Docker/device workflow. The verifier
uses Docker on its dedicated Linux host and the existing bounded sandbox.
See [AWS Fargate restrictions](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-security-considerations.html).
Containers remain the candidate execution boundary; the dedicated host adds
tenant and job separation around the daemon.

Create a separately packaged `services/authority/` backend using Python 3.12,
FastAPI/Uvicorn, psycopg, boto3, cryptography and the official OpenAI SDK. Pin
dependencies in its own lock file and build immutable release images. Keep all
backend dependencies and infrastructure outside `.ai/`, which the installer
recursively exports. Installed clients remain stdlib-only Python 3.9+.

Use one operator-owned public GitHub App. Only its broker holds the private key.
Issue installation tokens with explicit repository IDs and reduced permissions;
never inherit all installation repositories or permissions by omission.
[GitHub token downscoping](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).
The App has no ruleset bypass. No token purpose may inherit bypass via App identity.

## Credential and execution domains

| Domain | Allowed capability | Excluded capability |
|---|---|---|
| Provisioner | Consented configuration and privileged effective-control readback | Candidate execution |
| Broker | Mint tokens under a fixed workload-purpose matrix | Candidate-selected scopes or destinations |
| Coding sandbox | Task source, restricted executor connection, bounded outputs | GitHub/admin/model application keys, metadata, Docker socket |
| Submission service | Validate patch and create restricted task branch/PR | Admin, trusted checks, approval or bypass |
| Verifier host | Exact source/policy and job-specific artifacts | GitHub mutations, root keys, evidence signing |
| Publisher | Scoped checks-write and required read permissions | Token minting, administration, candidate execution |
| Session coordinator | Create/monitor model sessions and enforce task limits | Passing application credentials into workers |

Distinct deployed identities enforce these boundaries. A caller-provided purpose
field is not authorization. Broker policy binds authenticated workload, tenant,
installation, repository, job and allowed operations. No coding job inherits
human GitHub credentials, browser state or local administrator sessions.

Use the Agents API self-hosted executor as the initial real coding adapter.
The session coordinator creates and monitors the session outside the worker;
`codex exec-server` runs inside an isolated task container with a fresh HOME.
Only a connecting-environments credential enters that container. The application
API key remains in the coordinator. Pin a tested CLI and SDK version rather than
installing an unbounded alpha release.
[Official executor and credential contract](https://developers.openai.com/api/docs/guides/agents-api/environments/self-hosted).

Do not assume an environment credential is scoped to one job. Before adopting a
credential-sharing topology, test attachment attempts to other environments and
sessions in the same project. Start with separate tenant project/service-account
domains, no overlapping jobs within a credential domain, and per-job credential
rotation/revocation. Prove old credentials cannot attach to subsequent jobs;
automate this lifecycle and fail closed if the provider cannot enforce it.
Account eligibility, restricted-key behavior,
streaming, cancellation and executor compatibility are early live preflights.
No fallback places a broad model key in a worker. Session budgets, deadlines and
cancellation are enforced by the external coordinator and host lease supervisor.
Enforce admission limits; claim a hard spending cap only if verified provider
controls enforce it. Persist project/service-account, session/environment IDs,
executor version, credential generation and revocation outcome with the job,
never secret values in logs or evidence.

## Existing implementation to reuse

Reuse strict validators from `trusted_ci_policy.py`, independent verification from
`trusted_ci_controller.py`, hard-sized work storage and candidate isolation from
`trusted_ci_sandbox.py`, exact synthetic-merge discovery and review checks from
`trusted_ci_github.py`, and intended-denial probes from
`trusted_ci_qualification.py`. Preserve existing legacy protocol validation.

`autonomy_driver.py` supplies bounded supervision patterns, but an arbitrary
`AGENT_COMMAND` is not the managed runtime. Individual managed tasks do not require
an autonomous work queue. Existing installer hook preservation remains intact.

## Public contracts and persistence

Add `.ai/scripts/managed_authority.py` and stdlib
`managed_authority_protocol.py` with `connect`, `status`, `task start`,
`task status`, `task cancel` and administrator-only `qualify --live` commands.
`connect` opens the service journey or prints its URL for headless use. The
release-configured service endpoint must be independent of candidate content.
Local clients hold only unprivileged short-lived service credentials; use a secure
credential store where available or reauthenticate. No privileged local storage
setup is required. Keep all existing local hooks as fast feedback.

Version `/v1/` HTTP endpoints for connection callbacks, repository discovery,
configuration preview/approval, policy proposal/approval, provisioning status,
tasks, evidence, qualification and signed GitHub webhooks. Internal job, broker
and publication endpoints separately authenticate workload identities. Candidate
requests cannot select authority, installation, bucket, check command, runtime
image or credential permissions. Policies come from human-approved registry data.

Use expiring, server-stored, single-use callback state bound to the authenticated
user and intended installation. Use PKCE where supported, verify current GitHub
user/installation ownership and authorization, and reject replay. Authenticate
browser approval POSTs and require CSRF protection. Verify raw webhook signatures
and deduplicate delivery IDs. A CLI callback must not turn a browser approval
credential into a token available to the coding agent.

Migration `services/authority/migrations/0001.sql` creates tenant-keyed tables for
tenants/users/memberships, installations/connections/callback state, repositories,
desired/effective configuration and consent digests, immutable policy versions
and human approvals, provisioning operations/idempotency keys, tasks/attempts/
leases, evidence, qualification cases, webhook inbox/outbox and audit events.
Use tenant-scoped foreign keys and row-level security. Authenticated membership
determines tenant context, never a caller-provided tenant field. Fence completions
with lease-generation compare-and-swap; stale attempts cannot overwrite evidence.
Record schema versions and transactional migration/recovery behavior. Import
legacy metadata only through explicit migration; never upgrade legacy evidence.

Define a separate managed protocol version 2. Bind tenant, installation/repository
IDs, task/job/attempt/lease generation, head/base/merge SHAs, target, policy digest,
verifier digest, runtime image, authenticated provider execution, limits, times and
complete outcomes. Validate exact schemas, size bounds and artifact digests.
The control plane verifies its own launch records, approved image, current lease
and host identity before signing. EC2 identity or worker-uploaded JSON alone is
insufficient. Candidate containers cannot access report-upload credentials or
controller output locations; only the admitted controller supplies outcomes.

## Automatic provisioning and activation

Reconcile by repository, approved configuration digest and durable operation ID:

1. Authenticate ownership and discover capabilities and current effective controls.
2. Include inherited rules and bypass actors in the proposed change calculation.
3. Display exact changes and obtain explicit human consent and nonempty policy approval.
4. Establish the service check identity and qualification fixtures automatically.
5. Apply approved additive controls, preserving stronger checks and review rules.
6. Read back effective configuration with provisioner privileges.
7. Qualify actual hosted behavior; activate only after every required case passes.

GitHub hides bypass inventory from insufficiently privileged ruleset callers;
the provisioner supplies authenticated readback, not a read-only token's apparent
empty list. See [ruleset API](https://docs.github.com/en/rest/repos/rules).
Interrupted setup resumes from durable state and readback rather than blind replay.
Unsupported account capabilities or inherited constraints produce a blocked state,
never a request for customers to configure GitHub manually.

Bootstrap does not depend on a candidate-editable marker or an already-required
successful check. Establish identity on automatically created disposable fixtures
before requiring it on the target. Never grant temporary coding bypass or weaken
existing protections. If safe bootstrap cannot be established, stop before target
mutation. Final target readback and qualification remain mandatory; a disposable
fixture alone does not prove enforcement on the customer branch.

States are `connected`, `setup`, `qualification`, `active`, `blocked`, `revoked`.
Activation requires completed setup, effective controls, credential separation and
current qualification. Expire active eligibility and bind it to configuration and
authorization generations. Drift, revocation, missing evidence or failed freshness
checks block authorization. Recovery requires renewed readback and qualification.

## Managed task and verification flow

An authorized user submits a bounded task against an allowed repository/base.
The scheduler leases a dedicated coding host and launches the executor session.
Candidate networking permits only required executor endpoints and approved task
services; block instance metadata, broker/control endpoints and unapproved egress.
Export a size/path-bounded patch. The trusted submission service validates it,
creates the task branch/PR and records resulting SHAs; the model has no GitHub token.

A separate verification host runs the pinned independent controller against the
exact synthetic merge, using immutable approved critical checkers and the bounded
candidate sandbox. Tenant-approved checker code also stays isolated from other
tenants and the control plane. The publisher validates managed evidence, current
controls, explicit independent human review and freshly reread bindings before
issuing the required check on the exact merge SHA. Head/base, policy, authorization
or runtime changes invalidate eligibility. GitHub controls the human-authorized
merge; connection consent approves neither future policy changes nor candidate code.

## Ordered implementation slices and failing-closed checks

Every logic slice starts with its named failing test, receives focused validation
and independent review. Unfinished slices stay explicitly unavailable. Commands
below are deliverables, not existing evidence.

1. **Schemas and durable state — R2, R6, R7, R8.** Add backend package/lock,
   `src/authority/{schemas,db,state}.py`, migration and stdlib protocol validators.
   Write rejection and restart tests first. Check real PostgreSQL transactions,
   tenant/RLS isolation, migration recovery, fencing, and malformed/legacy reports.
2. **Infrastructure, broker and executor feasibility — R2, R3, R5, R7.** Add
   `infra/aws/`, Dockerfiles, `broker.py`, `workload_identity.py` and session
   capability preflight. Write scope/escalation rejection tests first. Verify real
   IAM denials and actual runtime identities, restricted executor credentials,
   cross-environment attachment denial, and one real session with cancellation.
   Stop on unavailable provider/account isolation before building dependent flows.
3. **Authenticated customer connection — R1, R4, R7, R10.** Add `api.py`,
   `auth.py`, `github_connect.py`, `webhooks.py`, onboarding templates and client
   `connect/status`. Write callback replay/tenant/CSRF tests first. Browser E2E
   completes standard consent/selection only and rejects altered ownership/replay.
4. **Approved policy and automatic protections — R2, R3, R4, R8.** Add
   `policy_registry.py`, `provisioning.py`, `github_rules.py`, `reconcile.py`.
   Write empty/unapproved policy and interrupted-operation tests first. Real setup
   E2E preserves stronger controls and proves no bypass/marker bootstrap deadlock.
   Framework uses existing obligations; adopters approve pinned nonempty mappings.
5. **Real managed coding — R3, R5, R7, R10.** Add `scheduler.py`,
   `session_coordinator.py`, `agents_provider.py`, `submission.py`,
   `workers/{runner,exec_server_adapter}.py`
   and pinned worker image. Write lease, path, cancellation and permission-denial
   tests first. Real model/executor E2E changes a fixture and produces the expected
   PR. Probe metadata/root-key/cross-tenant isolation and enforced resource limits;
   deny session-creation/inference calls with worker keys, fence reconnects, and
   prove revocation prevents attachment to concurrent and subsequent environments.
6. **Independent verification and publication — R2, R3, R6, R7, R8.** Add
   `verification.py`, `provenance.py`, `publisher.py`; adapt existing helpers.
   Write substitution/stale-attempt/forged-report tests first. Dedicated-host E2E
   accepts correct behavior and denies checker replacement, omitted obligations,
   stale bindings and altered candidate without trusting candidate tests.
7. **Automated hosted qualification — R4, R8, R9.** Add `qualification.py`,
   service-owned fixture creation/cleanup and independently recorded probes.
   Write intended-denial classification tests first. Run valid acceptance, bad
   acceptance, replacement checks, forged evidence, wrong issuer, absent review,
   direct update and stale binding probes. Auth/network errors, outages and skipped
   cases fail qualification; assert the expected denial reason and unchanged refs.
8. **Installed delivery and operations — R1, R8, R9, R10.** Update installer only
   where necessary; add client/installer regressions and operator deployment,
   upgrade, recovery, key rotation, retention and revocation procedures. Write
   compatibility/isolation tests first. A clean installed adopter completes the
   flow without backend dependencies or manual GitHub setup; exercise drift,
   outage, restart, credential revocation and database restore.
9. **AGENTIC activation and frozen gate — R1–R10.** Deploy independently
   administered staging; qualify AGENTIC and a disposable adopter. Obtain
   independent review, freeze the candidate and run the full gate once. Production
   claims require corresponding production evidence; local/staging scope is labeled.

## Validation and evidence

Implement the spec's exact `.ai/scripts/tests/test_managed_authority.py` groups:
`OnboardingConsent`, `ApprovedPolicy`, `CredentialDomains`,
`AutomatedProvisioning`, `CodingIsolation`, `ManagedProvenance`,
`TenantAuthorization`, `EnforcementLifecycle`, `InstalledClient`.
Implement `.ai/scripts/managed_authority.py qualify --live` for R9.
Root acceptance wrappers invoke the isolated backend environment where needed;
they must not silently replace deployed/runtime checks with mocked successes.

Add isolated backend commands:

- `uv run --locked --project services/authority python -m unittest discover -s services/authority/tests`
- `uv run --locked --project services/authority python -m authority qualify-deployment --environment staging`

Retain `python3 .ai/scripts/run_tests.py`, installed qualification, existing
trusted-CI regressions, `python3 .ai/scripts/okf.py records`, and framework parity
CI. Run focused tests during edits, narrow real slice E2E after its edits, then one
full gate per frozen candidate under `.ai/validation-policy.md`. Required hosted
checks fail when unavailable; unit-only suites may be separate, never called live
qualification. Record deployment/tenant/repository identities, source and image
digests, case-specific denials, cleanup results and exact commands/outcomes.

## Documentation and governance synchronization

Update `trusted-ci.md`, implementation status, install/upgrade guidance and new
managed operator/protocol docs in `.ai/docs/`. Describe supported scope, human
approval, local feedback, remote authority and blocked states accurately. Keep
spec acceptance unchanged. Use framework lifecycle/source tooling and Git scratch
receipts; do not create `knowledge/`. Close the retrospective before Verify.
No plan or local test closes the old external-authority deployment gap.

## Operator prerequisites, delivery boundary and risks

Plan approval selects AWS, the separate Python backend, one managed GitHub App and
the self-hosted Codex executor adapter. Operator account/region/domain, deployment
budget and quotas, GitHub App credentials, eligible model account and restricted
environment credentials are deployment inputs. They are once-per-service operator
inputs, never per-customer configuration. Prepare automated infrastructure and
registration tooling before requesting concrete operator actions. Independently
administered control-plane identities remain necessary for the stronger claim.

Provider beta compatibility and environment credential scope are early live
qualification risks, not assumed guarantees. Production activation stays blocked
until these and all external prerequisites are verified. No fallback to a broad
worker credential or manual customer setup is permitted. Other clouds, arbitrary
agent adapters, neutralizing external administrator credentials, automatic review
approval and a general SaaS billing console are outside this implementation.
No deferred component may remain on the critical path of the claimed service.

## Open design decisions

None within this proposed reference architecture. Account-specific deployment
values and live capability results remain explicit execution prerequisites; their
absence must be reported as a blocker, never replaced with a qualification claim.
