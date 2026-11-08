# Trusted CI implementation status

Status: Adopter-owned implementation in progress on `codex/trusted-ci`; not ready
to ship. External enforcement has not been activated. The earlier frozen gate and
9/10 original-spec result below apply to legacy checkpoint `f7b588e`, not the new
adopter-owned implementation. The user approved the adopter-owned spec and plan.

## Latest bounded continuation — 2026-11-08

The user requested a committed draft PR checkpoint for later resumption.
Implementation is preserved in `9164aca`; the [PR resume note](trusted-ci-pr-resume.md)
records publication scope and the unfinished integration with newer `main`.
Earlier statements that the current work is uncommitted are historical.

The [local task-controls checkpoint](trusted-ci-task-controls-local.md) supersedes
the handoff's missing-module/task-authorization status. It adds cleanup readiness,
separate complete administrative observation, exact artifact/nonce/request/export
bindings and original thirty-second mutation authorization. The candidate-free
admin producer alone receives source administrative visibility; coding never does.
Monotonic budgets prevent clock rollback from extending observation or writes.
The runtime inventory includes the new module and its extracted task path imports.

Installed remote commands now refuse absent coordination independently of release
holds, and framework CI invokes the optional real-crypto task-service contracts.
These changes do not supply the missing production workflow or onboarding journey.

The inherited `adopter-framework-integrated` gate timed out: supervisor marker 1,
lifecycle exit `None`, empty buffered suite output. It supplies no full-suite PASS.
No duplicate gate was launched. The current local slice's exact evidence and
remaining work are in the checkpoint; full-feature Review/Verify remain open.
The final packaged backend aggregate and optional-crypto service contracts passed
on tree `9281b9e`; independent review approved only this bounded local slice.

## Earlier continuation — 2026-11-08

The working tree remains unfinished and uncommitted. Privileged setup, hosted/live
qualification, publication, activation and merges remain held. No cloud account or
trusted bootstrap context has become available.

- `service.py` discovers the authority only from admitted Actions repository/ID,
  the fixed registry branch and current software pin. Public identity JSON is read
  from that pinned deployment; its strict schema and digest are checked.
- The separate `authority-v2.yml` currently implements seven isolated setup
  consumers only. The fixed Node launcher passes each Python child its selected
  credential; the artifact child receives only upload capabilities. Production and
  task workflow modes are still unfinished. The v1 workflow is unchanged.
- Ledger `adopter-credential-service` passed on tree `a44961d`: ten SDK methods
  using actual RSA signatures, encrypted model records and protected journals over
  synthetic native/Git/Actions endpoints. All seven consumer paths now pass through
  the service, upload a closed proof, and require authenticated local acceptance.
  This remains local fixture evidence, not secret staging in GitHub.
- Registration now captures returned App keys durably before browser return or
  installation. Unknown exchanges cannot be repeated/adopted by name; a captured
  response can recover without a second exchange. Independent review caught an
  unsupported `workflows: read` probe request. Its actual-install regression failed
  first, then passed with minimal `contents: read`, complete installation inventory
  and revocation. The correction was re-reviewed without further findings.
- The managed worker has a bounded source bootstrap, pinned binary/version checks,
  a minimal child environment and bounded stdio forwarding. A real unprivileged
  POSIX subprocess fixture completed the protocol, used the loopback/Unix relay
  with a synthetic model stream, edited files and exported exact bytes. This does
  not qualify an OCI worker, model entitlement or complete task supervision.
  Export scan errors and mutable-container-name cleanup were corrected through
  RED/GREEN regressions; the full parent supervisor remains unfinished.
- The deterministic held runtime now includes explicit controller/worker dependency
  sources, locked artifact SDK metadata and the fixed credential workflow. An
  extracted-artifact regression passed before subsequent cloud-source changes;
  the final integrated archive still needs its current verification.
- Native cloud provisioning composition is under review. Pending findings require
  immutable AWS update identity, request-specific terminal completion, and separate
  durable Azure group/deployment phases. Its earlier local fixture passes are not
  completion evidence for those boundaries or hosted qualification.
- Isolated Driver regression `adopter-driver-isolated` ran 58 tests in 1577.178s
  and failed three. A retained trace exposed a clock-origin mismatch between CLI
  startup and the actual run deadline. A deterministic three-second pre-CLI delay
  reproduced it (19.5076s against 17s); the corrected observer passed that same
  control while preserving real budgets, inner timings and descendant checks. A
  subsequent class diagnostic retains complete output; the full gate is still open.

Framework mode continues to use these existing documentation locations and Git
scratch receipts. `okf.py affected` reports no OKF bundle; none was created.

## Adopter-owned checkpoint — 2026-11-07

- Added strict v2 deployment/execution contracts, generation-fenced local journals
  and marker-free exact merge discovery while preserving legacy v1 validators.
- Added human-side manifest registration, separate purpose Apps, explicit token
  downscoping, credential wiring and a registration/installation preflight. This
  is not yet full onboarding, protection reconciliation or resumable recovery.
- An independent scoped review found coding-authority access, subprocess exposure
  of manifest conversion codes, and generic-422 denial acceptance. Corrections
  use a separate private coding fixture, in-process HTTPS redemption, specific
  denial categories, and explicit authority-access probing. Fixes were re-reviewed;
  that scoped approval is not final feature or lifecycle approval.
- Added AWS CloudFormation and Azure ARM template generation, ownership/cost
  previews, account verification, provisioning/readback and teardown boundaries.
  Additional execution and object-transport components are described below. The
  integrated hosted journey, complete lifecycle and real IAM/RBAC qualification
  are not verified as supported adapters.
