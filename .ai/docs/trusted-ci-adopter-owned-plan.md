# Implementation Plan: Automated adopter-owned trusted authority

Status: Approved by the user on 2026-11-07; implementation in progress. Implements the approved
[adopter-owned spec](trusted-ci-adopter-owned-spec.md), R1–R10. No new setup flow
or execution adapter is claimed implemented.

Tier: L2. Persona: Python principal engineer. Preserve Python 3.9 clients,
validate untrusted boundaries, bound subprocess/network operations and test actual
runtime permissions. Delegated planning used the planner role.

Execution constraint, approved by the user on 2026-11-07: continue the remaining
implementation and local verification despite unavailable trusted setup/cloud
accounts. Privileged setup, hosted execution, live qualification, publication and
activation remain blocked in this build. Local fixtures exercise the implementation
without granting hosted qualification or enforcement claims. This supersedes the
earlier callback gate as an implementation stop; it remains an activation gate.

## Objective

Make independent critical verification nearly automatic to install without an
AGENTIC-operated service or infrastructure subsidy. Adopters own their authority,
credentials, resources and usage. AGENTIC maintains the setup tooling and GitHub
Actions, AWS and Azure adapters.

## Success criteria

- R1, R4: Setup completes through authentication, selection and explicit approval,
  without manual resource assembly or secret copying.
- R2: All three adapters deploy into adopter-owned accounts with disclosed
  billable resource types and usage controls.
- R3, R5: Coding cannot access bootstrap credentials, authority write access or
  trusted-check publication capabilities.
- R6, R7: Independent approved policy, authenticated execution and exact revision
  bindings determine eligibility.
- R8, R9: Only current, fully qualified deployments become active; missing
  prerequisites and unexpected denial reasons fail closed.
- R10: Installed hooks remain useful, supported harnesses use adopter model
  credentials, and lifecycle operations preserve unrelated resources.

## Current state

- `trusted_ci_policy.py` validates immutable policy, nonempty coverage and
  separate coding/review identities. Version-1 snapshots are Actions-specific.
- `trusted_ci_controller.py:129` executes independent critical obligations.
- `trusted_ci_sandbox.py:106` enforces Linux OCI, a restricted candidate container,
  pre-provisioned hard-sized disk storage and effective resource controls.
- `trusted_ci_github.py:123` discovers synthetic merges but requires a target
  policy marker; its authority-run, report and publication helpers are reusable.
- `trusted_ci_deployment.py` performs readback and `trusted_ci_qualification.py`
  exercises hosted probes. These modules are under `.ai/scripts/`.
- `.ai/trusted-ci/authority.yml:53` requires self-hosted verification, supports
  polling/manual dispatch, and provides the publisher an issuer App key.
- `.ai/scripts/install.py:21` recursively exports `.ai/`; optional deployment
  dependencies must remain outside that tree.
- `repo.py context --json` confirms framework mode. `okf.py affected` has no
  bundle to inspect; the framework exemption applies. Do not create `knowledge/`.

Existing local and legacy CI evidence does not qualify the new setup flow,
GitHub-hosted verifier or cloud adapters.

## Proposed approach

Use an adopter-owned separate GitHub authority repository as the policy,
scheduling and publication control plane for all adapters:

| Adapter | Verification resources owned by the adopter |
|---|---|
| GitHub Actions default | Fresh standard Linux hosted runner per job |
| AWS | Disposable EC2 host, bounded disk, job-scoped S3 inputs/reports and IAM |
| Azure | Disposable Linux VM, bounded disk, Blob inputs/reports and scoped RBAC |

AWS/Azure provide hosted verification services and execution resources; they
retain the GitHub authority control plane. No central backend or public webhook
server is needed. Existing polling and `workflow_dispatch` discover current PRs.
Dispatch is only a hint; it cannot select commands, policy or credentials. Queue
delays and disabled schedules block stale eligibility rather than authorizing it.
Keep private source, policy and reports private; never publish them for free usage.

