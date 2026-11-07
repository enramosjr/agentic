# Implementation Plan: Trusted acceptance and merge authorization

Status: Proposed plan for the user-approved [spec](trusted-ci-spec.md).
Implementation and external deployment have not started. L2; Python principal
engineer persona. Runtime input validation and process isolation materially shape
the design; local filesystem permissions are not treated as a trust boundary.

## Objective

Give AGENTIC and adopters an independently administered critical acceptance
authority and remotely enforced merge boundary, retaining local hooks and existing
regression qualification.

## Success criteria

- R1, R2, R3: Candidates cannot replace critical checks, alter authoritative
  outcomes, or obtain check-issuer credentials.
- R4, R5, R6: Only complete trusted evidence for the exact repository, merge
  candidate, target and approved policy satisfies the required App check;
  independent approval and host protections remain mandatory.
- R7, R8: Local feedback remains usable; read-only inspection distinguishes
  installed tooling, configured controls and qualified enforcement.
- R9: Completed hosted positive and denial tests establish the actual boundary.
- R10: Fresh installs and upgrades distribute integration without credentials or
  silent changes to host protections.

## Current state

- [Framework parity](../../.github/workflows/framework-parity.yml) checks out the
  candidate, executes candidate tests/runner and aggregates outcomes. Retain this
  qualification without presenting it as independent critical acceptance.
- `.ai/scripts/tests/test_qualification_gate.py` tests aggregate failure propagation,
  rather than provenance or merge authorization.
- `.ai/scripts/install.py`: `KIT` recursively exports `.ai/`, excluding source
  `.github/`. Existing hook-option preservation, installation planning and drift
  checks must remain compatible with the format-1 manifest.
- `.ai/scripts/tests/test_install.py` has real installer/repository fixtures;
  `test_installed_qualification.py` exercises an uncommitted upgrade and retained
  adopter content.
- [Lifecycle guidance](lifecycle.md) already distinguishes operational guards and
  recorded attribution from authenticated consent. The approved spec records the
  inspected main ruleset and available administrator bypass.
- This is a framework repository. `okf.py affected` reports no bundle; do not
  initialize `knowledge/`. Use existing source docs and Git-scratch receipts.

## Proposed approach

### Authority and orchestration

Use a separately administered GitHub authority repository installed from a
reviewed immutable AGENTIC revision. Its approved workflow runs scheduled discovery
and operator `workflow_dispatch`; no always-on webhook service is needed. It queries
allowlisted numeric repository identities and open PRs. Dispatch inputs identify
repository/PR only, never commands, policies, code revisions or sandbox settings.

Separate acquisition, verification and fresh publication jobs. Only publication
receives the App's check-write credential; it never checks out or executes candidate
content. Private source acquisition uses independently scoped contents-read
credentials confined to trusted acquisition/controller processes. No App private
key or check-write token enters the controller or candidate executor.

Authority-side configuration and artifacts are authoritative. Installed local
configuration contains only discovery hints and public identifiers; editing it
cannot change the deployed authority. The local audit CLI is diagnostic and reads
authority evidence; its own output is not an authorization token.

### Approved policy, evidence and freshness

Strict versioned JSON policy declares repository identity, protected target,
nonempty critical check IDs, approved host-side checker revision, digest-pinned
worker images, resource limits and permitted transitions. Unknown fields, missing
checks, duplicate IDs and unsupported versions fail before execution.

Pin policy epochs through a marker in the protected target revision, with an
independently approved immutable epoch mapping held by the authority. Candidate
marker changes are evaluated under the existing target's policy and its transition
rules. Activation requires a new protected target commit. Never silently change
the active policy for an existing target SHA.

Evidence binds numeric repository ID, PR number, head/base/synthetic-merge SHAs,
policy/checker/image digests, authority workflow revision, run ID/attempt, required
outcomes and result digest. Publication requires the exact controller artifact
from that trusted execution and successful prerequisite jobs; artifact names or
candidate-created reports are insufficient. Reject missing, empty, duplicate,
skipped, neutral, canceled, timed-out or failing mandatory outcomes.

