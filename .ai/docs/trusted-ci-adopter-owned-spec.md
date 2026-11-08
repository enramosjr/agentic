# Spec: Automated adopter-owned trusted authority

Status: Approved by the user on 2026-11-07; lifecycle intent approval recorded as
`human:enram`. Replaces the centrally operated managed-service proposal.
No new deployment adapter or automated setup capability is claimed implemented.
Acceptance commands below are proposed deliverables.

Broker refinement: the user selected fresh brokered merges on 2026-11-07:
humans review; a separate scoped App performs the merge after fresh authorization.
This adds MERGE-R1–MERGE-R7 below and does not lift any live-operation hold.

Tier: L2. Persona: Python principal engineer.

## Problem and outcome

AGENTIC needs independently controlled acceptance verification and remote merge
authorization without requiring its maintainer to operate or subsidize adopters'
infrastructure. AGENTIC supplies maintained authority software, deployment
adapters and automated setup. Each adopter owns deployed resources and usage.

The setup journey asks for authentication, repository/provider selection,
required account values, consent and explicit approval of proposed changes.
It does not ask users to assemble Apps, credentials, workflows, runners, secrets,
rules or qualification fixtures manually. GitHub Actions is the proposed default;
AWS and Azure self-deployment adapters are included alternatives. All three use
the same policy, verification, publication and evidence contracts.

This replaces the operating/funding assumptions of
[the managed spec](trusted-ci-managed-spec.md) and
[withdrawn plan](trusted-ci-managed-plan.md). Existing independently controlled
critical verification remains the baseline to preserve.

## Users and scenarios

- A repository owner selects an execution adapter during trusted setup.
- A human administrator runs bootstrap outside the coding agent's access boundary.
- Setup provisions and qualifies approved resources and protections automatically.
- The adopter launches its chosen supported coding harness in a restricted context.
- Independent authority execution evaluates exact candidate revisions.
- Interrupted setup, drift, unsupported capabilities or revocation block activation.
- Adopters deploy AWS or Azure resources into accounts they control and fund.

## Requirements

- R1: Setup MUST automate authority provisioning and configuration after normal
  authentication, resource selection and explicit human consent. It MUST NOT
  require manual App form configuration, credential copying, workflow editing,
  secret wiring, rule editing, runner setup or qualification-fixture assembly.
- R2: AGENTIC MUST provide GitHub Actions, AWS and Azure deployment adapters.
  Resources MUST belong to the adopter's selected account, subscription or
  organization. Adapters MUST NOT depend on an AGENTIC-operated paid service.
  Setup MUST identify resource ownership, expected billable resource types and
  usage controls before creation; it MUST NOT promise unlimited free use.
- R3: Administrative bootstrap, coding, verification, publication and merging MUST have
  separate credential domains. Bootstrap credentials and issuer root keys MUST
  remain inaccessible to coding tasks. Publishers MUST lack administration,
  bypass and root credentials capable of minting administrative tokens, and MUST
  NOT execute candidate content.
- R4: Setup MUST discover effective controls, present exact changes, provision
  only approved configuration and verify effective readback. Retries MUST be
  idempotent. Bootstrap MUST preserve stronger existing protections and MUST NOT
  require temporary coding bypass or circular marker/required-check dependencies.
- R5: Strong enforcement MUST require an established isolated coding context
  without ambient administrator credentials, human browser sessions, authority
  write access or trusted-check publication capability. The adopter's chosen
  supported harness MUST remain usable without a mandatory AGENTIC model service.
  An external session whose separation cannot be established MUST receive a
  narrower or unverified status.
- R6: Independent authority policy MUST contain nonempty, human-approved critical
  coverage pinned outside candidate control. Evidence MUST bind repository,
  target, candidate/base/merge revisions, policy, verifier, runtime, adapter,
  authenticated execution identity and complete outcomes. Stale, forged,
  incomplete or candidate-supplied evidence MUST NOT authorize publication.
- R7: All adapters MUST restrict authority resources, artifacts, tokens and
  publication to approved account/repository/job bindings. Setup callbacks,
  provider responses and job completions MUST reject replay and resource
  substitution. Candidates MUST NOT select authorities, commands or token scopes.
- R8: Installed tooling MUST distinguish setup, qualification, active, blocked
  and revoked states. Active status MUST require effective controls, established
  credential separation and current qualification. Drift, revocation, stale
  bindings, missing evidence and unavailable dependencies MUST fail closed.
- R9: Every adapter MUST support automated real positive and intended-denial
  qualification before advertising enforcement. Qualification MUST exercise
  incorrect acceptance, replacement checks, forged evidence, spoofed issuers,
  absent review, direct updates and stale bindings. Generic errors, skipped
  probes and configuration presence MUST NOT count as proof.
- R10: Installation MUST preserve local hooks and Python 3.9 client compatibility.
  Coding environments MUST NOT receive bootstrap or service-root credentials.
  Policy changes and candidate review MUST remain explicit human decisions;
  setup consent MUST NOT approve future candidate changes. Deployment, upgrade,
  repair and teardown MUST be automated for adapter-owned resources while
  preserving unrelated adopter resources and protections.

