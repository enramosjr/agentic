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

The held `qualification_cases.HostCases` library produces the ordered host-negative
prefix from independently prepared, distinct PRs and heads: bad acceptance,
replaced checks, forged records, spoofed source, missing approval, direct push,
new head, new base, policy transition, human update and coding update. It
authenticates closed verifier evidence, actual mutation bytes, prior issuer
successes and exact stale coordinates before making each protected-update request.
The human/coding update probes require current issuer success. App probes reuse
the existing own-App authentication and source-only token mint/revocation path;
only the separate human token uses the authenticated-user endpoint. Candidate
reviews are observed, never submitted or requested.

After the caller retains request intent, the shared probe rereads prior acceptance,
current human approval and other required checks for new-base and policy-transition,
and current acceptance/approval/checks for human-update. The human transport is
reauthenticated after those reads and before the final source snapshot; its identity
must remain the same typed human with a strict positive integer ID. Only an exact
`protected_update` HTTP 403 or 422 counts as a human-update denial. These checks do
not supply native base movement or a native human-to-CLOSED-job observation bridge;
those three native cases remain unfinished.

Each returned observation binds the PR/head/base/synthetic merge/tree, actor,
exact request, HTTP denial and obligation, unchanged protected ref and evidence
digest. A generic error, unavailable credential, skipped obligation, unrelated
required check or moved ref cannot pass. The instance refuses another attempt
after starting, including an uncertain response. This is not durable recovery
across processes: full-prefix native orchestration and retained dispatch intents
remain unfinished. The separate bounded native direct-push/coding-update/missing-approval/bad-acceptance/replaced-checks/forged-records/spoofed-source/new-head
composition below owns durable case intents. Public invocation is held before network access. Local fixtures
exercise verification, cleanup, closed artifacts and publication against existing
synthetic active regression configurations; they do not establish initial trial
qualification. Production active-state and existing qualification requirements
are unchanged.

The held `qualification_broker.BrokerCases` library consumes independently prepared
real broker Sessions and reserved host-prefix coordinates, then executes the
ordered suffix: expired proof, revoked qualification, authority outage, context
transition and positive. It authenticates the actual merger App and source-only
token through the existing mint/revocation path. It reuses the existing fresh
broker, final controls and five final purpose proofs, immutable dispatch/outcome
receipts and actual-commit recovery. The prefix input reserves distinct PRs/heads;
it does not authenticate or execute those preceding host probes. Native full-case
orchestration must supply their actual observations separately.

Only specific measured refusals count: an authenticated issued proof has expired,
the previously authenticated qualification artifact was removed at final readback,
the authority's final artifact inventory returned 502/503/504, or a read-back
configuration and epoch actually changed. Other failures propagate. Negative
results require no merge request and an unchanged target. Stable-context refusals
also require an authenticated positive no-dispatch receipt. A changed registry
cannot authorize an old-context receipt; that refusal leaves the fence held for
independently pinned recovery. Positive results require exactly one synchronous
expected-head PUT, authenticated dispatch evidence, and actual closed merged-PR
readback with parents `[base, head]` and the intended tree. The actual merge SHA
may differ from the synthetic SHA. Unknown acknowledgements never qualify or
authorize a retry. Returned secret-free observations bind the measured identities,
requests, refs, proof/receipt locators, actual commits and evidence digests.

Both libraries are held before transport access and refuse reuse after starting.
Broker receipts also retain the existing create-only dispatch protection; no
durable native full-inventory restart coordinator is supplied. Connected local
fixtures execute the existing verification/publication and fresh-broker graph
using synthetic active regression configurations and modeled host/OCI boundaries.
Those ordered libraries do not themselves integrate initial-trial handoff/worker
admission into the controllers, produce qualification receipts, qualify hosted
isolation or activate anything. The separate native one-candidate composition
below now consumes an authenticated trial through the shared controller path.
The separate native candidate preparer described below does not supply their
completed case inputs. Hosted trial handoff into these controllers, full-inventory
orchestration, qualification receipt production and hosted qualification
remain unfinished; external real candidate human review remains required.

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