Publish the dedicated App check only on the verified synthetic merge SHA, never
on the PR head. Require strict up-to-date protection. Re-read repository, target,
PR and epoch identities before publication; refuse changes, conflicts or unknown
merge refs. Target/policy activation creates a new merge candidate with no trusted
success. Never fall back to publishing on head when a merge ref is unavailable.
Unsupported merge queues or retargeting configurations fail deployment inspection.
Hosted qualification must verify GitHub's actual selection/fallback behavior.

### Candidate isolation and trusted assertions

The trusted Python controller runs host-side checks through a narrow sandbox
adapter and never imports candidate code or test modules. Run candidate commands
inside a fresh Linux Docker container using an independently maintained,
digest-pinned Python/Git image. Use nonroot execution, read-only root filesystem,
dropped capabilities, no-new-privileges, normal seccomp, private PID namespace,
no network and bounded CPU, memory, processes, writable storage and wall time.
Expose only bounded sandbox work/fixture storage. Never build a candidate Dockerfile.

Do not mount the Docker socket, authority checkout, trusted checks, authoritative
results, credentials, or Actions environment/output files. Keep candidate imports,
`PYTHONPATH` and `sitecustomize` out of trusted host processes. Acquire pinned source
without candidate filters/hooks/build scripts; reject unsafe archive paths,
escaping links, special files and oversized archives. Treat stdout as bounded data,
suppressing workflow-command and terminal-control injection.

The initial AGENTIC policy contains approved host-side black-box obligations:

1. `AGENTIC-LIFECYCLE-DENIAL`: missing intent/plan refuses the guarded operation;
   prescribed prerequisites permit it.
2. `AGENTIC-ASSURANCE-FAILURE`: invalid declarations and changed declared inputs
   cause invalid/stale failure; actual successful re-execution restores the state.
3. `AGENTIC-INSTALL-PRESERVATION`: fresh install/upgrade preserves adopter content
   and custom hooks; exercise installed guard behavior.
4. `AGENTIC-AUTHORITY-SEPARATION`: replaced candidate tests/workflows, forged local
   records and hostile writes cannot change assertions or publish trusted success.

Assert exit status, returned structures and actual fixture end states, including
negative controls. Candidate PASS text is never an authoritative outcome. The
existing Linux/Windows matrix remains required additional qualification; do not
describe candidate-controlled matrix tests as independently verified acceptance.

### Host merge boundary and credential separation

Require the dedicated App as the check's expected source, authenticated independent
review, stale-review dismissal, last-push approval and current-base enforcement.
Inspect all effective rulesets, inherited rules, branch protections and bypass
actors, including every API page. Restrict permitted reviewers through approved
authority policy as well as host review requirements.

Add a separate protected-update restriction: coding identities cannot update the
protected branch directly, even after checks pass. Only independent merge identities
may bypass that update restriction in pull-request mode; they cannot bypass the
separate acceptance/review rules. The issuer has no contents-write or merge rights.

Require an independently approved authority-side credential/access attestation
bound to numeric repository, coding and App identities, with validity and rotation
limits. API readback cannot prove absence of hidden credentials. Missing separation,
unknown role membership, unavailable permission evidence or agent bypass leaves
deployment unverified. The current administrator-capable coding credentials must
be replaced outside this session before enforcement can be qualified.

## Boundaries and invariants

- Trusted commands, policies, imports, paths and issuer identity never come from
  candidate configuration or dispatch-controlled executable content.
- Independently approved policy changes cannot approve their own candidate.
- API/network errors, incomplete pagination and ambiguous metadata fail closed.
- Installer and inspection commands never grant permissions, create services or
  mutate remote rules. Preserve adopter customizations and existing protections.
- Python tooling retains Python 3.9 compatibility. Docker is an authority-executor
  dependency, not a prerequisite for ordinary local hooks.
- No local filesystem flag, ledger, approval attribution or diagnostic report
  authenticates the external authority.

## Implementation steps

### Step 1: Policy and evidence cannot be substituted — R1, R4, R5

New: `.ai/scripts/trusted_ci_policy.py`; examples under `.ai/trusted-ci/`;
`test_trusted_ci_policy.py`, `test_trusted_ci_provenance.py`,
`test_trusted_ci_freshness.py` under `.ai/scripts/tests/`.