- MERGE-R1: (R3, R7) A dedicated merger App/key MUST remain separate from admin,
  coding, verification and check publication. Its registration/tokens MUST lack
  administration, check/status publication, workflow/rule editing and authority
  write capabilities. Tokens MUST target only the approved source repository.
  The broker MUST NOT execute candidate content or lend its key to publisher jobs.
- MERGE-R2: (R3, R4, R10) Only the merger App MUST receive PR-only bypass on the
  separate protected-update restriction, with no acceptance-rule bypass. Humans
  MUST provide independent review without an ordinary alternative merge path.
  Setup MUST preview this change and preserve unrelated protections. Deliberate
  administrator compromise or rule replacement is outside the claimed boundary.
- MERGE-R3: (R6, R7, R8) Each merge request MUST use authenticated current registry,
  qualification, controls, App capabilities, task isolation, execution evidence,
  required check and independent human review. The decision MUST bind repository,
  installation, PR, head/base/synthetic-merge, policy/configuration generations,
  check context, verifier/runtime, proof identities and broker attempt. Missing,
  revoked, expired, inconsistent or unknown state MUST block dispatch. The broker
  MUST supply the expected head SHA to the synchronous merge API.
- MERGE-R4: (R4, R6, R8) An authorization-relevant transition MUST install/read back
  a new never-reused epoch-specific, issuer-App-bound required context before
  activating the registry generation. Old successes MUST NOT authorize the new
  generation. Every interruption MUST fail closed without acceptance bypass or
  weakening unrelated stronger protections; recovery MUST be supported.
- MERGE-R5: (R6, R7, R8) Merge authorization MUST live at most 300 seconds, with at
  least 60 seconds remaining on every expiring binding at dispatch. Final readback
  MUST be no older than 30 seconds. The single synchronous merge request MUST have
  a client deadline no greater than 30 seconds. Repository/target-scoped fencing
  MUST serialize attempts and AGENTIC configuration transitions; proofs MUST be
  single-use and attempt-bound. Auto-merge, merge queues and asynchronous scheduling
  MUST NOT extend this request path. Outage or unavailable readback MUST block it.
- MERGE-R6: (R7, R8, R10) Timeout, interruption or an ambiguous merge response MUST
  remain pending/unknown until authenticated exact-PR/head/result readback resolves
  it. An open PR MUST NOT by itself prove failure or permit blind retry. Every
  later attempt MUST obtain fresh authorization. Success MUST authenticate actual
  merge parents and tree, not assume its commit SHA equals the synthetic merge.
  Pre-dispatch revocation MUST block; post-dispatch changes MUST NOT be represented
  as guaranteed instantaneous cancellation. A client deadline does not promise
  cancellation of GitHub server work.
- MERGE-R7: (R9) Hosted qualification MUST prove the broker is the sole ordinary
  merge path, including positive reviewed merges and intended denials for missing
  review, bad acceptance, human/coding updates, stale bindings, expired proof,
  revoked qualification, outage and context transitions. It MUST demonstrate the
  merger cannot bypass acceptance. Generic errors and local fixtures MUST NOT
  count as hosted proof.

## Acceptance

- R1: `python3 .ai/scripts/tests/test_authority_setup.py AutomatedOnboarding`
  completes clean setup through supported consent/selection actions without
  manual configuration or secret copying.
- R2: `python3 .ai/scripts/tests/test_authority_adapters.py AdapterOwnership`
  exercises all three adapter contracts, verifies resource ownership and cost
  disclosures, and rejects dependence on AGENTIC-operated paid infrastructure.
- R3: `python3 .ai/scripts/tests/test_authority_setup.py CredentialDomains`
  tests deployed/bootstrap/worker boundaries and rejects privilege escalation,
  issuer impersonation and administrative credential access.
- R4: `python3 .ai/scripts/tests/test_authority_setup.py ProvisioningRecovery`
  verifies fresh/interrupted setup, effective privileged readback, preserved
  stronger controls and bootstrap without bypass or circular activation.
- R5: `python3 .ai/scripts/tests/test_authority_setup.py CodingIsolation`
  drives the supported protected launcher with an actual coding harness,
  verifies restricted access and refuses strong status for an unisolated
  administrator-capable external session.
- R6: `python3 .ai/scripts/tests/test_authority_setup.py IndependentEvidence`
  rejects empty/unapproved coverage, checker substitution, altered bindings,
  forged reports and incomplete outcomes.
- R7: `python3 .ai/scripts/tests/test_authority_adapters.py ResourceAuthorization`
  rejects callback replay, cross-repository/account substitution, stale leases
  and candidate-selected credential or authority parameters.
- R8: `python3 .ai/scripts/tests/test_authority_setup.py EnforcementLifecycle`
  exercises interruption, drift, revocation, outage and recovery without
  converting incomplete state into active enforcement.
- R9: `python3 .ai/scripts/authority_setup.py qualify --live --adapter all`
  qualifies GitHub Actions, AWS and Azure deployments against real disposable
  targets and records authenticated execution and case-specific denial results.
  Missing provider accounts, services or permissions fail rather than skip.
