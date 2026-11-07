# Trusted acceptance and merge authorization

Implementation is under qualification. Installing the kit does not activate a
trusted merge boundary. Local hooks, convergence, assurance and approval receipts
provide feedback and drift detection; they do not authenticate consent or authorize
updates to a protected branch. Do not claim deployed enforcement until the remote
inspection and hosted positive/denial qualification pass.

## Three separate environments

1. The coding environment edits the candidate and runs local checks. Its credentials
   have no authority-repository write/admin access, issuer keys, or target bypass.
2. The independent authority repository runs approved host-side assertions against
   the candidate inside a restricted Linux container. Docker and Podman are supported;
   Podman on Windows uses a WSL2 backend. No candidate code runs on the controller host.
3. A fresh publisher job reads the trusted run's artifact, validates provenance and
   freshness, and uses a separate App token to publish the required check. It never
   checks out candidate source or executes candidate-selected commands.

The authority administrators, kernel/runtime, approved worker image and approved
host-side checks are trusted. This does not defend against their compromise or prove
every software behavior correct.

## Installation and ownership

The normal installer exports `.ai/scripts/trusted_ci*.py`, this guide and templates
in `.ai/trusted-ci/`. It preserves existing hook merging and manifest ownership.
It does not export source `.github/` workflows into an adopter, modify host rules,
create an App, grant privileges or install credentials. Adopter discovery configuration
belongs at `.agentic/trusted-ci.json`, outside installer-owned assets. Its contents
are the approved public policy object, not private keys or locally authored evidence.

The authority administrator copies the reviewed kit into a different repository and
installs `.ai/trusted-ci/authority.yml` as `.github/workflows/authority.yml`. Record
the immutable deployed commit; set policy `workflow_sha` to that authority commit
and `verifier_sha` to the reviewed upstream AGENTIC revision. Policy is configured
after the code commit, avoiding a self-referential commit hash in the workflow.

## Policy and target activation

The strict policy fields are defined by `trusted_ci_policy.py`. Required fields:
`schema_version` (1), numeric `repository_id`, `repository` (`owner/name`), simple
`target` branch, `epoch`, numeric `app_id`, `check_name`, numeric
`authority_repository_id`, `authority_repository`, workflow path, immutable
`workflow_sha` and `verifier_sha`, digest-pinned `image`, nonempty unique `checks`,
numeric `reviewers`, `coding_actors`, `merge_actors`, `transitions`, and `limits`.
Limits declare positive `seconds` (maximum 600), `memory_mb` (4096), `processes`
(256) and `disk_mb` (1024). Coding identities cannot overlap reviewer/merge identities.

Independently approve this policy in the authority's `AGENTIC_POLICY_JSON` variable.
Maintain immutable epoch mappings. Activate through a protected target commit
containing `.agentic-trusted-ci.json` with exactly `epoch` and `policy_digest`, where
the latter is the canonical SHA-256 from `trusted_ci_policy.digest(policy)`.
Candidate modifications are evaluated against the current target's marker.
`transitions` contains digests of independently approved successor marker objects;
it never makes candidate acceptance text executable policy.

Only the exact synthetic merge SHA receives the App check. Head-only publication,
unknown/conflicted merge refs and stale targets refuse. Policy activation requires
a new protected target commit, so old results cannot authorize the new epoch.
Merge queues and unsupported retargeting configurations are not qualified.

## Critical checks and adopter extensions

The initial AGENTIC policy uses these nonempty host-side checks:

- `AGENTIC-LIFECYCLE-DENIAL`: missing intent/plan refuses; prerequisites permit.
- `AGENTIC-ASSURANCE-FAILURE`: invalid, stale and failing obligations refuse;
  actual successful re-execution restores verification.
- `AGENTIC-INSTALL-PRESERVATION`: real fresh install/upgrade retains adopter data
  and custom hooks, and installed local feedback works.
- `AGENTIC-AUTHORITY-SEPARATION`: candidate workflow changes, forged receipts and
  hostile writes do not reach trusted files, credentials or check publication.