The held `trial_candidates.Prepare` native library reuses `Native.observe`'s exact
CLOSED worker/Git authentication and original-token cleanup, then prepares sixteen
distinct PR/head candidates in the fixed host-prefix/broker-suffix order. It copies
only the authenticated exported worker bytes and executable modes, through the
existing source-only own-App proof/token and shared submission controller. The
native administrator observes the existing effective controls before each case;
every mutation retains that observation's original 30-second wall/monotonic budget
and rechecks the original configuration fence, immutable handoff, disposable pair,
trial binding and unchanged seed target. Neither original nor trial registry is
changed, and no review submission or solicitation occurs.

Protected native storage retains the exact handoff/artifact/export binding, ordered
submission requests and per-case pending intent before writes. Resume authenticates
completed candidates read-only. A lost PR acknowledgement can recover the exact
existing PR; an absent branch/PR or unknown intermediate effect cannot authorize a
repeated source write. Missing/changed CLOSED worker evidence, moved bindings,
expired controls and substituted identities fail closed. Partial candidates may
remain on refusal, with their intent held; this is not transactional rollback.

These are candidate reservations with the same worker tree, not completed host or
broker case inputs. Case-specific mutations, prior-success coordinates, ordered
execution and external independent human review remain unfinished. The preparer
itself supplies no trial certificate or qualification receipt; its result explicitly
reports no executed cases, qualification or enforcement.

The held `trial_controller.Native` library selects one exact reservation and
consumes it through the actual shared preparation, verification, issuer publication,
warm broker, final administrative controls, five final purpose proofs, immutable
dispatch/outcome receipts and terminal finalizer. It starts from the authentic native
handoff, CLOSED worker and complete unchanged candidate journal. A distinct native
trial-task envelope binds that worker to this exact candidate's bytes, modes, branch
and PR; it never relabels the worker receipt as a production receipt for another PR.

The protected native certificate binds the original handoff, worker, candidate,
unchanged unqualified deployment, independently observed controls, exact pending
merge operation/sequence and original expiry. Intent is retained before authority
effects. Only the exact retained conditional fence commit permits read-only
lost-acknowledgement recovery; an absent effect never authorizes another write.
Recovery requires the live original native authorization and retained journal;
fresh recovery after their expiry or loss is not established by this slice.
Native observation still requires the original settled trial binding. The case
controller separately authenticates its owned pending fence transition and shares
only immutable worker/Git readback with that observation path.

The production entrypoints retain their ACTIVE state and existing-qualified-receipt
admission. The separate internal trial entrypoint requires an actual authenticated
native or read-only case admission object; caller JSON, a certificate alone or a fabricated active
deployment cannot select it. Both paths share the same controller implementations.
Independent human review is observed before fencing and again by the final broker;
the fixture may model authenticated host review but no coordinator submits or
requests reviews. The final freshness, expiry, single-use and expected-head merge
rules remain unchanged. Positive recovery authenticates the actual closed PR,
merge parents and tree. Withdrawal or stale final readback refuses dispatch;
genuine no-dispatch evidence can finalize, while uncertain effects remain pending
until actual evidence resolves them. Known terminal cases cannot restart.

The native composition retains provisioning/session capabilities in its trusted
process. The separate held `trial_case.Publication` library publishes the exact
pending case, certificate, request and original CLOSED worker through the existing
conditional registry path. It records intent before effects and authenticates the
exact committed parent, message, document, unrelated tree entries and per-task
case ref. Lost acknowledgements recover read-only; absent effects never permit a
repeated write. The original settled binding, owned pending case fence and terminal
transition remain distinct.

`trial_case.CaseReadStaging` shares the existing native reader-App mint/stage/revoke
implementation. Its separate `AGENTIC_TRIAL_CASE_ORIGIN_TOKEN` and protected purpose
journal own a fresh original-authority-only `contents:read` delegation. The revoked
worker token and its old handshake cannot substitute for this capability. A pinned
`trial case handoff` consumer in the already prepared case run produces a distinct
CLOSED artifact. Native binding authenticates its exact case/revision, token digest,
numeric scope, run/attempt and job interval before publishing the case execution
binding. Unknown mint/write/binding effects remain retained without replay.

Each `service.case_producer` invocation reconstructs a fresh read-only `Hosted`
admission from lookup hints, authenticated original/case records, the CLOSED fresh
consumer, original worker/Git evidence and the exact conditional pending fence.
Only existing purpose credentials, read-only Actions access and the new scoped
read delegation enter the role. No native Provision, configuration session,
protected journal, model keys or other role roots cross the handoff. The same
verification, publication, broker, controls, proof, receipt and terminal engines
consume this admission. Terminal recovery uses the existing independently
configured recovery/finalization pin and narrowly scoped administrative writer;
it never dispatches or requires access to the native owner. It still requires
live original authorization, certificate and consumed read delegation. Recovery
after their expiry is not established. Native cleanup can revoke the exact
retained case delegation even after expiry.
The consumed delegation also bounds the broker gate's effective lifetime and
retains the original 60-second dispatch margin. Trial terminal effects recheck
that live admission before every conditional Git write, including after blocking
receipt reads; the ordinary production recovery path retains its existing rules.

