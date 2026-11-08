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

The held `.ai/trusted-ci/authority-v2.yml` has two dispatch modes. The default
`credentials` mode retains the seven independent setup consumers. The `task`
mode prepares one request with the reader identity, authorizes its model lease
in a separate job, then runs coding and administrative controls concurrently.
Only the prepared request flows through job outputs; the controls job receives
the admin key, while coding receives only its coding and model-delivery keys.
Only model authorization has a write-capable authority token for its encrypted
auth-state journal; the other jobs retain read-only authority access. Before
loading the source coding key, the task host pulls the authenticated registry's
digest-pinned formatter and coding images with a credential-free engine environment.
Every job checks out the authority revision, never candidate-selected code.
The existing release holds stop all these service roles before input reads or
authentication. Workflow wiring does not qualify execution or activate a service.

## Provider components implemented locally

- GitHub: marker-free merge discovery, separate purpose-App bootstrap components,
  additive effective-control reconciliation, and approved atomic software
  installation/upgrade/removal with non-forced references, drift refusal and
  preservation of unrelated files. The held native setup composition also retains
  new-resource creation and exact initial software publication in protected local
  storage. Unknown creation cannot be adopted by name; prepared recovery remains
  bound to the original approved release. API-fixture tests cover lost
  acknowledgements. Full guided setup and credential staging remain unfinished.
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
The separated workflow graph and administrative recovery wiring remain missing,
so this is not a functioning hosted merge service.

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
submission. Guided onboarding, initial ChatGPT-plan consent and hosted task
qualification remain unfinished. Encrypted vault/access leases, signature-verified identity,
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
the parent artifacts by themselves and never publish a check.

Local contracts, clean installed-client checks, extracted-runtime checks and
offline SDK tests do not prove live API semantics, IAM/RBAC, hosted containers
or real cleanup.

Remaining integration includes resumable registration recovery; connecting the
independent policy/release registry, separated Actions jobs and all adapter
operations into the complete onboarding/lifecycle journey; protected-harness
admission and submission integration; broker receipt/runtime wiring,
host-transition workflow integration; automatic real qualification fixtures; and final acceptance
convergence/review. The new repository software installer does not itself complete
that journey or revoke registered Apps/cloud resources.

Privileged setup, live GitHub registration, all hosted executions, live
qualification, publication and activation remain blocked in this build. Separate
trusted setup and adopter test accounts are required. Adopters own resources and
usage; AGENTIC does not fund or operate a shared service. There is no hard billing
cap, and Azure NAT/public-IP resources can incur idle charges if later deployed.