New installed stdlib entry points: `.ai/scripts/authority_setup.py`,
`authority_protocol.py`, `authority_status.py`, `protected_task.py`. New optional
deployment package: `deploy/authority/`, with bootstrap, API integration, worker
provisioning, separately pinned dependencies and release artifact. Put AWS
CloudFormation in `deploy/authority/aws/`, Azure Bicep and compiled ARM templates
in `deploy/authority/azure/`. The client obtains a pinned trusted release;
privileged bootstrap never executes candidate-modifiable workspace code.

Generate separate purpose-specific Apps through manifests:

- Administration: approved setup, effective-control readback and repair.
- Issuer: checks-write and necessary read permissions only; its registration
  cannot mint administrative tokens.
- Coding: reduced contents/PR permissions, without administration, trusted checks,
  status publication, independent-review identity or bypass.
- Merge: target-only contents-write/pull-request-read, with a separate key available
  only to the candidate-free broker job. No administration, check/status/workflow
  writing, authority access or acceptance bypass. Humans review; this App performs
  protected merges after fresh authorization, as selected by the user.
- Reader: contents/PR/Actions read only. Implementation refinement: an additional
  purpose App avoids passing an issuer or coding root key into verification merely
  to mint read tokens. This preserves R3's credential separation without a broker
  or secret-token handoff service; it adds one standard consent in the same journey.

The user-selected merger alone receives PR-only bypass on the separate update
restriction, with no acceptance bypass. Store keys only in the authority's secrets; coding has
no authority-repository or secret-administration access. Administrative credentials
appear only in dedicated trusted reconciliation jobs. Publisher and verifier
jobs never receive them. Keep coding App keys outside coding tasks; use reduced
tokens or the trusted submission helper.

Add version-2 deployment and execution contracts without relaxing version 1.
Deployment records bind adapter, account/resources, repository/target, approved
configuration, policy/release pins, App IDs, protection generation, state and
qualification. Execution reports bind head/base/merge, policy, verifier/runtime,
adapter, job/attempt, provider resources, all outcomes and report digest.
Authenticate Actions authority/workflow revision/run/attempt/job and artifact.
Cloud validation additionally checks external launch records, approved image and
configuration, account/resource IDs and job-specific report location via provider
APIs. Uploaded JSON, an instance identity or a local status file alone is insufficient.

Persist setup journals outside coding and in authority-controlled state. Use
operation IDs, conditional updates and generation fencing for recovery/concurrency.
Setup discovers, previews changes/costs, obtains approval, provisions, wires,
qualifies and verifies final target controls. Version 2 stores policy outside the
target; a local marker is informational, removing the bootstrap dependency cycle.
Prove actual manifest callback behavior early; loopback support is a technical
prerequisite, not an assumed capability or excuse for manual key copying.

Protected tasks run the supported harness inside a bounded Linux Docker/Podman
container with copied workspace and fresh filesystem. Do not mount host HOME,
browser/credential stores, authority files, Docker socket or host Git configuration.
The trusted outer launcher owns export, credential admission, submission and task
receipts. Bind receipts remotely to a registered launcher identity whose key is
outside coding; candidate-written files cannot establish isolation. Initially
support the existing Codex CLI execution path with adopter-owned model credentials;
do not add a central model service. Existing unrestricted desktop sessions remain
unverified. Check actual platform isolation rather than equating fresh HOME with it.

## Boundaries and invariants

- Human-approved policy and authority code remain pinned outside candidate control.
- Publishers execute no candidate code and possess no administration-capable key.
- Candidate sandboxes receive neither GitHub/cloud credentials nor metadata access.
- Trusted jobs never evaluate candidate-selected shell, templates, images or scopes.
- Cloud federation trusts the specific authority repository and approved workflow
  context; reject broader owner-wide trust. No static cloud root keys in workflows.
- Each cloud job has its own host/storage namespace; do not reuse hosts across jobs.
- Digest-check inputs, fence report completion and authenticate external launch state.
- Preserve stronger controls and unrelated resources throughout lifecycle operations.
- Setup consent approves neither subsequent policy changes nor candidate code.
- Missing permissions, readback, services or evidence produce blocked status.