The held `trial_launch.Native` supplies exact-case launch coordination through
the same registry, staging, dispatch and producer engines. It conditionally
publishes a separate READY record while the disposable registry is still settled.
That record binds the selected prepared candidate and original CLOSED worker;
it contains no merge certificate or pending operation. The existing reader-App
engine stages the fresh case capability before the single possible workflow
dispatch. Retained publication, mint, secret and dispatch intents precede effects;
unknown outcomes never authorize another write or POST.

The fixed `case` workflow path first closes a `trial case ready` token consumer.
Native coordination authenticates its exact revision, token fingerprint, numeric
scope, pinned run/attempt/job and interval before preparing that real run through
the shared candidate-review and conditional-fence path. The fresh capability's
expiry guards native preparation and each fence write. Human candidate review
is observed externally; the coordinator neither requests nor submits it.
The waiting fixed preparation job then reads the exact pending case and emits
its lookup with the authenticated request. A distinct CLOSED `trial case handoff`
consumer binds that pending certificate, followed by native conditional execution
publication. Producer jobs observe that binding and reconstruct fresh read-only
admissions; no secret is staged after queueing, and the revoked worker capability
cannot substitute for either consumption proof. Missing or ambiguous evidence
leaves retained intent pending without redispatch.

The workflow shares the existing verification, publication, concurrent broker /
controls / five final proofs and independently pinned automatic finalizer jobs.
The native host-negatives, `direct-push`, the distinct reserved `coding-update`
and then `missing-approval`, follow successful
publication with a separate `trial host denial` job. Only that job receives the
selected App key (coding for the first two, merger for `missing-approval`).
The typed scheduling case name must match authenticated case data before App
construction or token minting; scheduling input alone grants no credential authority.
It uses the same `HostCases` probe as the complete ordered prefix,
with actual closed verifier evidence, the exact issuer check, effective obligations
and externally observed independent human review. No human token is needed for
these coding-identity cases. A create-only intent precedes the scoped PATCH of the
protected target to the exact synthetic merge SHA (`force=false`). Unknown effects,
changed target/candidate or any denial other than `protected_update` leave the
fence pending and cannot replay the request.

The missing-approval case still requires independent human approval during normal
preparation and publication. Its later host probe instead requires current approval
to be absent, together with CLOSED successful verifier evidence, the exact current
issuer check and all other effective check obligations. Local connected fixtures
model an external withdrawal after publication; the coordinator never creates,
submits, dismisses or withdraws real reviews. The shared probe rereads these
prerequisites after retaining intent, before sending the scoped merger-App
`PUT /pulls/{pr}/merge` with the exact candidate head and `merge_method=merge`.
Only HTTP 403/405/422 with `required_review`, no denied obligation, and unchanged
candidate/target establishes this negative. It never enters broker merge dispatch.

The closed successful host job retains its exact request, identity, source,
candidate, certificate and denial observation. The broker authenticates that
outcome and emits a distinct trial-only `host-denied` no-dispatch receipt; it never
enters merge dispatch or fabricates a broker failure. This case skips the warm
controls/final-proof rendezvous. The existing independently pinned finalizer
reauthenticates the closed host outcome and broker receipt before recording a
`not-submitted` terminal fence. Production entrypoints reject this receipt without
authenticated trial admission. The complete eleven-case `HostCases.run` contract
remains unchanged. This three-case progression is not that complete ordered prefix.
The automatic finalizer emits a separate `trial-case-terminal` artifact. After
that same-run job closes successfully, the held native
`trial_controller.Native.observe_terminal(prompt,name,locator)` authenticates its
exact request/certificate, pending parent and conditional terminal commit, rereads
the worker/candidate and unchanged target, and retains the closed producer evidence
in the native terminal journal. It borrows and revokes the existing scoped coding
token for candidate readback, and performs no source or registry writes. Missing/unknown
terminal uploads cannot grant local completion or another finalization attempt.