Adopters add application-specific host-side functions to `CHECKS` in
`.ai/trusted-ci/checks.py` in the independently approved authority checkout, then
list their stable IDs in the approved policy. Each function receives the sandbox
adapter and must assert real outcomes/end states. No extension may override a built-in
obligation. Changes require a newly approved authority revision and policy epoch.
Never import candidate application/test modules into these host-side functions.
Candidate test discovery, PASS text and missing/skipped tests cannot establish coverage.

## Executor prerequisites

Use an independently provisioned ephemeral Linux authority runner with a working
Docker or Podman engine, approved digest-pinned Python/Git image, cgroup memory/CPU/
process limits and default seccomp. The candidate always has a nonroot user,
read-only root, no network, no capabilities, no-new-privileges and no host credentials,
runtime socket, controller files or result paths. Podman copies the isolated source
snapshot into the stopped container. Docker uses a read-only mount of only that
temporary snapshot, since its daemon refuses copies into a read-only rootfs. Neither
path exposes the authority checkout or trusted assertion/result files.

Set `AGENTIC_WORK_VOLUME` on the trusted runner to an independently provisioned empty
disk-backed OCI volume. Its whole filesystem capacity must fit policy `disk_mb`,
and its root must be writable by UID/GID 65534. Plain unbounded volumes and tmpfs
are refused: AGENTIC's lifecycle scratch requires disk backing. A deterministic
container-name reservation prevents two executions sharing the volume concurrently.
The independent runner provisioner must discard/reset that volume after execution;
use an ephemeral runner per job. The executor never creates privileged containers,
loop devices or host mounts to provision storage. Infrastructure setup is outside
the coding agent's credentials and this executable integration.

The real acceptance tests clean only their own admitted fixture data after the
candidate container stops, using a nonprivileged trusted-image helper. This keeps
their modules sequentially runnable on one externally provisioned work volume;
production executor storage still follows the independent provisioner's lifecycle.

The workflow's executor label is `agentic-authority`; configure it only for those
independently provisioned ephemeral runners. Missing prerequisites leave checks
unverified. Hosted candidate Windows regression remains an additional requirement,
not a claim that Linux isolation was qualified by Windows tests.

## Credentials and protected updates

The separate authority needs a read-only `AGENTIC_READ_TOKEN` able to inspect source,
PR reviews, effective rules, collaborators, authority variables, workflow runs and
artifacts. Private-source downloads use that read credential only on trusted host
processes. Download redirects never receive its bearer header.

Only the publisher has `AGENTIC_ISSUER_PRIVATE_KEY`. Configure
`AGENTIC_TARGET_OWNER` and `AGENTIC_TARGET_REPOSITORY` in the authority repository.
The minted installation token requests only checks-write, contents-read and
pull-requests-read (plus implicit metadata-read). The App must have no admin,
contents-write or merge capability. Do not store this key in candidate repositories
or any secret store writable by coding credentials.

The independently administered target requires two effective active rulesets:

- Acceptance rules have no bypass actors, strict current-base checks bound to the
  dedicated App, at least one approving review, stale dismissal, last-push approval,
  code-owner approval, resolved threads, deletion protection and no force pushes.
- A separate update restriction allows only explicit independent merge identities
  to bypass that restriction in pull-request mode. They do not bypass acceptance.

The target's `.github/CODEOWNERS` has one global `* @maintainer ...` rule, with only
approved independent reviewer identities. Specific later patterns and team owners
are not supported in this first adapter. Review identities must resolve to policy
IDs; coding credentials cannot be owners, administrators or unknown custom roles.
Retain existing qualification checks while adding the new required App check.

