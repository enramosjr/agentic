# Adopter-owned authority: local tooling

The adopter-owned source remains unfinished and unqualified. Its deployment,
qualification, publication, activation, protected-run and brokered merge commands are deliberately
held. Local hooks remain available as fast feedback. No current local status,
fixture, rendered template or cached receipt authorizes a merge.

## Available local surfaces

The installed stdlib client supports these commands without `deploy/`, cloud
SDKs, provider credentials or a model account:

```text
python3 .ai/scripts/authority_setup.py status
python3 .ai/scripts/authority_setup.py plan --deployment deployment.json
python3 .ai/scripts/authority_setup.py verify-local --deployment deployment.json
```

`plan` is a local projection, not a provisioning consent preview. `verify-local`
validates structure and, when a lease/report pair is supplied, their local
bindings. Neither authenticates a provider execution. An `active` field written
into a local document still produces blocked/inactive status.

`authority_setup.py merge` is explicitly held before reading deployment files or
loading credentials. The selected merge contract requires human review followed
by a fresh authorization and one synchronous request from a separate scoped App.
It does not retain an ordinary human merge path based on an earlier check.

The prerelease v2 record now requires five distinct App IDs: admin, reader,
issuer, coding and merge. Four-domain records are rejected. The merger registers
only contents-write/pull-request-read for the target; its PR-only update exception
is separate from acceptance rules, which have no bypass.

The optional backend supports credential-free [infrastructure rendering](trusted-ci-cloud-rendering.md)
and deterministic export of the actual held runtime:

```text
python3 deploy/authority/build_runtime.py --output authority-runtime-held.tgz
python3 deploy/authority/build_bootstrap.py --output authority-bootstrap-held.zip
```

Both refuse existing output. Runtime export includes only selected authority
code and optional independently approved `.ai/trusted-ci/checks.py`, plus a file
digest manifest. The whole runtime digest must match `resources.bundle_sha` in
the independently approved deployment before the worker imports code. Candidate
bytes have their own per-job digest and a separate extraction/mount tree. An
archive checksum alone does not establish a trusted release origin.

The installed stdlib route for `connect` and `setup` selects only a release pin
embedded in an independently reviewed client. It authenticates the GitHub
repository's numeric identity and immutable revision, then verifies the archive
and exact selected file inventory before extracting into native owner-only
storage. It creates an isolated optional Python environment and invokes the
acquired native entry point with fixed command arguments. Candidate deployment
paths, environment overrides and local `deploy/` fallbacks are refused. This
build has no designated trusted bootstrap release, and its operational holds
still run before release retrieval or authentication. A modifying checkout's
client is not a trusted bootstrap: the frozen client and OS context must already
be outside coding-agent access. Protected storage does not establish same-user
coding isolation.

The held `.ai/trusted-ci/authority-v2.yml` has four dispatch modes. The default
`credentials` mode retains the seven independent setup consumers. The `task`
mode prepares one request with the reader identity, authorizes its model lease
in a separate job, then runs coding and administrative controls concurrently.
Only the prepared request flows through job outputs; the controls job receives
the admin key, while coding receives only its coding and model-delivery keys.
Only model authorization has a write-capable workflow token for its encrypted
auth-state journal. Administrative preparation and recovery borrow a separate,
authority-only admin App token for fenced CAS; other workflow tokens stay read-only. Before
loading the source coding key, the task host pulls the authenticated registry's
digest-pinned formatter and coding images with a credential-free engine environment.
Every job checks out the authority revision, never candidate-selected code.
The existing release holds stop all these service roles before input reads or
authentication. Workflow wiring does not qualify execution or activate a service.

The `production` mode discovers one ready protected-task PR and independently
reads its current synthetic merge, retained task and pinned qualification before
an administrative job acquires one merge fence. No candidate number, command,
policy or authority is selected by a dispatch input. Missing retained qualification
blocks this path; the qualification producer remains unfinished.

Administrative preparation reads independent review of the exact candidate head
before collecting retained evidence and again immediately before acquiring its
merge fence. The API must identify the approved reviewer as a human `User`, with
a unique review identity, separate from the PR author and coding actors. Missing,
stale or dismissed approval, an outstanding change request, ambiguous review
inventory or unavailable readback stops preparation without acquiring a fence.
The coordinator only observes reviews; it never submits an approval or requests
review on the operator's behalf. Setup consent cannot approve a candidate.
After an interruption before fencing, preparation rereads current review and
evidence. An already pending fence blocks another preparation. The broker still
performs its own fresh human review readback before dispatch; preparation does
not issue a reusable review authorization.