- `lifecycle.py run adopter-foundation-contracts --inputs ... -- python -m unittest discover -s .ai/scripts/tests -p test_authority_*.py`
  → PASS on tree `e8fe749`. These are local contracts, not the spec's hosted
  acceptance groups. Mocked groups deliberately use different names so convergence
  cannot mistake their PASS for complete onboarding or deployed enforcement.
- `lifecycle.py run adopter-host-disk-probe -- wsl -d podman-agentic-trusted-ci -u root -- python3 /mnt/c/Users/enram/Projects/agentic/deploy/authority/host_probe.py --runtime podman --image docker.io/library/python@sha256:2784af835b90070d9d37d3aa5aa01a3e825d88436b0d58f7776d2cdcb6780f9e`
  → PASS on tree `54eee32`: actual bounded ext4 writes, expected oversized-disk
  refusal and work-volume cleanup. The initial run failed because the backend
  lacked `mkfs.ext4`; a digest-pinned unprivileged formatter container corrected
  that prerequisite without changing the backend OS. This is local host admission,
  not GitHub-hosted or cloud qualification.
- The user confirmed that no AWS/Azure test accounts are available. No cloud
  resource was created and neither adapter is qualified.
- The user also confirmed that no trusted bootstrap context is available.
  Privileged setup cannot run in this modifying-agent session, and another
  terminal/container controlled by this session is not a substitute. The real
  GitHub bootstrap gate remains blocked; no additional setup approval is pending.
- Independent work continued on a credential-free AWS/Azure renderer at
  `deploy/authority/render_cloud.py`. Its real CLI tests pass without credentials
  or provider tools, verify payload checksums, preserve existing output and reject
  invalid configuration before creating files. A scoped independent review approved
  only that rendering slice, not deployment or the full feature.
- Offline AWS validation with `cfn-lint==1.60.0` initially reported W3011: the
  shared OIDC provider lacked replacement retention. The focused regression was
  recorded RED/GREEN; both retention policies are now present. Ledger label
  `adopter-aws-template-lint` → PASS on tree `06a0602`, rendered template SHA-256
  `535f1f3f8218208a6f876ea02f1a421b1550031586c5f54b2444116cbf9309f3`.
- Offline Azure decompilation and compilation with checksum-verified Bicep 0.49.2
  → PASS (`adopter-azure-template-decompile`, `adopter-azure-template-build`).
  That Azure output remained byte-identical after the earlier AWS-only correction:
  SHA-256 `5a8bd70fa8da44e7b6cf6ecd954bbb68beec05860d2fc0309c8b2f3250f78985`.
  No Azure login, deployment or permission test occurred.
- The user subsequently authorized continued implementation/local verification,
  while explicitly holding privileged setup, hosted execution and live
  qualification. The callback gate remains an activation gate, not a source-work
  stop. The original preflight ZIP is obsolete; the [guide](trusted-ci-bootstrap-preflight.md)
  now describes the operational holds rather than directing setup here.
- Added fixed release holds before public live entry points, a stdlib installed
  status/plan/local-validation client, additive protection reconciliation, and
  a transactional authority-software installer supporting approved upgrade/removal
  without overwriting unrelated files. This is not complete onboarding or teardown.
- Added short-lived job leases, deployment-approved runtime bundle digests,
  separate candidate hashes, AWS exact-object STS/S3 capabilities, Azure
  user-delegation Blob capabilities, and provider-account/resource-scoped transport.
- Added disposable EC2 and Azure VM/NIC execution, external launch/program/image
  readback, bounded result validation, cancellation and cleanup. EC2 lost-response
  recovery is scoped by idempotency token and ownership tags; root disks force
  deletion and leftovers are authenticated/removed. Azure completion requires
  actual Managed Run Command success and exit zero, not provisioning success.
- Added a standalone worker and deterministic held runtime export. Archive limits
  include total decompressed metadata, links/escapes are refused, and candidate
  directory modes permit sandbox UID access while authority/enclosing roots stay
  private. These source paths have local contract evidence, not hosted proof.
- Independent review found and corrected bundle substitution, lost EC2 launch
  acknowledgement, compressed PAX metadata expansion, sandbox directory
  permissions, inherited EBS retention, a fake-only transport keyword and Git-tree
  ancestor/descendant collisions. Each has failing-before/passing-after evidence.
  The [final narrow report](trusted-ci-adopter-local-review.md) approves only the
  EBS/installer corrections and explicitly withholds overall/hosted approval.
- `lifecycle.py run adopter-local-contracts --inputs ... -- python -m unittest discover -s .ai/scripts/tests -p test_authority_*.py`
  → PASS on tree `2216002`: 90 tests, one POSIX-only test skipped on Windows.
  The first integrated run failed because its new installer fixture lived under
  lifecycle's Git scratch without its own repository. A deterministic reproduction
  failed for that reason, then passed after initializing the isolated adopter
  repository; the integrated suite subsequently passed. Two earlier diagnostic
  invocations failed for tooling reasons and are not counted as valid RED proof.
- `lifecycle.py redgreen green -- wsl -d podman-agentic-trusted-ci -u root -- runuser -u nobody -- /tmp/agentic-authority-cfnlint-160-20261107/bin/python /mnt/c/Users/enram/Projects/agentic/.ai/scripts/tests/test_authority_worker.py`
  → PASS, four tests with no skips as the unprivileged `nobody` UID. No container,
  loop device, filesystem mount or backend package setup occurred. The preceding
  valid RED showed the candidate-root mode was 0700 instead of 0755; an earlier
  direct WSL `-u nobody` launch failed at account startup and was not accepted as
  that reproduction.
- `lifecycle.py run adopter-aws-offline-signing --inputs ... -- <isolated-python> deploy/authority/test_aws_signing.py`
  → PASS on tree `a061344`, using pinned real boto3/botocore and synthetic
  credentials without network/provider calls. The deliberately broken path-style
  variant is rejected by the same worker URL contract. Dependencies are pinned
  outside `.ai/` in `deploy/authority/requirements-aws.txt`.