- R10: `python3 .ai/scripts/tests/test_authority_setup.py InstalledLifecycle`
  exercises clean installation, local hooks, upgrade, repair and teardown,
  preserving adopter data and keeping bootstrap credentials outside coding access.

- MERGE-R1: `python3 .ai/scripts/tests/test_authority_merge.py MergerCredentialDomains`
  tests exact scope, escalation rejection and absence of merger credentials from
  publisher/candidate domains. Local contracts do not close hosted R3/R9.
- MERGE-R2: `python3 .ai/scripts/tests/test_authority_merge.py SoleMergePath`
  tests the exact Integration/App-ID PR-only update exception, no acceptance bypass,
  independent human review and rejection of alternate ordinary actors.
- MERGE-R3: `python3 .ai/scripts/tests/test_authority_merge.py FreshEligibility`
  rejects altered/missing bindings and unavailable readback, and checks expected
  head SHA submission to the synchronous API.
- MERGE-R4: `python3 .ai/scripts/tests/test_authority_merge.py GenerationTransition`
  retains head/base after generation-A success, transitions to B, rejects A for B,
  and exercises every interruption boundary without an unsafe intermediate state.
- MERGE-R5: `python3 .ai/scripts/tests/test_authority_merge.py AuthorizationWindow`
  controls time/concurrency to test expiry, the exact 60-second boundary, readback
  age, single use, fencing and HTTP deadline.
- MERGE-R6: `python3 .ai/scripts/tests/test_authority_merge.py UncertainMergeOutcome`
  loses responses before/after a server merge, prevents blind retry, reconciles
  actual parents/tree and requires fresh subsequent authorization.
- MERGE-R7: `python3 .ai/scripts/authority_setup.py qualify --live --adapter all`
  additionally exercises real broker-positive and case-specific denials for all
  three execution adapters. Missing services/accounts fail, never skip to PASS.

## Constraints

- No AGENTIC-funded AWS, Azure or other central execution service.
- AWS/Azure adapters and deployment code are maintained by AGENTIC; the adopter
  deploys them into its own infrastructure and owns associated bills.
- GitHub account capabilities, Actions usage, models and cloud resources may have
  adopter costs. Disclose applicable usage, permissions and plan limitations.
- Authentication, organization-owner approval and account/subscription values may
  require human input. Configuration and resource wiring remain automated.
- Bootstrap runs outside coding-agent access. Removing environment variables
  alone does not establish credential isolation.
- Remote configuration cannot neutralize existing administrator-capable coding
  sessions; do not advertise that guarantee.
- Private source, policies, logs and artifacts must not become public to obtain
  free runner usage. Preserve the adopter's approved confidentiality boundary.
- GitHub-hosted runners must demonstrate required Docker, cgroup, disk-backed
  capacity and cleanup properties. Existing self-hosted evidence is insufficient.
- AWS/Azure adapters provision qualified isolated execution; generic serverless
  containers are not presumed to satisfy the existing Docker contract.
- Prove manifest callback/authentication behavior on supported platforms; do not
  assume loopback callback support without testing.
- Provider SDKs and infrastructure dependencies stay outside the stdlib installed
  client, except in explicitly isolated optional deployment packages.
- Framework documentation stays in existing locations; do not create knowledge/.
- The user-selected broker replaces the earlier ordinary human merge path and
  blanket no-App-bypass statement. The exception applies only to the separate
  update restriction; acceptance remains non-bypassable by the merger.
- Source/local verification authorization does not permit privileged setup, hosted
  execution, live qualification, publication, broker merges or activation here.

## Non-goals

Operating a shared AGENTIC SaaS, subsidizing adopter infrastructure, supplying a
mandatory model account, supporting every harness immediately, automatic human
approval or neutralizing administrator credentials on arbitrary machines.

## Assumptions

- The user requires AGENTIC-maintained AWS/Azure self-deployment adapters and
  rejects maintainer-funded infrastructure for other users.
- GitHub Actions is the proposed default, not a promise of universally free use.
- Protected coding may use a local or selected environment provided actual
  credential separation is established. No central AGENTIC coding fleet is required.
- Existing verifier/sandbox/publication logic can be reused after adapter-specific
  qualification; prior evidence does not prove new paths.

## Open questions

None.

## Evidence and proposed automation mechanisms

- Current `.ai/trusted-ci/authority.yml` requires a self-hosted verifier and
  `.ai/docs/trusted-ci.md` requires hard-sized disk-backed storage. The GitHub-hosted
  default is proposed work, not existing support.
- [GitHub App manifests](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest)
  support registration and credential generation through a guided flow.
- [GitHub Secrets API](https://docs.github.com/en/rest/actions/secrets) supports
  programmatic secret wiring.
- [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
  distinguishes public standard runners from private usage and owner billing.
- [AWS deployment links](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-console-create-stacks-quick-create-links.html)
  and [Azure template deployment](https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/deploy-to-azure-button)
  support preconfigured deployment with account-owner approval.