For the GitHub Actions adapter, verification pulls the approved digest-pinned
image and uses the existing bounded disk, sandbox and host-side controller.
Evidence uploads only after sandbox, disk and temporary-input cleanup succeeds.
It requires a Linux runner with noninteractive root host setup, Docker, cgroup
support, ext4/loop-device tools and sufficient disk. These prerequisites have not
been qualified on hosted runners. AWS/Azure service promotion remains held;
the existing provider modules are not silently substituted for this path.

After verification, five own-App proof jobs and a distinct administrative
`publication controls (PR)` job run separately. Publication authenticates their
closed successful artifacts, task/evidence/qualification bindings and current
refs before the issuer writes its exact check. Its administrative observation
takes at most 30 seconds and remains usable for at most 300 seconds, matching the
preliminary proof lifetime. It cannot be replaced by final broker controls.
This provisional publication window does not extend the final broker's 30-second
readback bound.

After publication, broker, final controls and five final proof jobs start
concurrently. The producers wait for the live broker's authenticated immutable
readiness request. The existing broker session revalidates the completed final
round and dispatches once within its original freshness budgets. Its reader key
supplies source/check reads; its separate merger key supplies only the source
merge token. Neither has authority write access, admin or issuer keys.

The main graph's separate administrative `finalize` job runs after terminal broker
and final producers, including failure paths. It uses `vars.AGENTIC_FINALIZE_PIN`
for its independently approved runtime coordinates. A denied publication still
runs the broker's positive no-dispatch path, so authenticated terminal evidence
can finalize the attempt without a merge or blind retry. Missing positive evidence
remains pending.

The runtime archive also contains `.github/workflows/authority-v2-recovery.yml`.
Its separately dispatched `finalize` job reads `vars.AGENTIC_RECOVERY_PIN`, an
independently approved JSON object with `authority_repository`, numeric
`authority_repository_id`, `workflow` (the recovery workflow path) and immutable
`workflow_sha` (the recovery runtime revision). This is trusted configuration,
never a dispatch input or a pin inferred from today's default branch. The job
authenticates itself before reading the pending registry and can recover after
software drift or deployment expiry. It never dispatches a merge or retries an
uncertain request. Missing/contradictory terminal proof preserves the fence.
The held native setup coordinator now provisions both runtime pins through its
exact approved configuration session. Each value is explicit in the consent
preview and retained before its one possible write. Resume reads back uncertain
writes without repeating them; existing unowned values and drift require repair.

## Provider components implemented locally

- GitHub: marker-free merge discovery, separate purpose-App bootstrap components,
  additive effective-control reconciliation, and approved atomic software
  installation/upgrade/removal with non-forced references, drift refusal and
  preservation of unrelated files. The held native setup composition also retains
  new-resource creation and exact initial software publication in protected local
  storage. Unknown creation cannot be adopted by name; prepared recovery remains
  bound to the original approved release. API-fixture tests cover lost
  acknowledgements. The native operator composes initial installation and
  resumable registration, policy/account selection, scoped configuration fencing,
  existing cloud provisioning, model consent, runtime pins, dispatch locking,
  seven credential consumers and additive source protections. It completes the
  configuration fence only after effective source-control readback, leaving the
  deployment in `qualification`, with enforcement inactive. Real qualification
  and an independently released bootstrap remain unavailable.
- AWS: exact job-scoped STS session policies and presigned S3 capabilities, pinned
  EC2 launch/readback, rejection of unsupported AMI disk mappings, encrypted root
  deletion, lost-launch-response recovery and authenticated owned-volume cleanup.
- Azure: private job-container provisioning, user-delegation Blob capabilities,
  pinned VM/NIC creation and readback, Managed Run Command completion/exit checks,
  no VM identity or public NIC, and authenticated owned-resource cleanup.
- Common worker: digest checks before extraction/import, bounded compressed and
  expanded archives including PAX metadata, link/path refusal, separate trusted
  and candidate trees, sandbox-readable candidate directories, fenced results,
  cancellation handling and refusal to report success before cleanup completes.

These backend components require a trusted caller outside coding access. The
operational hold is a release policy, not a security boundary against source
modification. Inactive public entry points cannot be enabled through a local
environment variable. Internal library fixtures are not deployed enforcement.