Native finalization retains the exact terminal intent before Git effects. After
an interrupted completion, `trial_controller.Native.recover_terminal(prompt,name)`
only authenticates the retained conditional terminal commit and records local
completion. An absent/different effect cannot trigger another write. This does
not relabel the original settled baseline, clear an uncertain fence or renew an
expired delegation.

The held controller permits `coding-update` only after the exact original
`direct-push` case has an independently CLOSED terminal producer and native
observed completion. The second selection uses the same original sixteen
reservations and CLOSED worker, with a distinct PR/head/task identity. Separate
protected controller, launch, staging and publication journals and separate
READY/pending/execution refs preserve the first case's immutable evidence.
The second handoff retains its predecessor's exact execution revision and
terminal locator. Fresh native and producer contexts authenticate both conditional
transitions, from the original settled baseline to the first pending fence and
then its terminal state, before admitting the second case. Current state cannot
replace that original baseline. The third distinct reserved `missing-approval`
candidate requires both exact predecessor histories and their owned native CLOSED
completions. Both pending/terminal transitions are authenticated from the original
baseline, with distinct journals and immutable READY/pending/execution refs for
all three cases. All three terminal entries remain in fence history.

Before each subsequent queue operation, the same credential engine authenticates
and revokes the exact owned predecessor capability, then mints and stages a fresh capability
in its separate protected journal. Both READY and pending-case consumers must
close for that exact token/candidate/run/job/interval. Neither the revoked worker
token nor either prior case token can authorize the third case. Original ownership,
expiry and total deadline still bound all effects; progression never renews them.
`trial_launch.revoke(provision, token_factory, name='missing-approval')` reconstructs
exact third-token cleanup after expiry or restart.

The fourth distinct reservation, `expired-proof`, requires all three exact CLOSED
terminal histories and owned native completions from that same original trial.
Its separate READY/pending/execution refs and protected journals cannot reuse a
prior case capability. The same staging engine authenticates and revokes the
owned missing-approval token before minting and staging the fourth token. Exact
cleanup remains reconstructible with `name='expired-proof'` after expiry/restart.

The broker keeps its ordinary merger/reader purposes and real warm Session. It
authenticates current verifier/issuer success, independent human approval,
administrative publication observation and initially valid own-App envelopes,
then retains a create-only intent before waiting for actual proof expiry. No
expiry field or original deadline is rewritten. The actual Session must raise
the exact `proof_expired` observation and emit its genuine `not-submitted`
receipt without entering dispatch. A separate CLOSED broker outcome binds the
intent, retained proof bytes and no-dispatch receipt. Missing, unknown or wrong
outcomes leave the fence pending and cannot replay the attempt. The independently
pinned Finalizer authenticates that outcome before its exact conditional terminal
transition; native observation retains the fourth CLOSED terminal entry. Earlier
READY/pending/execution references stay pinned across subsequent effects.
Only this authenticated case's pre-readiness scheduling wait spans proof aging,
bounded by its original consumed capability, certificate, operation and deployment
expiry. The readiness request's 120-second lifetime and final 30-second freshness
remain unchanged. Case-mode broker/concurrent jobs allow ten minutes of runner
scheduling; original authority deadlines still stop them sooner. Production keeps
its original 120-second scheduling wait and five-minute job timeout. When this
broker closes without readiness, concurrent roles refuse the completed broker;
they do not fabricate control or final-proof artifacts.

The fifth distinct reservation, `authority-outage`, reauthenticates all four
exact CLOSED histories and owned native completions from the immutable original
trial. Separate READY/pending/execution refs and journals bind its fresh token;
the staging engine revokes the exact owned expired-proof token before queueing.
Cleanup remains reconstructible with `name='authority-outage'` after expiry or
restart. Prior capabilities cannot authorize its consumers or producers.

This case drives the existing warm Session, concurrent administrative controls
and all five final proofs with the original 120-second readiness and 30-second
freshness bounds. Only the genuine typed `readback_unavailable` from a 502/503/504
at the final authority-artifact inventory can satisfy the named negative. A
successful authorization is refused before dispatch; wrong failures cannot
produce its named outcome. A create-only intent precedes the attempt. The CLOSED
broker outcome binds the exact collection inputs, observed failure, unchanged
before/after snapshot and genuine no-dispatch receipt. After readback recovers,
the pinned Finalizer revalidates those inputs at their original timestamps
through the shared collector. Historical job admission requires this exact
authenticated CLOSED Session receipt; it cannot start a broker or extend any
authority. Missing, unknown, substituted or still-unavailable evidence leaves the
fence pending. The final source snapshot follows blocking admission reads before
terminal effects, and native observation retains all five exact history entries.