## Implementation steps

### Step 1: Versioned setup and adapter contracts — R2, R6, R7, R8

Add protocol validators, deployment records and new `deploy/authority/` adapter
interfaces: discover, preview, apply, readback, execute, qualify, repair, destroy.
First write malformed/unknown-field, substitution, stale-generation and legacy
evidence rejection tests. Verify strict round trips, atomic journal recovery,
concurrency fencing and rejection of forged/incomplete outcomes.

### Step 2: Trusted bootstrap and purpose Apps — R1, R3, R7

Add bootstrap authentication, callbacks and manifest registration modules. First
write callback state/replay/ownership tests. Qualify actual registration,
installation, credential delivery, encryption/wiring and cleanup without copying
keys. Prove issuer/coding registrations cannot mint administration tokens.
E2E: disposable-account guided bootstrap; reject replay, changed account/repository
and wrong origin. Callback feasibility gates dependent onboarding work; no manual
configuration fallback.

### Step 3: Idempotent provisioning and approval — R1, R4, R8

Add authority-repository creation, immutable release installation, approved policy,
rules reconciliation and journals. First write interruption/retry, consent-digest
and stronger-control preservation tests. Read effective/inherited rules with
sufficient privileges, preview exact changes and apply only approved operations.
E2E: interrupt/resume each boundary, preserve unrelated protections and prove no
candidate marker or temporary bypass is needed. Final target readback is mandatory.

### Step 4: GitHub-hosted verification/publication — R2, R3, R6

Update authority template; add trusted disk-provisioning/cleanup helpers. Create
per-job hard-sized ext4 storage with correct ownership on the disposable runner.
Privileged host setup stays separate from candidate execution. Split admin
readback, verification and publication into jobs with distinct credentials.
First write admission and cleanup failure tests. E2E: actual hosted Docker,
cgroup, disk/resource exhaustion, forged reports, candidate tampering and cleanup.
The previous self-hosted runner label does not qualify this path.

### Step 5: Protected coding and submission — R3, R5, R7

Add protected launcher, outer supervisor, registered launcher credentials and
container policy. Reuse bounded supervision without requiring an autonomous queue.
First write credential access, receipt forgery, path escape, scope and cancellation
tests. E2E: an actual supported harness changes a fixture and submits the expected
PR. Probe browser/HOME, metadata, socket, authority, admin and check-publication
access. Reject strong admission for an unrestricted existing session.

### Step 6: AWS self-deployment adapter — R1, R2, R3, R4, R6, R7, R8, R9

Add CloudFormation, OIDC IAM, S3 policies, EC2 launch/provision/cleanup and AWS
provenance validation. Separate deployment/launch/readback/job identities. Hosts
receive only needed object access, no GitHub root key or role-management rights.
Pin launch configuration/image and provision bounded disk before admission.
First write IAM/resource-substitution tests. E2E: deploy to selected adopter
account, complete verification, assert cross-job/object/admin denials and external
launch/report bindings, then clean up after success, failure and cancellation.

### Step 7: Azure self-deployment adapter — R1, R2, R3, R4, R6, R7, R8, R9

Add Bicep/ARM, federation, scoped RBAC, Blob policies, disposable VM provisioning
and Azure provenance validation. Keep deployment/launcher/job identities separate;
implement Azure identity semantics rather than copying AWS assumptions.
First write RBAC/resource-ID/artifact-substitution tests. E2E: deploy to selected
subscription, verify real acceptance and access denials, validate launch/report
bindings and clean up on all exits. If Managed Run Command is used, check actual
execution state, exit code and complete report; provisioning success alone does
not prove checker success.

### Step 8: Status, drift and lifecycle operations — R4, R8, R10

Add setup/status/repair/upgrade/destroy orchestration with adapter-owned inventories.
First write stale-readback, revocation, interrupted-upgrade and foreign-resource
preservation tests. Changes to policy, authority code or protections require
explicit approval. E2E per adapter: drift, rotation, partial loss, repair, upgrade
and teardown. Local cached records never independently establish active status.