AWS signing uses the optional versions in `deploy/authority/requirements-aws.txt`.
They stay outside the recursively exported stdlib `.ai/` client. Azure transport
uses the adopter's Azure CLI login and explicitly ignores ambient storage
connection strings. Job hosts receive expiring object URLs, not cloud identity
credentials or GitHub keys. Those URLs must stay out of logs and coding mounts.

## Verification limits and remaining work

Initial qualification still lacks a complete native execution coordinator.
The qualification receipt reader validates an already active generation and its
authenticated closed receipt; it cannot produce the first qualification. Task
submission/admission and merge authorization also require active state, while
model leases separately permit qualification-purpose execution. Existing App
registrations cover the approved source/authority scopes, not a new trial
repository. The held native `trial_setup.Provision` now provisions a separately
approved disposable pair: a private fixture with frozen seed bytes and an
independent private authority with frozen runtime bytes. It reuses initial
installation and native five-App registration. The existing configuration session
must own both exact `qualification-fixture` scopes while the production deployment
is unqualified `qualification`; every setup API boundary rechecks that same
configuration revision, digest and fence. Pair consent pins ownership, software,
cost ownership and expiry; subsequent App consent pins the newly created numeric
repository identities. All five Apps are newly registered for the disposable pair,
with admin/reader scoped to both and coding/issuer/merge only to the fixture.
Production installations are not extended or borrowed.

Separate protected trial journals retain creation intent, prepared commits and
captured registration responses. Unknown creation is never adopted by name or
repeated; known prepared software and captured callbacks can resume under the
original current consent/fence. The producer returns public identities and exact
origin bindings with `execution_admitted`, `hosted_qualified` and
`enforcement_active` all false. It does not configure trial controls, stage trial
credentials, dispatch a task, submit a review or authorize a merge. This native
composition is in the held bootstrap bundle, not an enabled installed qualification
command. Local API fixtures exercise provisioning and recovery only.

The held `trial_admission.Admission` admits one exact candidate-free qualification
parent and captures the frozen fixture source through the existing bounded Git
object reader. It requires the completed private provisioning journal, an already
configured independent disposable registry in unqualified `qualification`, current
effective controls, five authenticated closed own-App proofs and a separately
authenticated/decrypted qualification-purpose model lease. Critical coverage,
reviewers and model/runtime pins match the approved origin; model authorization
uses a distinct session. Exact execution consent is separate from setup consent.
The retained admission contains public bindings, never a model token or key.
Immutable software and closed evidence are authenticated once per admission or
resume. Capture buffers exact Git bytes between live checks of the original
origin fence, both configurations, source ref, effective controls, parent identity
and expiry. No bytes return if the final check fails. It does not replay dispatch
or mutation.
`Provision.completed()` supplies read-only frozen-pair readback after the trial
registry exists, without replaying initial installation or registration.

The held native `trial_configuration.Prepare(provision).run(approve)` prepares
that completed pair through the existing operator configuration coordinator. It
derives a new setup deployment from the origin's approved critical policy and
model/runtime pins, with the disposable numeric repositories and five own Apps,
a fresh acceptance epoch and separate model authorization. Production model
session/account metadata and credential roots are not copied. Exact policy and
configuration previews require their own consent. The original retained pair,
configuration fence and expiry bracket native transport calls and session checks.
The original origin fence must remain live throughout preparation and recovery.

The shared coordinator creates/authenticates the disposable registry, owns its
configuration fence, prepares runtime pins and dispatch protection, stages all
seven separate purpose credentials, authenticates their closed consumer proofs,
records model metadata only after those proofs, and reconciles effective fixture
protections. Lost secret/consumer-dispatch acknowledgements use the existing
retained consumption proofs, never blind replay. Registry recovery accepts only
the exact retained conditional commit. The completed result is still unqualified
`qualification` with enforcement inactive. Native setup may access separate roots;
this does not make any root available to the coding worker.

The held `trial_worker.Worker` consumes that native retained admission, a separate
fixture-only coding transport, the original encrypted model delivery and exact
prompt consent. It reuses the protected parent's worker measurement, model relay,
protocol, stopped-volume export and confirmed cleanup before any readiness upload
or source write. `trial_controls.Controls.collect` is the separate pinned
`trial_task_controls` administrative job, named `trial task controls (<task_id>)`.
It reads the live parent cleanup artifact, performs real effective administrative
readback and uploads its response; the worker authenticates the closed successful
job. The shared task-control protocol retains its exact nonce/artifact bindings,
120-second readiness limit, original 30-second observation and monotonic budgets.
Only then can the parent submit the exact exported tree to the disposable fixture.
The frozen seed may include the exact owned `.github/CODEOWNERS` path.
Already authenticated configuration/software commits are immutable: hot guards
reobserve their exact live refs and repository identities, retained journals,
original session ownership and expiry. Source mutations additionally bracket the
current source identity/ref with late configuration/software reads. Full live
job/effective-control readbacks bracket execution and submission. Cancellation is
checked through submission and completion, including after blocking readback.