- Updated AWS template `dd6d67a673a87fc7ca9a2e21619b58a680561d363cce503e4c21d004a2e6c55d`:
  `adopter-aws-template-lint` → PASS with cfn-lint 1.60.0 on tree `8b9af71`.
  Updated Azure template with private jobs container
  `9e67f6d342a50254e1a0c48f0f076bae4ed433ef42c674431fd877a17d1b83f5`:
  `adopter-azure-template-decompile` and `adopter-azure-template-build` → PASS
  with Bicep 0.49.2. Both are offline validation, not deployment evidence.
- Full onboarding, protected-task admission, integrated cloud execution/delivery,
  complete acceptance convergence and the new frozen-candidate gate remain pending.
  No final Review/Verify/Ship completion is claimed. Unfinished source remains
  uncommitted; unrelated POSIX-hook worktree files are not part of this change.

### Continued local integration

- Azure cleanup was refined after deterministic stale-inventory failures. The
  [phase plan](trusted-ci-azure-cleanup-plan.md) separates fresh ownership capture,
  one blocking provider deletion and identity-only absence polling. Unknown
  completion stays pending; child-not-found cannot mark a parent absent, and
  replacement resources are not deleted. [Independent scoped review](trusted-ci-azure-cleanup-review.md)
  approved the correction after 20 cloud-execution and 3 transport tests passed.
  Azure GETs use fixed-endpoint, subscription-scoped bearer headers and distinguish
  authenticated `ResourceNotFound` from generic/authentication errors. No live call ran.
- Fourteen optional backend test modules moved to `deploy/authority/tests/`.
  The two spec entry paths remain import-safe dispatchers, without aliases from
  local contracts to hosted acceptance groups. Installed discovery without
  `deploy/` now passes; named unavailable hosted acceptance commands fail explicitly.
  The [packaging review](trusted-ci-adopter-packaging-review.md) approved only this boundary.
- Split local gates `adopter-client-contracts` and `adopter-backend-contracts`
  → PASS on tree `c83d19a`, subsequently confirmed REUSE before later source
  additions. Backend validation uses ordinary unittest discovery, not the parallel
  runner's resume cache. Later registry/provenance changes still need the next
  integrated local run; the earlier PASS is not silently upgraded to the current tree.
- Source CI now has a required backend job on Windows/Linux × Python 3.9/3.15,
  with offline real-SDK signing on 3.15. `adopter-backend-ci-gate` → PASS on tree
  `6f60614`: unprivileged Linux execution of the actual Bash summary rejected
  every non-success dependency combination, including a missing backend result.
  The expanded remote matrix has not been run or published.
- Added the separate-branch registry CAS journal. It keeps policy outside its own
  pinned software commit, rejects software drift, bounds serialized writes before
  mutation, verifies regular Git mode and blob identity, preserves ancestor paths,
  and fences concurrent divergent updates. Seven local tests pass; the
  [registry review](trusted-ci-adopter-registry-review.md) grants only scoped approval.
- Added v2 parent-artifact authentication and cleanup envelopes. Eight local tests
  cover workflow/run/attempt/job/role substitution, cloud-parent envelopes, ZIP
  safety, timestamps and a bypassed-verification negative control. These helpers
  are not yet a complete runtime service or publisher.
- Added read-only v2 control facts and own-App capability proof components.
  Human collaborators and coding bots are checked separately. Token scope,
  registration/accepted permissions, intended denials, authority exclusion and
  probe-token revocation are locally exercised. Administrative observer tokens
  now include necessary Webhooks read permission; Webhooks write remains denied.
  Capability proofs explicitly retain `isolation_established: false` and contain
  no credentials. Managed-task admission remains independently required.
- R3/R5 also cover indirect candidate execution through privileged target
  automation. Current readback conservatively blocks unqualified enabled Actions
  or active webhooks. It does not disable either. Any future mitigation needs an
  exact approved preview and must preserve required-check dependencies; local
  tests do not qualify a strategy or authorize remote mutation.
- Two broader script-regression attempts were deliberately stopped when confirmed
  Azure source defects invalidated their candidates. Neither supplies a PASS.
  The broader local gate remains pending until the next source candidate is frozen.
  No privileged setup, live qualification, publication, activation or default-branch
  merge occurred. All operational holds remain in place.

### Fresh brokered merge refinement

The user selected fresh brokered merges on 2026-11-07. The approved spec/plan
now include MERGE-R1–MERGE-R7; refreshed intent/plan approvals are recorded as
`human:enram`. No operational hold was lifted.

- Added an explicit `broker-merge` hold and installed `merge` command that refuses
  before reading deployment/credentials. Five distinct purpose Apps are now
  required; prerelease four-App documents fail closed. The merger is target-only,
  contents-write/pull-request-read and independently probed for prohibited scope.
- Added a v2 rules validator with the merger Integration/App ID as the sole
  PR-only update exception. Acceptance bypass stays empty; legacy v1 human-bypass
  validation remains unchanged. The independent fifth-domain review found no
  findings in that narrow scope; it did not approve the complete broker.
- Registry bindings now distinguish authenticated deployment blob SHA plus
  deployment digest from branch head used for CAS. A durable admin-owned fence
  serializes configuration and merge attempts; fence-only commits preserve
  deployment bytes/generation. Expiry and unknown results do not unlock it.
- Configuration sessions bind scope, owner workflow/run/attempt, sequence,
  deadline and expected progress. Established software/control/cloud mutators
  refuse missing sessions before external effects. Preview no longer creates a
  rule nonce. Registry writes recheck freshness before each Git effect, including
  the final ref update; a slow upload cannot authorize an expired update.