### Step 9: Hosted qualification — R4, R8, R9

Extend qualification with automatic disposable repositories, policies and provider
fixtures. First write intended-denial classification tests. Exercise correct and
incorrect acceptance, replaced checkers, forged evidence, wrong issuer, absent
review, direct updates and stale bindings; assert reasons and protected refs.
Where positive behavior needs independent review, present the generated fixture
for explicit human review; never fabricate approval. `qualify --live --adapter all`
requires authenticated current results for all adapters. Missing providers fail.
Aggregate current matching per-adapter evidence without repeating unchanged runs.

### Step 10: Installed delivery and frozen gate — R1–R10

First write installed lifecycle regressions. Preserve local hooks and Python 3.9;
export stdlib clients only and obtain optional tooling by approved release digest.
Update guidance, implementation status, privacy/cost disclosures, recovery and
teardown documentation. E2E: clean installed adopter. Obtain independent review,
close retrospective, freeze candidate, converge and run one full gate. Keep any
unqualified adapter unavailable and accurately labeled; do not declare completion
of this spec until all three are qualified.

## Authorized broker refinement — MERGE-R1–MERGE-R7

The user selected fresh brokered merges on 2026-11-07. This refines the approved
steps above rather than requesting another product approval. The issuer's check
is acceptance evidence, not reusable merge authorization. All live holds remain.

1. **Credential domain — MERGE-R1.** Add the `broker-merge` hold first. Introduce
   a fifth merge-purpose App with contents-write/pull-request-read only, target
   installation and its own secret. Require five distinct prerelease-v2 domains;
   reject older four-domain records without guessing an identity. Bind coding and
   merge bot IDs separately from App and installation IDs; reviewers remain human.
   Extend own-App identity/scope/denial/revocation proofs and the installer.
2. **Host controls — MERGE-R2.** Add a v2 rule validator; retain v1 User-bypass
   semantics unchanged. The sole update exception is Integration=`apps.merge`,
   PR-only. Acceptance has no bypass. Human reviewer checks are separate from both
   bots, and unknown/administrative collaborator grants remain blockers. Do not
   silently disable or qualify target Actions/webhook automation.
3. **Transitions — MERGE-R4.** Prepare exact approved changes; acquire the
   configuration fence before any rule/software/credential/provider side effect.
   Install/read back the new never-reused epoch context and merger-only update
   restriction before activating the registry generation. Keep unrelated stronger
   controls; retire only superseded owned controls after the new gate is effective.
   Tests hold head/base fixed and interrupt each boundary to reject old successes.
4. **One broker handler — MERGE-R3, MERGE-R5.** A separate candidate-free job reads
   current registry, qualification, exact refs, verified/clean evidence, issuer
   check, effective controls, purpose proofs, task admission and independent review.
   Re-read bindings immediately before dispatch; require 60 seconds remaining on
   every expiring proof, 300-second maximum authorization life and readback age at
   most 30 seconds. Send one synchronous merge request with expected head SHA,
   merge method `merge` and HTTP deadline at most 30 seconds. No auto-merge/queue.
5. **Fence and immutable receipts — MERGE-R5, MERGE-R6.** Keep operations beside
   deployment on the same registry branch with admin-only CAS writes. Separate
   stable configuration identity (authenticated deployment blob SHA plus SHA256 d)
   from branch head used for CAS. Fence-only commits change neither deployment
   bytes nor generation. Admin prepare acquires one repository-wide pending fence
   before verification; all configuration-side-effect paths require their own
   configuration fence, so sibling config/merge commits cannot both win. Process
   one candidate per fence. Broker credentials remain source-only plus authority
   read/artifact-runtime capabilities, never authority contents-write. Persist
   operation-specific gate/dispatch/outcome receipts as authenticated immutable
   Actions artifacts; authenticate dispatch intent before HTTP and recheck expiry
   after upload latency. Only admin finalize/recovery clears a terminal fence.