The sixth distinct reservation, `bad-acceptance`, authenticates all five exact
CLOSED histories and owned native completions against the immutable original
trial. Separate journals and READY/pending/execution refs retain the original
owner, expiry and deadlines. The existing staging engine revokes the exact owned
authority-outage token before staging the fresh sixth origin-read capability and
queueing. `trial_launch.revoke(..., name='bad-acceptance')` reconstructs cleanup
after expiry or restart. Earlier capabilities cannot authorize this case.

Only authenticated `bad-acceptance`, `replaced-checks` and `forged-records` cases may retain the pinned verifier's failed first policy
criterion through `negative_evidence`; cleanup and exact execution provenance must
still validate. Its mutations are derived from the immutable exported worker bytes
and checked against the actual candidate and baseline. The successful evidence
producer job means the observation was retained, not that acceptance passed.
Normal independent human review, all five preliminary own-App proofs, task binding,
certificate and closed publication observation remain required. A create-only
issuer intent precedes the unchanged success-only publication engine. Only that
engine's actual failure for the named criterion produces the distinct CLOSED
`trial-publication-denial` artifact. Unexpected publication, other failures and
unknown acknowledgements cannot count or replay.

The separate merger-App host job authenticates that issuer refusal and uses the
shared `HostCases._probe`, rereading failed evidence, actual mutation bytes,
independent human approval and other required checks after durable host intent.
Only HTTP 403/405/422 with `required_check` for the exact issuer obligation and
unchanged candidate/target establishes this negative. The broker emits the
existing exact `host-denied` no-dispatch receipt; warm final-proof jobs are skipped.
Generic Session no-dispatch evidence cannot close any selected named host case.
The pinned Finalizer reauthenticates the named evidence and checks the final source
snapshot after blocking admission reads, immediately before terminal effects.
Native observation retains all six exact histories without qualifying the trial.
Missing or substituted evidence and moved predecessor refs preserve the fence.
Positive verifier, issuer and broker consumers retain their success requirements.

The seventh distinct reservation, `replaced-checks`, reauthenticates all six exact
CLOSED histories and owned native completions against that same immutable original
trial. Its separate journals and READY/pending/execution refs preserve the original
owner, expiry and deadlines. Staging revokes the exact owned bad-acceptance token
before minting the fresh seventh origin-read capability and queueing. Original
worker and earlier case capabilities cannot authorize the seventh consumers.
`trial_launch.revoke(..., name='replaced-checks')` reconstructs cleanup after expiry
or restart.

This case reuses the failed-verifier, strict issuer refusal, shared host probe and
pinned Finalizer path above. The shared mutation validator additionally requires
an actual changed candidate file under `.ai/scripts/tests/` or `.github/workflows/`,
bound to bytes from the original CLOSED worker export and actual baseline. The
binary-only default fixture cannot establish this negative. The local connected
fixture opts into hostile checker/test bytes before the original worker closes
and before all sixteen reservations; no candidate, tree, baseline or earlier
artifact is retrofitted. Its permissive candidate lifecycle command still fails
the actual pinned controller's denial assertion. Native CLOSED observation retains
all seven histories; positive consumers remain success-only.

The eighth distinct reservation, `forged-records`, reauthenticates all seven exact
CLOSED histories and owned native completions against the immutable original
trial. Separate journals and READY/pending/execution refs retain the original
owner, expiry and deadlines. Staging revokes the exact owned replaced-checks token
before minting the fresh eighth origin-read capability and queueing. Original
worker and all seven earlier capabilities cannot authorize the eighth consumers.
`trial_launch.revoke(..., name='forged-records')` reconstructs cleanup after expiry
or restart.

The same failed-verifier, strict issuer refusal, required-check host denial and
pinned Finalizer path requires an actual changed candidate file under
`knowledge/history/lifecycle/`, checked against the exact head and baseline.
The local connected fixture adds attempted forged lifecycle approval/PASS bytes
only inside the initial worker export, before closure and all sixteen reservations.
They remain untrusted candidate attack input; they never become native records,
task evidence, authority receipts or qualification. Replacement-only export cannot
establish this case. Native CLOSED observation retains all eight histories and
leaves the original trial unqualified. Positive consumers remain success-only.