- Persistent epoch/check history forbids reuse after activation. Inactivation
  preserves that history; reactivation and replacement qualification require a
  fresh context. A local host-transition helper now installs/read backs the gates;
  production workflow integration remains pending.
- Added bounded dispatch and exact-result recovery primitives. Immutable intent
  authentication precedes a single expected-head request. Upload delay triggers
  another fence/window check. The actual request runs in an isolated child with
  a parent-enforced total deadline; timeout is unknown and cannot retry/unlock.
  Source recovery requires authorized PR/head, actual parents and matching tree.
- Independent review found the initial socket-only timeout, expiry during registry
  uploads and reactivation with an old context. Each correction has recorded
  failing-before/passing-after evidence. The [latest scoped review](trusted-ci-broker-foundations-review.md)
  approves the reactivation correction; it is not overall feature approval.
- `lifecycle.py run adopter-broker-foundations --inputs ... -- python -m unittest discover -s deploy/authority/tests`
  → PASS on tree `6517961`, before the later reactivation regression/correction.
  `lifecycle.py redgreen green -- python deploy/authority/tests/test_authority_fence.py`
  → PASS after that correction (seven tests). Earlier upload-expiry and stalled
  child regressions likewise have recorded RED/GREEN evidence.
- `lifecycle.py run adopter-broker-installed-client --inputs .ai/scripts/** -- python -m unittest discover -s .ai/scripts/tests -p test_authority_*.py`
  → PASS on tree `6517961`, including the actual clean installed merge hold.
- A complete broker eligibility collector, receipt/runtime wiring,
  separated broker workflow, host transition workflow integration and real qualification
  remain unfinished. No MERGE-R3–MERGE-R7 completion, full convergence, final
  Review/Verify/Ship or live authorization is claimed. Source stays uncommitted
  on the explicitly unfinished branch. All live/privileged/enforcement holds remain.
- `git diff --check` → PASS. The latest `lifecycle.py scan-diff` reported zero
  findings after the positive validator test asserted its returned gate.
  Dispatch tests assert the expected-head request and submitted outcome. Neither
  is used as standalone E2E or hosted acceptance evidence.
  The existing no-new-lessons retrospective remains closed; it was not replaced
  with a conflicting closure during this continued task. Framework context was
  reconfirmed, so no `knowledge/` bundle was created; docs and Git-scratch receipts
  carry synchronization evidence.

### Continued broker implementation and gate limitations

- The host-transition helper verifies new effective rule bodies before retiring
  the exact old owned rules. It preserves foreign controls and writes the new
  qualifying registry record last. Lost final CAS acknowledgement/readback is
  recovered only through the exact deployment/fence, direct-parent commit and
  unchanged unrelated tree proof. Twelve local tests include readback tampering,
  changed ownership, expired sessions and a fresh-session recovery.
- Bootstrap installation probes now revoke temporary tokens on successful and
  failed probes, including unexpected forbidden capabilities. Revocation failure
  refuses success. No actual App registration or credential probe ran here.
- A verification fence may last up to one hour while the separately issued merge
  authorization remains at most five minutes. The regression allows a 600-second
  verification followed by a fresh authorization and rejects using the fence's
  acquisition time as that authorization.
- Parent-side exact source submission, controlled Codex app-server conversation
  and current issuer-check intent/readback helpers have focused RED/GREEN evidence.
  The submission result retains `admission_established: false`; the harness result
  retains `model_execution_qualified: false`. No OAuth, model inference, protected
  task, check publication or broker merge ran. Independent scoped reviews found
  no findings and explicitly withheld integrated/hosted approval.
- Added create-only Actions broker receipts and an artifact-only Node upload child.
  Six receipt tests and four upload-child tests have recorded RED/GREEN passes.
  Same-name/same-content dispatch receipts still refuse another append. Lost upload
  acknowledgements produce zero merge calls; recovery inspection grants no retry.
  The separate readback mode permits inspection of a failed producer without
  treating that job as successful verification. Workflow runtime-token injection,
  closed producer roles and actual hosted artifact semantics are not verified.
- The official artifact SDK is pinned to 6.3.1 outside the installed `.ai/` client.
  Its initial dependency audit failed on six moderate entries through `glob` and
  `minimatch`. Scoped overrides pin 14.0.2 and 11.0.1 respectively; the identical
  audit has recorded RED/GREEN PASS. `adopter-artifact-sdk-offline` → PASS for the
  actual SDK import and single-file archive path, with no upload/network call.
- Evidence correction: earlier invocations repeated `--inputs`, which retains
  only the final group because the option takes multiple values. Those executions
  remain historical outcomes but cannot establish reuse across omitted inputs.
  Correct invocations use one option, e.g. `--inputs 'deploy/authority/**' '.ai/scripts/**'`.
  `adopter-backend-current-inputs` → PASS on tree `1b1ff1c`; a backend edit correctly
  produced RERUN and unchanged inputs produced REUSE. That PASS predates the newer
  submission, harness, check and receipt helpers and is not current aggregate evidence.
- The broad script gate has no PASS: attempts timed out at 600, 1800 and 3600
  seconds. The four-worker attempt reported Driver failures and Freshness errors;
  its timing class passed. A bounded Driver fail-fast run failed when its five-second
  test budget expired before the expected recovery session. The same named test
  passed in a clean `f7b588e` worktree; one comparison does not establish a cause.
  A bounded Freshness diagnostic timed out at its broad-validation Verify case
  after three tests passed. The inspected Verify/ledger/test source is unchanged
  from baseline. Disposable-fixture stack snapshots locate substantial Verify
  time in repeated ledger input hashing: each of 100 labels recomputes Git
  inventories, and Verify evaluates the entries twice. This diagnostic does not
  explain every Driver/Freshness failure or supply a broad PASS. No production
  timing/ledger patch, timeout increase or weakened assertion was made.