6. **Unknown outcome — MERGE-R6.** Timeout/lost response/cancellation never
   automatically retries or expires/unlocks the fence. Recover read-only from exact
   PR/head and merge commit; compare authorized parents and synthetic tree rather
   than assuming the actual commit SHA equals the synthetic one. An open PR or
   absent artifact is not failure proof. Any later attempt needs a new fence and
   entirely fresh gate. Document bounded pre-request authorization; do not promise
   server-side cancellation or atomic predicates beyond GitHub's head-SHA guard.
7. **Qualification and delivery — MERGE-R7.** Add exact contract entry points,
   local tests and real hosted broker-positive/intended-denial probes for all
   adapters. Test native human/coding update rejection even after issuer success,
   acceptance enforcement against merger, stale/context/expiry/outage failures,
   credential maps, response loss and recovery. Local fixtures never close hosted
   qualification. Privileged setup, publication, broker merges and activation stay
   held until separately authorized prerequisites and real qualification exist.

## Testing strategy

Implement the exact approved acceptance groups in new
`.ai/scripts/tests/test_authority_setup.py` and `test_authority_adapters.py`.
Keep pure-logic/fake tests separate from live browser/GitHub/OCI/AWS/Azure
qualification. Assert effective runtime permissions and final states, not template
existence. Skips and generic authentication/network errors never count as denials.
New logic is test-first; record RED/GREEN evidence through lifecycle tooling.

## Validation commands

Retain `python3 .ai/scripts/run_tests.py`, `python3 .ai/scripts/okf.py records`,
installed qualification, trusted-CI regressions, framework parity and the existing
frozen-candidate process. New commands to implement:

- `python3 .ai/scripts/tests/test_authority_setup.py`
- `python3 .ai/scripts/tests/test_authority_adapters.py`
- `python3 .ai/scripts/authority_setup.py qualify --live --adapter github-actions`
- `python3 .ai/scripts/authority_setup.py qualify --live --adapter aws`
- `python3 .ai/scripts/authority_setup.py qualify --live --adapter azure`
- `python3 .ai/scripts/authority_setup.py qualify --live --adapter all`

Run focused checks during edits, narrow slice E2E after its edits and the full
gate once per frozen candidate under `.ai/validation-policy.md`. Check evidence
reuse before repeating unchanged commands. No new command above is passing evidence.

## OKF impact

Framework mode: update `.ai/docs/trusted-ci.md`, implementation status,
install/upgrade guidance and new adopter/provider/protocol documentation. Keep
receipts in Git scratch; record exact commands/outcomes. Do not create `knowledge/`.

## Dependencies and delivery order

Steps 1–4 establish the common authority. Step 5 establishes protected coding
admission. Cloud adapters depend on reviewed/integrated/focused-tested common
protocol; lifecycle and qualification integrate all three. Deliver one usable
authority outcome in one eventual PR. If implementation is delegated, assign
explicit client/protocol, bootstrap/GitHub, AWS and Azure ownership. Do not mutate
shared accounts/fixtures concurrently. No merge to the default branch.

## Risks and mitigations

- Bootstrap exposure: trusted release outside coding, never workspace authority.
- Manifest callbacks: prove real compatibility before dependent onboarding work.
- Runner differences: assert actual disk/OCI/cgroup admission and fail closed.
- Cloud costs/permissions: preview resources and usage controls; prepare concrete
  deployment changes before seeking account-specific live deployment authorization.
- False isolation: qualify the actual launcher; keep unrestricted agents unverified.
- Outages/quotas: block eligibility, retain recovery state and never silently switch.

## Out of scope

AGENTIC-operated SaaS, subsidized compute, central model gateway, all-cloud
replacement of the GitHub control plane, universal harness support and neutralizing
administrator credentials on arbitrary desktops.

## Open decisions

None. This proposed architecture is ready for plan approval. Live accounts,
permissions, callback behavior and execution capabilities are deployment
prerequisites. Missing prerequisites block qualification; mocks cannot replace it.