Trial readiness, controls and task artifacts use distinct `trial-task-ready`,
`trial-task-controls` and `trial-task` names. They are not production task admission
or a qualification receipt, and all results retain `hosted_qualified` and
`enforcement_active` false. Protected purpose journals retain exact prompt consent
and known completion without model tokens or delivery keys. Unknown worker,
readiness, administrative-upload or submission outcomes stay pending; this bounded
library never automatically reruns a worker or upload after interruption. A known
completed worker returns its original locator while its admission remains live.
Resolving uncertain intermediate effects is not supplied by this library.

The held `trial_handoff.Native` connects preparation to the Actions
`qualification` mode. Its separately approved prompt digest, exact original
configuration/fence, disposable identities, software/runtime/model pins and expiry
are published through the existing conditional registry writer into immutable
per-task refs in the original authority. The original registry and software refs
remain unchanged. Each record binds its parent instead of its own commit digest;
recovery authenticates the exact conditional commit and unrelated Git entries.
Neither record nor setup consent authorizes candidate review or active enforcement.

`setup.TrialReadStaging` authenticates the original reader App and automatically
stages one expiring token with only `contents:read` on the original numeric
authority repository. Its root stays native. The protected native credential
journal retains the token; public records and outputs contain its fingerprint,
scope and effective deadline. Secret write intent and the workflow run baseline
precede the single possible dispatch to the locked software ref. A closed
`trial handoff` job proves exact token consumption. Native coordination then
publishes the exact run/attempt binding before any model, proof or worker job can
proceed. A lost acknowledgement is observed, never another POST. Missing or
ambiguous evidence remains pending. The effective deadline does not extend the
provider token's expiry or substitute for actual revocation.

`Admission.hosted` authenticates those original-authority records and live fence,
the current disposable configuration, exact pinned job, five closed own-App
proofs and closed decrypted model delivery before using the existing execution
guards. It reconstructs no native Provision or configuration-session object.
The separate `Controls.hosted` observation purpose authenticates the same native
task/consent, closed producers and live cleanup readiness; it receives no model
key and copies no native worker journal across jobs. Immutable artifact metadata
and live producer identity preserve exact nonce/run/attempt/artifact bindings
without repeatedly downloading the same archive. The original 120-second readiness,
30-second observation/write and monotonic budgets remain unchanged.

The fixed launcher supplies each job only its existing purpose credentials and
the consumed origin-read capability. Only the model authorization job receives
the model vault key; the trusted parent outside the container receives the
delivery key. Candidate execution receives only its model relay capability.
Source reads reuse the coding-scoped transport; exact authority metadata reads
use the read-only Actions transport. Admin, reader, issuer and merger roots do
not enter the coding job. Only model authorization may write its encrypted auth
journal through the workflow token.

`Native.observe` authenticates the exact closed task artifact, actual Git parents,
tree, bounded blobs/modes, request marker and exact PR readback under the live
original/trial bindings. Known completion revokes the retained origin token;
staging cleanup remains available after expiry. An absent artifact or open PR
alone never proves failure. Unknown execution, upload or submission remains held
without replay; incomplete intermediate effects are not manufactured into a
completed receipt. Later work needs fresh authorization under a valid fence.

The connected local fixture covers native setup, dispatch, real model encryption,
own-App proofs, worker pipes, relay streaming, independent administrative controls,
exact submission and completed readback. First execution additionally completes
with 100ms transport latency without extending those windows; completed readback
is verified separately without simulated latency. GitHub/OAuth/OCI/kernel/model transports are fixtures;
this does not prove hosted execution or isolation. Ordered qualification cases,
qualification receipt production and external independent human candidate review
remain unfinished. Production task/broker validators still require active
qualification; no state flip or caller JSON can replace those missing producers.
All public operations remain release-held, with no trusted bootstrap release or
enabled installed qualification command. The full case graph and hosted
qualification remain unavailable.

