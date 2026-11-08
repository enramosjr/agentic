# Adopter authority integration resolutions

These are implementation decisions within the approved adopter-owned spec and
plan (R1–R10, MERGE-R1–MERGE-R7). They do not authorize live setup or activation.
The source journey remains unfinished; privileged setup, hosted qualification,
publication, enforcement and broker merges remain held.

## Native setup ownership

Trusted local setup uses an authenticated native administrator, rather than a
fabricated Actions execution. Only a configuration operation may carry `setup`
with its operator ID, administrative App installation ID and complete approved
preview digest. Its run/attempt are null. Workflow-owned configuration operations
and all merge operations retain their positive workflow coordinates.

`SetupConfigurationSession` checks current-user identity, administrative repository
access, private authority identity, App registration/installation permissions,
approved account/target and resource scope before every effect. A retained exact
configuration/digest/branch binding is mandatory. The existing mutators keep their
guarded interface; the new owner type supplies no unguarded mutation path.

The preview binds software inventory, cloud template/account, protection changes
and credential resource names. Approval remains an action recorded by the trusted
setup controller in protected storage. JSON fields and native administrator access
do not establish that a modifying process is absent. Setup must still run outside
coding access; managed workers receive neither its credentials nor journal.

## Software interruption recovery

Before changing a software ref, setup retains the prepared commit, exact approved
plan digest, complete preview digest and operation/sequence in its private journal.
Failure to confirm persistence stops the update. Reconstruction requires that
retained record and authenticates the actual commit, sole parent, approved file
inventory and preservation of unrelated files. It cannot infer approval from the
current default branch. Recovery reuses the prepared commit rather than creating
another one. Once the registry is repinned, rolling software back to the old base
fails the phase guard.

`adopter-native-setup-owner` passed on tree `93aa7b8`: nine methods, including lost
acknowledgement recovery and deliberately bypassed proof/phase negative controls.
These are API/Git fixtures, not live setup or qualification.

## Initial installation boundary

The first software installation precedes the registry and cannot borrow a workflow
owner that does not exist. The setup entrypoint must admit only newly created,
approved private authority resources, fixed release inventory, protected creation
receipts and a nonforce Git update. Existing installations cannot use that narrow
exception for repair. After the registry exists, ordinary scoped configuration
sessions govern subsequent effects.

`deploy/authority/setup.py:InitialAuthority` now composes that initial creation and
software transition with the protected journal and existing Git installer. It
persists creation intent before the single repository POST, retains the returned
resource ID, and accepts only the private owned auto-initialized README tree. It
persists the prepared commit before the nonforce update. Unknown creation cannot
be retried or adopted by name; lost software-update acknowledgement can recover
only that exact commit. Recovery also rechecks the complete approved release
manifest. Existing registry state excludes this capability. This is one setup
component, not complete registration, secret wiring, qualification or activation.

The seven-method local fixture suite passed at tree `bbad376` after an independent
review finding and actual RED/GREEN correction of substituted recovery inventory.
The [scoped review](trusted-ci-native-setup-review.md) records the exact limits.
The subsequent expiry regression failed when journal persistence consumed the
remaining approval window. Creation now reauthenticates immediately before its
POST and checks time after identity reads. The same regression passed; all eight
initial-installation methods passed at tree `7a68fdb`. A persisted intent never
authorizes creation after its preview expires.

## Fixed service and workflow composition

Credential staging now has a fixed seven-name inventory: five purpose-App keys and
separate model vault/delivery keys. It retains exact values and write intents in a
protected sibling journal before writes, reuses the installed consent envelope and
its original keys, and authenticates the native CLI actor against the setup owner.
An acknowledged write remains unverified. A present uncertain secret cannot be
overwritten automatically; an authenticated matching consumer proof can recover it.
Each consumer receives its own credential and proves actual consumption through a
domain-separated HMAC bound to the current operation, nonce and execution. The vault
consumer also opens the exact initial encrypted model record. This does not add
static AWS/Azure credentials; cloud authentication remains federated.

The ten-method SDK fixture passed at tree `0c2c5a2`. [Independent scoped review](trusted-ci-credential-staging-review.md)
resolved authorization expiry after identity readback. These are local fixtures;
the fixed workflow still must wire the producer jobs and isolated upload path.

Use a separate v2 authority workflow and a fixed role dispatcher. Preserve the v1
workflow. Admission precedes sensitive credential construction; inputs are bounded
hints, not commands, policies, authorities or token scopes. Process one fenced
candidate per run so producer job identities remain unambiguous.

Publication requires its own authenticated administrative readback before the
issuer check exists. It cannot depend on the final broker rendezvous: broker
preload already requires that check. After publication, warm the broker, final
controls and five separate own-App producers concurrently; then perform the fresh
rendezvous and one dispatch. Administrative finalization is separate.

The coding supervisor must compose real disk/container admission, a clean pinned
harness, access-only lease/relay, measured cleanup, validated export and exact
submission into the authenticated task receipt. A protocol fixture or submitted
PR alone cannot establish isolation. These connected handlers remain unfinished.

## Noncircular qualification

The current full-summary reader cannot bootstrap its own positive broker case:
that case must precede the final summary digest, while ordinary broker admission
requires the digest. The qualification producer must resolve this through a
separate, authenticated trial authority confined to disposable fixture repository
IDs, with its own registry/fence and certificate. A certificate permits trials; it
must not claim completed qualification.

Ordinary production entrypoints must reject trial markers and certificates.
Qualification shares the actual broker controls, evidence, freshness, dispatch and
merge-result path, replacing only qualification admission with a strictly scoped
trial admission object. No `skip_qualification` flag belongs in the production API.

The final chain is parent configuration → authenticated trial certificate and
prerequisites → actual case receipts → complete qualification summary. Production
and fixture controls are observed separately, with equivalent approved rule
semantics. Activation occurs only after the complete summary and sidecar chain
exist. The real deployment never references a trial certificate as its qualification.
This producer/chain integration remains unfinished and is not hosted evidence.