Write failing tests first for strict schemas, empty/duplicate coverage, identity
substitution, immutable epochs, replay and ref/policy changes during execution.
Implement pure validation/comparison without shell execution. Check: the three
approved acceptance commands reject deliberate policy/evidence substitutions.

### Step 2: Assertions execute outside candidate control — R2, R3

New: `.ai/scripts/trusted_ci_sandbox.py`, `trusted_ci_controller.py`; host-side
cases and worker-image definition under `.ai/trusted-ci/`;
`test_trusted_ci_acceptance.py`, `test_trusted_ci_isolation.py`.

First write hostile candidate fixtures for trusted-file writes, credential/host
access, resource exhaustion and output injection. Implement safe source acquisition,
sandbox lifecycle, bounded transport and the four initial obligations. Clean up
owned containers on error/cancellation. Check: actual Docker execution of working
and violating candidates; always-pass candidate tests and forged records cannot
rescue failure. Missing isolation prerequisites fail designated acceptance.

### Step 3: Only the separate App publishes trusted outcomes — R4, R5, R6

New: `.ai/scripts/trusted_ci_github.py`; authority workflow template under
`.ai/trusted-ci/`; `test_trusted_ci_authorization.py`.

Write controlled-HTTP integration tests first for pagination, wrong issuers,
changed refs, revoked approval, stale epochs, wrong run/attempt and replayed
artifacts. Implement discovery, artifact provenance and the separate publisher.
Pin Actions dependencies by full revision. Check: actual adapter flow publishes
only complete trusted outcomes on the synthetic merge SHA; no publisher path
executes candidate content or publishes authoritative head-only success.

### Step 4: Deployment inspection distinguishes configuration from enforcement — R6, R8, R9

New: `.ai/scripts/trusted_ci.py`, `test_trusted_ci_deployment.py`; deployment and
hosted-qualification manifest examples under `.ai/trusted-ci/`.

Implement `verify-deployment`, `--live`, `--json` and explicit configuration
selection, including the spec's default invocation. Read effective protections,
identities, authority pins, approvals and hosted evidence. Write failing fixtures
first for absent/conflicting/inherited rules, agent bypass, inaccessible evidence,
expired attestations and unsupported modes. Check: real CLI against controlled
host responses returns nonzero for blockers/unverified prerequisites and makes no
mutation requests. Do not infer deployment from local configuration.

### Step 5: Adopter installs retain local feedback — R7, R10

Existing: `.ai/scripts/install.py`, `test_install.py`,
`test_installed_qualification.py`. New: `test_trusted_ci_install.py`,
`test_trusted_ci_compatibility.py`, `.ai/docs/trusted-ci.md`.

Use recursive `.ai/` export and existing manifest conflict handling; do not
automatically copy source `.github/`. Distribute templates/tooling and identify
external provisioning in installation output. Keep runtime configuration at an
adopter-owned path outside installer-owned assets. Test first through real fresh
install/upgrade, custom hooks, history-free upgrade, drift and conflict fixtures.
Check: installed guards function; no remote writes, credentials or active-enforcement
claims arise from installation. Run affected existing installer tests as well.

### Step 6: Independently provision and qualify hosted enforcement — R1, R2, R3, R4, R5, R6, R7, R8, R9, R10

New: trusted hosted-qualification driver and receipt schema under `.ai/trusted-ci/`.
An independent operator provisions the authority repository, App, approved policy,
scoped credentials, restricted coding identity and disposable qualification target
from reviewed immutable files. This prerequisite cannot be supplied by local tests.

Before production activation, run discovery through isolated checks and App
publication. Exercise actual host refusal for bad acceptance, replaced tests,
forged records, spoofed App source, absent approval, direct push, new head/base and
policy transition. Record API responses and unchanged protected refs for denials.
Positive merges occur only in the explicitly authorized qualification repository.
The trusted driver has an explicit target allowlist; local `verify-deployment
--live` only reads its evidence. Independently activate AGENTIC and read back its
effective controls. Missing infrastructure/evidence leaves R9 incomplete.

### Step 7: Delivery describes the verified boundary — R7, R8, R9, R10