Store `access-attestation.json` at an independently approved immutable authority
revision, selected by `AGENTIC_ACCESS_REF`. Fields: `schema_version` (1),
`repository_id`, `authority_repository_id`, `policy_digest`, `app_id`, `coding_actors`,
`reviewers`, `merge_actors`, numeric `approved_by`, `credential_separation` (true),
UTC-second `issued_at` and `expires_at` (at most 31 days apart), and
`issuer_permissions` exactly checks/write, contents/read, pull_requests/read,
metadata/read. This is an independent operator's bounded access attestation;
API readback alone cannot prove hidden credentials absent. Rotate/reapprove it
with credentials, identities or policy changes.

## Hosted qualification and read-only inspection

Before claiming enforcement, independently provision and explicitly authorize a
disposable repository with the same policy/checker/image, identities and effective
control semantics. Explicitly authorize only that disposable target by setting
`AGENTIC_QUALIFICATION_REPOSITORY_ID` on the authority. Prepare separately reviewed
hostile PR fixtures for every case in `trusted_ci_qualification.CASES`. Fixtures
must have other required checks passing and independent approval where needed,
so a denial cannot pass merely because unrelated CI or review is missing.

The authority-only `qualify-host` command takes `--policy` (disposable target),
`--reference-policy` (production), `--manifest`, `--run-id`, `--attempt`, and
`--output qualification.json`. Manifest fields are `schema_version` (1),
`qualification_repository_id`, ordered `cases`; each case has `name`, `pr`, `head`,
`prior_merge`, `prior_head`, `prior_base`, `negative_run_id`, `negative_attempt`,
`expected_failure`, and `mutations`. Each mutation contains `path` and SHA-256
`sha256` for reviewed candidate bytes. Bad-acceptance, replaced-checks and
forged-record cases require actual failed-obligation reports from the exact
authority run/attempt and snapshot, not an absent App check or unavailable engine.
Mutations must differ from target bytes; replacement and forgery cases include
their actual replaced test/workflow or forged lifecycle receipt. Prior fields identify actual previous
trusted successes for freshness probes; use null for unused prior fields.
The independent coding/merge test credentials are supplied only to this job as
`AGENTIC_QUALIFICATION_CODING_TOKEN` and `AGENTIC_QUALIFICATION_MERGE_TOKEN`.
The driver attempts real protected updates, checks explicit host refusal and
unchanged refs, then performs the positive merge only in the disposable target.
It never updates the production branch. Generic validation, permission and
revision-mismatch refusals do not qualify as governance denials; snapshots must
remain unchanged around each negative operation.

Publish the resulting `qualification.json` as the authority run's
`hosted-qualification` artifact and set `AGENTIC_QUALIFICATION_RUN` to the completed
successful run ID. The same immutable authority workflow revision must execute
the trusted qualification job. Receipts bind effective production controls and
expire when artifacts/access attestations expire or controls change. The workflow
template's `qualification-probes` mode runs the trusted qualification job; first
use `qualification-fixtures` to evaluate prepared disposable PRs under the
separately approved `AGENTIC_QUALIFICATION_POLICY_JSON`. Configure its
`AGENTIC_QUALIFICATION_ACCESS_REF`, repository name and fixture manifest variables
in the authority. Candidate jobs cannot supply this artifact.

From a configured adopter, run:

```text
python3 .ai/scripts/trusted_ci.py verify-deployment --live --json
```

This operation only reads host state and authority evidence. Missing credentials,
inaccessible rules, agent bypass, absent policy activation, unverified separation,
unqualified host behavior or missing evidence return nonzero with `unverified`.
Local output itself does not authenticate the boundary. No production merge,
remote-rule mutation or privilege provisioning occurs during inspection/install.

## Recovery and evidence

Keep failures blocking. Correct the underlying policy, credentials, host rules or
candidate and rerun the exact trusted obligations. Never waive a check, accept a
candidate report or remove an existing protection to get a green gate. Rollback
requires independently approved policy activation on a new protected target commit.

Adopters synchronize their relevant OKF capability/spec/playbook and log with exact
commands and outcomes, distinguishing installed tooling from deployed enforcement.
Framework source keeps documentation here and receipts in Git scratch. Do not
record a PASS for unavailable isolation or hosted qualification.