- Source stays uncommitted and explicitly unfinished. Full onboarding, isolated
  task/authentication/relay integration, broker workflow wiring, terminal
  recovery, acceptance convergence and the final frozen gate remain open. All
  privileged/live/publication/activation/enforcement/merge holds remain intact.

### Broker collection and model credential boundaries

- Added closed-role historical artifact authentication, task-admission and
  qualification-summary readers. They validate exact pinned producer jobs and
  domain documents; a submission or an uploaded JSON document alone grants no
  admission. The actual task/qualification producers remain incomplete.
- Added admin-only control rendezvous and the candidate-free broker collector.
  Reader permissions were not broadened. The broker emits one immutable readiness
  receipt after preload; control and five own-App producers refresh afterward.
  Independent review found cached App proofs could survive revocation after preload.
  Mandatory readiness-bound final proofs now replace that authorization path.
  Regression fixtures preserve old successes while revoking each App and assert
  zero merge calls; a coherent fixture reaches one expected-head merge transport.
  `adopter-broker-evidence-current` → PASS on tree `2da9459` (five test methods).
  These are controlled fixtures, not a GitHub merge or hosted timing qualification.
- Added broker-session sequencing, one-shot dispatch and pending unknown-outcome
  handling. Public execution checks the release hold before registry access. The
  real workflow graph, staged credentials and admin terminal recovery remain open.
- Added separate encrypted model-vault storage, access-only delivery, Git CAS
  rotation intents, fixed OpenAI OAuth transport and real signature verification.
  The controller authenticates the pinned dedicated auth job, persists a pending
  intent before one refresh request, validates replacement credentials and persists
  the complete encrypted rotation before delivery. Unknown or invalid responses
  retain the intent and prevent another grant. No native login cache or API billing
  fallback is used. Initial consent and actual relay/task integration remain open.
- `lifecycle.py run adopter-model-auth-sdk --timeout 240 --inputs 'deploy/authority/**' '.ai/scripts/**' -- <isolated-auth-python> -m unittest discover -s deploy/authority -p test_model_*.py`
  → PASS on tree `5da3085`: 24 methods (vault 9, OIDC 9, rotation 6), with real
  cryptography/PyJWT and synthetic issuer/API/Git fixtures. This includes controlled
  malformed-discovery refusal and lost Git completion acknowledgement. No live
  authorization, model request or entitlement qualification ran.
- Required Python 3.15 backend CI steps now include these optional SDK tests and
  locked artifact-client validation. The new remote matrix has not been published
  or executed. [Scoped model controller review](trusted-ci-model-auth-review.md)
  found no controller defect and explicitly withholds overall approval.