The ninth distinct reservation, `spoofed-source`, authenticates all eight exact
CLOSED histories and owned native completions against the same original trial.
Staging revokes the exact owned forged-records capability before minting the ninth
origin-read capability and queueing; the worker and all eight earlier capabilities
cannot authorize its READY, handoff or producers. Separate journals and all prior
READY/pending/execution refs retain their original owner and deadlines. Named
cleanup remains reconstructible after expiry or restart.

This case uses the shared host probe's actual source-check prerequisites: a
completed successful foreign-App check with the exact context and synthetic merge,
absence of authoritative issuer success, independent human approval and every other
required obligation passing. Its publish job authenticates the genuine task,
certificate, preliminary App proofs and CLOSED publication controls, then retains
a named source observation after durable intent. Acceptance verification is not a
prerequisite for this source-spoof attack; its current observation phase skips the
scheduled verifier, as does the current new-head phase described below. Historical
new-head preparation still verifies. The spoof phase neither manufactures verifier success nor invokes normal issuer
publication. The success-only production verifier, issuer and broker remain strict.

The separate merger-App host job rereads prerequisites after its durable intent
and counts only the exact required-check HTTP 403/405/422 denial. CLOSED readers
authenticate both named observations, job intervals and intents; the pinned
Finalizer requires the exact `host-denied` receipt. A generic Session no-dispatch
receipt cannot close this named case. Native CLOSED observation retains all nine
histories and leaves the original trial unqualified. Local hostile source checks
enter only the existing source API fixture, never trusted role or task artifacts.

The tenth original reservation, `new-head`, uses a separately journaled historical
preparation on the same PR. The native owner captures the exact frozen source-base
tree as the old verification fixture; this is not another model result. It appends
that tree to the reserved branch, runs the actual pinned verifier and success-only
issuer, and retains CLOSED old acceptance with its exact task, operation, synthetic
merge and issuer coordinates. Historical preparation cannot dispatch: the existing
Session exception path emits its no-dispatch receipt and the pinned Finalizer
closes that separate operation. Its conditional terminal commit becomes part of
the current case baseline without becoming another host-case history entry.

The current phase appends the original CLOSED worker tree after the old head.
Both source changes use exact expected-old-OID atomic updates, preserve file modes,
and retain protected intent before effects. Unknown effects permit only exact
read-only recovery. Original reservation/worker evidence remains unchanged. Fresh
READY, pending and execution bindings use distinct phase refs and capabilities;
the prior capability is revoked before current staging. The current host producer
reauthenticates genuine same-PR old success, current human approval and every other
obligation, and requires absence of current own-App success. Only the exact issuer
required-check denial and named `new-head` outcome can close it. The original
deadlines, all nine predecessor histories and their 27 refs remain binding.

This ten-case progression is a bounded prerequisite, not the complete ordered
eleven-case host prefix, five-case broker suffix or qualification.
In particular, initial-unqualified revocation remains unimplemented; an ACTIVE
qualification receipt cannot substitute for that design.
The launcher passes only the fresh read capability and each role's existing
purpose credentials; READY/preparation/consumer jobs receive no App root or model
key. The terminal job can close a failed broker's genuine no-dispatch receipt or
authenticate actual merge parents/tree after a lost merge acknowledgement.
`trial_launch.revoke(provision, token_factory)` reconstructs native cleanup from
the actual provisioning owner and protected launch/staging journals, using the
same exact retained-token revocation engine after expiry or coordinator restart.
It does not require a live case admission, mint, restage or dispatch. The
source/local fixtures model queued jobs and CLOSED artifact
transport. They do not establish separate hosted processes or credential isolation,
and no real workflow is dispatched by this build.
Local fixture execution drives authenticated job/closed-artifact readers,
actual App proofs, verifier cleanup, effective controls and the actual merge
request encoder, with GitHub/OCI/kernel/model boundaries modeled. It establishes
neither hosted execution/isolation nor qualification. The bounded controller
does not prepare the case-specific mutations or coordinate all sixteen probes.
Full-inventory workflow coordination, case-specific mutations and ordering,
qualification receipt production and final hosted qualification remain unfinished.
Trial and original deployments
stay unqualified; `qualification_record` remains a strict reader. No complete
original requirement, trusted release, activation or enforcement is claimed.

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