Local broker foundations include a durable operation fence on the independent
registry branch, stable deployment-blob identity separate from branch CAS, scoped
configuration sessions, fresh checks before external mutations and a persistent
history of epoch/check contexts. After activation, reactivation, replacement
qualification and authorization-relevant configuration changes require a fresh
context. The host-transition helper installs both fresh gates, reads back their
effective bodies, retires only the old owned controls, preserves foreign controls
and writes the qualifying record last. Exact commit/readback proof recovers a
lost final acknowledgement without replaying effects. Its production workflow
and activation are still absent.

Dispatch primitives require a create-only authenticated intent before one request,
then recheck the fence, bindings and deadlines. The HTTP child has a total parent
deadline of at most 30 seconds; a timeout cannot retry or clear the fence.
Recovery compares the actual merge's parents and tree with the authorized
candidate, rather than assuming its SHA matches GitHub's synthetic merge SHA.
The artifact-backed receipt store now authenticates the exact pending operation,
pinned broker job/run/attempt, immutable artifact identity, archive digest and
bounded document. Existing dispatch receipts refuse another append even when
bytes match; lost acknowledgements stop before a merge and recovery stays read-only.
Its internal Node uploader uses a locked official Actions SDK and passes only
the runtime artifact capability into the child. Runtime-token injection and the
closed workflow producer contract remain unqualified. A fresh eligibility collector
and broker session now compose authenticated task/qualification/evidence artifacts,
current checks/reviews/refs and readiness-bound administrative controls plus all
five final own-App proofs. Cached App proofs cannot authorize the final dispatch.
The held workflow and service now connect these producers and a separate terminal
recovery entrypoint. Local API/OCI fixtures exercise the composition; this is not
a functioning or qualified hosted merge service.

The terminal recovery helper accepts only positive no-dispatch evidence from a
terminal pinned broker, or an authenticated historical dispatch plus the exact
actual merged PR/parents/tree. A missing artifact, elapsed deadline, open PR or
contradictory receipt leaves the fence pending. Terminal-only Git writes preserve
the deployment and authenticate the exact commit when acknowledgement is lost.
This path cannot dispatch, retry or refresh an authorization; its public entry
remains held.

Parent-side submission helpers validate a bounded plain TAR export without
extracting it, then create/read back the exact Git tree, single-parent commit,
creation-only task branch and PR using the scoped coding identity. Their result
explicitly does not establish task admission. The controlled Codex app-server
helper receives a task capability for a worker-local relay, validates exact
thread/turn completion and retains `model_execution_qualified: false`. The parent
supervisor composes cleanup, readiness and separate administrative readback before
submission. Native onboarding now connects initial ChatGPT-plan consent and
credential-consumer verification; live consent and hosted task qualification
remain unqualified. Encrypted vault/access leases, signature-verified identity,
separate Git auth-state CAS and dedicated-job refresh management have local
fixture evidence. Unknown refresh outcomes remain pending rather than retrying a
grant. No login, credential export or model call occurred.

The relay now supports worker loopback → fixed Unix socket → trusted parent →
public Responses transport. It replaces the task capability with the access-only
credential only upstream, rebuilds headers and bounds requests, traffic, events
and deadlines. Late failure or missing completion cannot produce successful
diagnostic evidence. Direct-execution unprivileged POSIX tests exercise the local
HTTP/socket path and startup cleanup. The actual socket mount, pinned Codex
container, producer integration and hosted model access remain unqualified.

Check-body construction requires the full validated parent execution/cleanup
envelope. Readback requires a unique exact issuer App/context/intent/merge SHA
success within the pending operation's interval. These helpers do not authenticate
the parent artifacts by themselves. The separate held service issuer authenticates
those artifacts and its own closed administrative publication observation first.

Local contracts, clean installed-client checks, extracted-runtime checks and
offline SDK tests do not prove live API semantics, IAM/RBAC, hosted containers
or real cleanup.

Remaining integration includes publishing an independently approved bootstrap
release; complete status/drift/repair/upgrade/destroy and automation migration;
cloud producer promotion; protected-harness
admission and submission qualification; hosted producer/runtime qualification,
host-transition workflow integration; automatic real qualification fixtures; and final acceptance
convergence/review. The new repository software installer does not itself complete
that journey or revoke registered Apps/cloud resources.

Privileged setup, live GitHub registration, all hosted executions, live
qualification, publication and activation remain blocked in this build. Separate
trusted setup and adopter test accounts are required. Adopters own resources and
usage; AGENTIC does not fund or operate a shared service. There is no hard billing
cap, and Azure NAT/public-IP resources can incur idle charges if later deployed.