- Added a task-scoped loopback/Unix-socket relay with a fixed public Responses
  endpoint, rebuilt upstream OAuth headers, explicit supported request profile,
  bounded incremental SSE forwarding and no automatic request retry. Only validated
  completion plus EOF records the actual stream digest; late failure, disconnect,
  expired capability and budget exhaustion cannot produce successful relay evidence.
  The request profile follows the public [preview requirements](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
  and [completion semantics](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference).
- Review found startup cleanup gaps. Socket-permission, listener and unstarted-thread
  failures have actual failing-before/passing-after reproductions. Ownership is
  captured at acquisition and cleanup refuses substituted filesystem identities.
  [Scoped follow-up](trusted-ci-model-relay-review.md) resolves that finding without
  overall approval. `adopter-model-relay-posix` → PASS on tree `6d50300` for eleven
  tests with no skips under unprivileged `nobody`. The exact command uses
  `wsl --distribution podman-agentic-trusted-ci --user root --exec /usr/sbin/runuser -u nobody -- /usr/bin/python3 /mnt/c/Users/enram/Projects/agentic/deploy/authority/tests/test_authority_model_relay.py`.
  Earlier `wsl ... -- runuser ... -m unittest ...` evidence is not relied upon after
  a diagnostic exposed ambiguous option handling. No container, mount, loop device,
  provider call or privileged setup was performed by these tests.
- Added positive `not-submitted` receipts only in the closed pre-dispatch failure
  path. Once dispatch is entered, every uncertain exception remains pending; no
  such receipt can be emitted. Present no-dispatch evidence excludes later receipt
  creation, and contradictory historical inventory is refused. Uploader contracts
  → PASS on tree `95b062f`, including a deliberately rejecting negative control.
- Added held admin terminal recovery using an independently pinned recovery job,
  exact original terminal attempt and immutable artifacts. Expired authorization
  permits historical inspection only. No-dispatch evidence or exact actual merged
  PR/parents/tree is required; missing/expired evidence, live producers, open PRs,
  rerun substitution and conflicting receipts cannot release the fence. Review
  found a missing outcome/dispatch gate-digest comparison; its actual RED/GREEN
  regression now keeps the fence pending even when the PR really merged.
- Terminal-only registry CAS retains the old configuration after software drift
  and proves the exact new commit, sole parent, intended fence and unchanged
  unrelated tree on a lost acknowledgement. Three focused storage tests and eight
  finalizer methods have recorded RED/GREEN evidence. The terminal envelope digest
  is stored in the four-field history record; the envelope is not separately
  retained, so its hash alone cannot reconstruct all audit facts. Real workflow
  credential staging and recovery invocation remain unfinished.
- The model SDK aggregate and dependency consistency checks subsequently passed
  on tree `cb8c503`; no live auth/model call ran. The lifecycle task metadata was
  corrected through `lifecycle.py tier` to L2/feature with the current authority
  security scope; intent/plan approvals were retained.
- Added initial model consent with persistent host identity, private PKCE/state/
  nonce, exact loopback callback and issued-client handling. A durable exchange
  intent precedes one token request. Unknown outcomes retain only an unverified
  registration hint and require fresh authorization values; verified encrypted
  envelopes recover storage without another exchange or resealing. Profile output
  is credential-free and explicitly unqualified. The public entry remains held.
- The private setup journal lives outside the checkout. Windows uses native
  protected DACL readback; POSIX uses owner-only permissions. Review found that
  matching readback could hide a failed persistence flush, and writable parents
  could permit path substitution. Both have actual reproductions and corrections:
  persistence errors refuse progress, and ancestor substitution rights are checked.
  A separate mutable-snapshot alias caused consent sealing CAS failures; its
  focused RED/GREEN correction returns independent committed snapshots.
- Existing Windows AppData/Temp ACLs grant coding sandbox principals substitution
  rights and are correctly refused. Tests use fresh synthetic home-directory
  fixtures; no existing ACL was changed or exempted. `adopter-private-setup-windows`
  and `adopter-private-setup-posix` → PASS on tree `d67dfe1`, eight methods with
  platform-specific skips. [Scoped private-store follow-up](trusted-ci-private-setup-review.md)
  resolves its findings without asserting a trusted bootstrap context.
- `adopter-model-auth-sdk` → PASS on tree `becec34`, 33 methods including nine
  consent cases. Real local callbacks, generated issuer signatures, PKCE checking,
  denial-before-code negative control, zero grants on uncertain intent persistence
  and sealed-envelope recovery are locally exercised. [Scoped consent review](trusted-ci-model-consent-review.md)
  found no component defect; actual secret staging, deployment wiring, managed
  task integration and hosted qualification remain unfinished. No actual provider
  authorization, GitHub/cloud mutation, model request or enforcement activation ran.
- `adopter-backend-current-inputs` → PASS on tree `399edfe` after relay and terminal
  recovery additions, before private-setup and consent additions. It is historical
  evidence for those inputs, not current whole-feature acceptance. The terminal
  [outcome-binding follow-up](trusted-ci-broker-terminal-review.md) resolves its
  finding; the complete workflow and frozen gate remain outstanding.
- `adopter-backend-current-inputs` → PASS on tree `5da3085`, before relay and
  terminal-recovery additions. It is historical aggregate evidence, not a claim
  that subsequent inputs are covered. The broad script gate still has no PASS.

### Native setup continuation — 2026-11-08

- Added authenticated native configuration ownership for trusted setup, while
  preserving workflow owners for runtime/merge operations. Exact approved scope,
  current human administrator access, App installations and retained progress are
  checked before effects. Prepared software recovery authenticates the exact
  commit, parent, inventory and unrelated files, then reuses the same commit.
  `adopter-native-setup-owner`, `adopter-configuration-compatibility` and
  `adopter-software-compatibility` → PASS on tree `93aa7b8`.
- Added the held `InitialAuthority` creation/software composition. It permits only
  a newly created private authority with a retained creation receipt and no
  registry. Unknown creation stays blocked without a second POST or name-based
  adoption. Prepared software updates are journaled before publication; recovery
  rechecks the original approved release and performs no second publication after
  a lost acknowledgement. Seven fixture methods passed under
  `adopter-initial-setup` at tree `bbad376`; the inventory-substitution regression
  has actual failing-before/passing-after evidence. The public method forwards the
  approved preview directly and remains held before I/O.
- [Independent native setup review](trusted-ci-native-setup-review.md) resolves
  the scoped recovery findings. Complete onboarding, secret wiring, fixed service
  and workflow composition, managed coding supervision and noncircular hosted
  qualification remain unfinished; [integration notes](trusted-ci-adopter-integration.md)
  preserve those boundaries. This is not feature or deployment approval.
- App JWT signing now uses in-memory bounded RSA keys with sanitized failures,
  rather than a temporary PEM file and OpenSSL child. `adopter-app-signing` → PASS
  on tree `5948d1f`, two real cryptography/PyJWT methods with synthetic keys.
  [Scoped signing review](trusted-ci-app-signing-review.md) found no defect.
  `adopter-auth-ci-contract` → PASS on that tree for the CI wiring assertions;
  the expanded hosted matrix has not been run.
- Privileged setup, hosted execution, live qualification, publishing, activation,
  enforcement and real broker merges remain held. No GitHub/cloud mutation or
  provider authorization was performed in this continuation. AWS and Azure remain
  explicitly unqualified. No Review/Verify/Ship completion is claimed.
- Integrated local checks `adopter-backend-current-inputs` and
  `adopter-model-auth-sdk` → PASS on tree `c527f51`, after the native setup,
  consent, software-recovery and in-memory signing changes. The latter contains
  33 methods using real cryptography/PyJWT with synthetic credentials and local
  loopback. Windows backend results retain their platform-specific skips;
  earlier separately recorded unprivileged POSIX results are not relabeled as
  current hosted qualification. `git diff --check` also passed.
- The broad `.ai/scripts` gate remains unsuccessful. Read-only diagnosis shows
  progress through repeated receipt validation rather than a demonstrated deadlock:
  the 100-receipt fixture induces hundreds of Git subprocesses on Windows, and
  recovery-policy fixtures use short real child deadlines. No production timing
  optimization, weakened assertion or unchanged broad-suite retry was made. This
  remains a full-gate blocker, separate from the passing backend checks.
- A later setup-only regression reproduced approval expiry during intent
  persistence: one synthetic repository creation occurred before refusal. Setup
  now reauthenticates immediately before creation and checks the clock after
  identity reads. The same test passed, and all eight methods passed under
  `adopter-initial-setup` on tree `7a68fdb`. The `c527f51` integrated evidence above
  predates this correction; it is not relabeled as current aggregate evidence.
- Corrected a Python/JavaScript artifact-boundary mismatch: Python still rejected
  positive `not-submitted` evidence. The all-receipt-kind regression failed before
  correction and passed afterward. All five Python launcher methods passed under
  `adopter-artifact-python-boundary` at tree `5283d5c`; unchanged JavaScript uploader
  evidence was confirmed REUSE. [Independent follow-up](trusted-ci-broker-terminal-review.md)
  found no defect in the correction and grants no overall or hosted approval.

## Source prepared

### Remaining integration continuation — 2026-11-08

- Added protected credential staging and authenticated per-purpose consumer
  verification. The fixed inventory contains five App keys and separate original
  model-consent vault/delivery keys; no static cloud credential family is accepted.
  Acknowledgement does not establish verified consumption. Unknown present writes
  remain blocked until a matching pinned consumer proof; no overwrite is inferred
  from metadata. `adopter-credential-staging` → PASS on tree `0c2c5a2`, ten methods.
  [Scoped independent review](trusted-ci-credential-staging-review.md) resolves
  expiry-after-identity-readback and inventory preservation corrections.
- The recovery-policy failure was reproduced with controlled three-second child
  startup. Its fixture now advances the policy clock only after recovery/PID
  readiness, with a separate bounded startup watchdog. Original `[6, 2]` allowance,
  timeout exit and both-child termination assertions remain.
  `adopter-driver-recovery-deadline` → PASS on tree `a00e253`; the slow-startup
  reproduction also has RED/GREEN evidence. No production driver budget changed.
- The 100-receipt Freshness fixture completed in a bounded Windows measurement:
  `adopter-freshness-measure-windows` → exit zero, 327.842 seconds overall, tree
  `5283d5c`. Its per-Git counters were discarded by the command wrapper, so no
  counter or phase-duration claim is made. Two attempted POSIX measurements did
  not reach the test: scratch policy rejected temporary storage, then Windows
  metadata-copy permissions rejected the mounted fixture.
- Only that large fixture's Verify subprocess watchdog is now 600 seconds;
  the common helper still defaults to 120. Its full 100-receipt history and all
  behavior assertions remain. A deterministic short-watchdog failure injection
  was RED; after correction the same command ran the real test without injection
  and recorded GREEN. The original long-timeout attempt did not produce a valid
  RED receipt and is not counted as one. This is focused evidence, not a passing
  full regression suite or feature gate.
- The artifact upload path is being extended to closed producer documents and
  fixed members, so credential/evidence jobs need not pass root keys to an upload
  action. Python and JavaScript name-admission tests have actual RED/GREEN evidence;
  integrated SDK archive verification and the workflow remain pending.
- All work remains uncommitted and unfinished. Privileged setup, real credential
  staging, live/provider qualification, publication, activation and enforcement
  remain held. AWS/Azure remain unqualified; no whole-feature sign-off is claimed.

- Strict policy, snapshot and evidence validation, including approved policy epochs.
- Restricted Docker/Podman execution with runtime checks before candidate execution,
  no issuer credentials, and independently provisioned disk-backed work storage.
- Host-side critical assertions and authority-controlled adopter extension support.
- Exact merge-bound GitHub artifact provenance and separate App publication.
- Read-only deployment inspection, independent access attestation checks and hosted
  qualification probes with explicit obligation-specific denial evidence.
- Separate authority workflow, installer distribution and provisioning notice,
  adopter guide and governance documentation updates.

## Executed evidence

Commands use the installed Python executable on Windows in place of `python3`.
See the lifecycle ledger in Git scratch for exact executable, inputs and outcomes.

### Frozen-candidate gate — 2026-11-07

- Fetched `origin/main` before freezing; it matched base
  `cbedc6bde3c423124d72d5e50525fc5e25ca62cf`, so no base merge was needed.
- Created and pushed only the unfinished `codex/trusted-ci` branch checkpoint
  `f7b588ed7291f6d5052afdb15d740c3f1a25af8a` (`wip: freeze trusted CI candidate for qualification`).
  No PR, default-branch merge or host-rule change was performed.
- [Framework parity run 42394070020](https://github.com/enramosjr/agentic/actions/runs/42394070020)
  → **PASS, all 35 required jobs successful**: 32 Windows/Linux × Python 3.9/3.15
  regression segments, both native Windows preflights, and the final Qualification
  summary. Exact SHA, complete job-name inventory and every job's successful
  completion were checked against the GitHub API.
- `lifecycle.py run framework-parity-f7b588e -- gh run watch 42394070020 --repo enramosjr/agentic --exit-status`
  → PASS. This recorded the completed remote result; it did not rerun the matrix.
- Fast governance budget/role/skill contracts → PASS before the full matrix.
- Fresh strict `lifecycle.py converge .ai/docs/trusted-ci-spec.md` on the frozen
  SHA, with the approved real disk-backed executor, → **9 PASS, 1 FAIL, 0 MANUAL**.
  R1–R8 and R10 passed. R9 returned `unverified: GitHub credential required`;
  the independently provisioned authority/App and hosted denial evidence are still
  unavailable. The regression PASS does not waive this feature acceptance failure.
- Local qualification data was verified cleared; the task-owned work volume,
  verified loop device and backing volume were removed after this gate run.

The tested legacy source revision remains the checkpoint above. Later adopter-owned
source additions have not received that full gate. Legacy Review/Verify completion
and deployment approval remained blocked by R9; no feature-signoff PASS is claimed.

### Current disk-backed qualification — 2026-11-07

The user explicitly approved the documented privileged infrastructure setup in
the dedicated Podman WSL2 backend. A fixed trusted image created a 256 MiB ext4
filesystem with UID/GID 65534 ownership, attached as the recorded task-owned
`/dev/loop0`, and mounted through the engine-managed work volume.

- `lifecycle.py run trusted-ci-disk-isolation -- python -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_isolation.py`
  → PASS under strict acceptance, with the real OCI case executed, not skipped.
- `lifecycle.py run trusted-ci-disk-controller-final -- python -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_acceptance.py`
  → PASS under strict acceptance. The full real controller/lifecycle/assurance/
  installer flow passed, and a deliberately broken candidate with unconditional
  success, empty candidate tests and forged local approval was rejected by the
  trusted lifecycle assertion.
- `lifecycle.py run trusted-ci-disk-combined -- python -m unittest -v test_trusted_ci_isolation test_trusted_ci_acceptance`
  → PASS, nine tests with no skips, on tree `a287560`. Tests now clean only their
  admitted fixture data through an unprivileged trusted-image helper after the
  candidate container has stopped, so the modules execute sequentially without
  privileged resets between them.
- Final `lifecycle.py run trusted-ci-disk-owned-cleanup -- python -m unittest -v test_trusted_ci_isolation test_trusted_ci_acceptance`
  → PASS, **eleven tests with no skips**, on tree `7a1d717`. Independent review
  identified a fixture-cleanup reservation race; the helper now reacquires the
  exact deterministic container name before deleting its own data. The collision
  and failed-admission guards have recorded RED/GREEN and portable regressions,
  and the corrected helper also passed this real sequential-container run.
- Independent cleanup check found only `lost+found` in the work filesystem. Both
  task-owned volume mappings were then removed; the recorded loop device was
  verified against its backing file, detached, and confirmed detached. Final
  filtered volume and candidate-container inventories were both `[]`.

R2/R3's earlier local environment blockers are resolved. The frozen regression
gate subsequently passed as recorded above. Hosted R9 qualification remains
outstanding; no convergence PASS is claimed.

### Earlier diagnostics and portable evidence

- `lifecycle.py run trusted-ci-portable -- python -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_*.py`
  → PASS, with real controller/isolation cases explicitly skipped without the
  required volume. This establishes portable checks, actual localhost HTTP publisher
  integration and actual installer/local-feedback paths, not deployed enforcement.
- `python -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_qualification.py`
  → PASS, six tests, including the complete controlled-host ten-case driver and
  rejection of generic refusals. Controlled responses are not hosted evidence.
- A deliberately broken `check_negative` implementation made its criterion-proof
  regression fail as expected; the negative test is sensitive to missing enforcement.
- `python -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_isolation.py`
  → PASS for portable checks, with one real OCI case skipped. The Docker read-only
  source-handling regression was observed RED, then GREEN after its fix.
- `lifecycle.py converge .ai/docs/trusted-ci-spec.md` with
  `AGENTIC_TRUSTED_ACCEPTANCE=1` → **7 PASS, 3 FAIL**. R2/R3 lack the required
  disk-backed executor prerequisites; R9 lacks the independent hosted credentials
  and configuration. No strict skipped pass or convergence success is claimed.
- `lifecycle.py run trusted-ci-installer-regression -- python -m unittest discover -s .ai/scripts/tests -p test_install.py`
  → FAIL/timeout at 600 seconds. Its installed governance-size failure was isolated
  to `InstructionsTests.test_installed_governance_including_markers_stays_below_budget`,
  reproduced RED, and repaired with a shorter existing-introduction link.
- `lifecycle.py run trusted-ci-installed-budget -- python -m unittest discover -s .ai/scripts/tests -p test_install.py -k test_installed_governance_including_markers_stays_below_budget`
  → PASS after that repair. The serial suite's final incomplete class was separately
  run with `lifecycle.py run trusted-ci-windows-hook-upgrade -- python -m unittest test_install.WindowsHookUpgradeTests`
  → PASS. These focused results do not rewrite the broader timeout as a suite PASS.
- Source `AgentsBudget.test_agents_md_stays_below_its_cold_start_budget` → PASS.
- Spec/plan/test requirement trace → PASS for all ten requirement IDs.
- Lifecycle audit → PASS. Review and Verify stages remain open.
- `okf.py affected` reports no bundle; framework-source exemption applies. Existing
  framework docs were updated and no `knowledge/` bundle was created.

An early Podman container isolation check passed before the work area was corrected
from tmpfs. The full controller then correctly failed on lifecycle's disk-backed
scratch requirement. That earlier smoke result does not qualify the current
disk-backed implementation; the current qualification above supplies that evidence.

## Independent review

The original [review](trusted-ci-review.md) and
[follow-up](trusted-ci-review-followup.md) requested changes. The final narrow
[supplement](trusted-ci-review-supplement.md) found no remaining issue in the
examined correction, while explicitly withholding completion/deployment approval.
Reported matrix poisoning, workflow API shape, unrelated-denial, predecessor-binding
and vacuous-test defects were corrected. The frozen regression gate passed;
current passing convergence remains required after hosted infrastructure is available.

The [local follow-up review](trusted-ci-local-review.md) found no remaining issue
in the cleanup ownership correction. Its review preceded the final eleven-test
result above. R9 still prevents overall approval despite the completed regression gate.

## External prerequisites

1. Future authority executors still need independently provisioned disk-backed
   work storage. The local blocker was resolved through the user's explicit
   [storage authorization](trusted-ci-storage-proposal.md), and its task-owned
   resources were cleaned afterward. The executor itself performs no privileged
   storage setup.
2. An independent administrator must provision the authority repository, approved
   image/policy, App, private credentials, restricted coding identity, effective host
   rules and disposable hosted qualification fixtures. Credentials must remain
   outside the coding environment; the current administrator-capable session does
   not establish that separation.
3. Run hosted positive/denial qualification and obtain passing convergence/review.
   The frozen regression gate and local disk-backed controller/isolation acceptance
   have passed; reuse unchanged evidence according to repository policy.

The retrospective recorded the observed tmpfs/disk-backed integration lesson with
its failing command evidence. No lesson was promoted to a project rule. A `wip:`
checkpoint and branch-only push may be used for the explicitly requested full CI
gate. No PR, default-branch merge or remote-rule mutation is authorized by that gate.