Existing: `AGENTS.md`, `.ai/lifecycle.md`, `.ai/docs/lifecycle.md`,
`.ai/docs/install-and-upgrade.md`, `.ai/docs/windows-runtime.md`, `.ai/README.md`,
`README.md`. New: trusted-CI guide and deployment receipt references.

Document setup, approved policy activation, failure recovery and rollback that
retains closed protections. Preserve local workflows and qualification names.
Independent two-pass review checks the approved spec, integration, denial paths,
documentation and evidence. Check: document contracts, requirement traceability,
current convergence and exact-candidate qualification. Distinguish tested tooling
from deployed enforcement in every delivery claim.

## Testing strategy

Implement on an isolated `codex/` branch after plan approval. Write new logic and
denial tests first. Dependencies: policy/evidence precedes controller and host
adapter; those precede publisher/audit; installer integration precedes hosted
qualification. External provisioning must be complete before activation.

Use controlled API fixtures for deterministic integration and actual installer/CLI
paths. Actual Docker is mandatory for R3, and actual GitHub enforcement for R9.
Windows retains portable policy/API/installer/hook coverage. Mocked sandbox flags,
off-platform skips and zero-test discovery cannot satisfy isolation acceptance.
The trusted acceptance inventory checks required IDs/counts and rejects missing or
skipped mandatory cases, independent of candidate unittest discovery output.

## Validation commands

Existing commands available for planning/implementation checks:

```text
python3 .ai/scripts/lifecycle.py analyze .ai/docs/trusted-ci-spec.md
python3 .ai/scripts/lifecycle.py trace .ai/docs/trusted-ci-spec.md --plan .ai/docs/trusted-ci-plan.md --tests .ai/scripts/tests
python3 -m unittest discover -s .ai/scripts/tests -p test_install.py
python3 -m unittest discover -s .ai/scripts/tests -p test_installed_qualification.py
python3 .ai/scripts/run_tests.py -j 4
```

Trace with tests becomes a completion check only after those tests exist and cite
requirements; a planning trace without tests establishes plan coverage only.
Do not run product suites merely to deliver this read-only plan.

After deliverables exist, run the ten spec acceptance commands through convergence
on a Linux/Docker qualification host with live authority evidence available. The
slice E2E is discovery → isolated critical assertions → exact App publication →
actual host acceptance/refusal. Assert the final protected-ref state, not startup.

Record checks with `lifecycle.py run`, use `reuse` before repeating, and reuse
identical convergence evidence. Run focused tests in the loop, the slice E2E on
the completed candidate, then the full existing 32-segment Linux/Windows/Python
matrix and preflights once on the reviewed frozen candidate/current base. Retain
separate trusted authority qualification. Missing prerequisites are unrun/blocking,
never PASS. Review and retrospective close before final Verify; Git-scratch receipts
record exact outcomes. No complete/ready claim while R9 remains unqualified.

## OKF impact

Update existing framework documentation and Git-scratch lifecycle receipts; create
no source `knowledge/` bundle. The adopter guide explains application-specific OKF
synchronization and evidence logging without rewriting adopter knowledge or
claiming enforcement from installation. Reassess source mappings with `affected`
where an adopter bundle exists.

## Risks and mitigations

- GitHub merge-check selection must hold in the deployed configuration: actual
  hosted qualification gates activation, including target/policy races.
- Container isolation relies on the trusted kernel/runtime: patch and pin the
  infrastructure and expose no host services or secrets to candidate code.
- Current coding credentials have administrator bypass: deployment stays inactive
  until externally restricted identities and separate authority are established.
- Private archives/artifacts introduce parsing and credential risks: bounded strict
  parsing, safe extraction, provenance checks and separate scoped credentials.
- Polling/provisioning add latency; missing authority results remain blocking.

## Out of scope

Other hosting providers, universal sandbox adapters, autonomous default-branch
merging and exhaustive correctness claims.

## Open decisions

None. The plan is ready for implementation approval. Independent provisioning is
an explicit deployment prerequisite, not an assumed property of this environment.

## Platform references

- [GitHub required-check selection and expected sources](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)
- [GitHub check-run API](https://docs.github.com/en/rest/checks/runs)
- [GitHub repository rules API](https://docs.github.com/en/rest/repos/rules)
- [Docker execution controls](https://docs.docker.com/engine/containers/run/)
