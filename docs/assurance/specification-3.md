# Spec: architecture constraints as governed capability requirements

Approved by human:enramosjr in chat, 2026-10-28. L2; Python principal engineer.
The user accepted D1–D3 and approved specification-3.md. Implementation requires an approved plan; no implementation has started.

## Problem and outcome

Architecture decisions need a durable connection to executable constraints. Capability requirements already provide stable IDs, Verify commands, Inputs, evidence, status reports and L2/L3 enforcement. Increment 3 adds a governing-decision reference and demonstrates architecture drift detection through that existing path.

VERIFIED continues to mean that the declared command passed on its recorded inputs. A governance reference establishes neither ADR approval nor complete architectural correctness.

## Users and scenarios

An adopter declares an architecture constraint as an ordinary structured capability requirement, links its motivating decision, and supplies a command that detects violations. Explicit execution establishes evidence; a constrained source edit makes it stale; rerunning exposes the violation; repair and another run restore VERIFIED. Readers can locate the decision from assurance output. Malformed or dangling references receive diagnostics.

## Requirements

- R1: A structured capability requirement MAY declare one indented `- Governed-by:` line before its first scenario. A present line MUST contain exactly one Markdown link with nonempty label and target to a local Markdown decision document. No special namespace, capability filename or requirement type MUST be required.
- R2: Governance references MUST use existing OKF document-relative or bundle-relative resolution and resolve to an existing Markdown file within the knowledge bundle. Empty/malformed values, duplicate or late declarations, external URLs, directories, missing files and targets resolving outside the bundle MUST make the requirement INVALID with an ID and repair diagnostic. Optional fragments MUST be retained, but section existence and decision approval/status MUST NOT be claimed as validated.
- R3: Assurance text and JSON reports MUST expose the governing reference for requirements declaring it, including nonpassing requirements. This metadata MUST remain declared provenance: it MUST NOT grant VERIFIED, waive failure or certify approval. JSON metadata MUST be additive under schema_version 1, with no changed output fields for requirements lacking the declaration.
- R4: Governance MUST NOT implicitly alter the execution command or evidence input scope. Governing-document edits MUST stale evidence when that document matches declared Inputs; omission MUST retain existing freshness behavior. Documentation MUST explain that omission can leave evidence unchanged and show explicit inclusion when decision edits should invalidate it.
- R5: Governed requirements MUST retain existing mechanical, MANUAL and UNDECLARED Verify semantics. Constraint commands MUST execute only through existing explicit producer commands. Reading governance metadata MUST NOT execute obligations or add an enforcement gate.
- R6: Governed requirements MUST retain their IDs and declaration through approved delta add/modify/merge. Existing exact-command convergence evidence, input scope and L2/L3 touched-requirement enforcement MUST apply. Selected INVALID, STALE, FAILED or UNVERIFIED constraints MUST refuse Verify without recording it; existing nonblocking statuses MUST remain nonblocking.
- R7: The lifecycle guide MUST document the reference grammar, explicit input scope, statuses, enforcement and limits, with a runnable standard-library fixture showing a real forbidden dependency. Requirements without Governed-by MUST retain existing evidence, status, exit and gate behavior.

## Acceptance

All classes below are proposed NEW tests in `.ai/scripts/tests/test_assurance_architecture.py`; none exists or has passed yet. The file must support direct unittest execution with these exact class names. Direct invocation must fail if the file or named class is missing; no empty discovery run counts as evidence. Tests must assert the described end state. Full gate selection follows the approved implementation plan and repository validation policy.

- R1: `python3 .ai/scripts/tests/test_assurance_architecture.py DeclarationTests` asserts declaration extraction in an arbitrary structured capability, optional omission and placement before the first scenario.
- R2: `python3 .ai/scripts/tests/test_assurance_architecture.py ReferenceTests` asserts both resolution conventions, preserved fragments and every listed invalid case, including a symlink escaping the bundle; validation executes neither the target contents nor an obligation.
- R3: `python3 .ai/scripts/tests/test_assurance_architecture.py ReportTests` drives actual assure text/JSON commands, asserts reference visibility for passing/nonpassing requirements, and proves metadata cannot change mechanical status, basis, exit or approval claims. Ungoverned report fields remain unchanged.
- R4: `python3 .ai/scripts/tests/test_assurance_architecture.py FreshnessTests` records evidence and edits the linked ADR, asserting STALE with the ADR explicitly included in Inputs and existing freshness behavior when omitted. It asserts exact recorded scope, with no implicit added input.
- R5: `python3 .ai/scripts/tests/test_assurance_architecture.py ConstraintFlowTests` drives an actual temporary adopter CLI through UNVERIFIED, explicit successful run, VERIFIED, forbidden source dependency edit, STALE, explicit failing run, FAILED, repair and explicit successful run, VERIFIED. The checker asserts a real forbidden dependency; disabling the check must break the test. Additional cases assert MANUAL/UNDECLARED and that reports never run commands.
- R6: `python3 .ai/scripts/tests/test_assurance_architecture.py IntegrationTests` drives approved delta add/modify/merge and matching convergence, asserting preserved IDs/declaration, exact scope and one execution. Actual gate cases assert selected invalid/failing constraints refuse without a Verify record and repair/passing evidence permits Verify, while existing nonblocking outcomes remain unchanged.
- R7: `python3 .ai/scripts/tests/test_assurance_architecture.py CompatibilityTests` exercises the documented example and asserts existing behavior for ungoverned requirements. Existing assurance, attestation, delta and gate tests provide additional compatibility coverage.

## Constraints

Standard library only; Python 3.9+. Reuse capability blocks, OKF path conventions, ledger evidence, explicit execution and existing gates. No new database, daemon, hook, lifecycle stage, policy language, mandatory third-party checker or automatic execution.

Framework mode: no knowledge bundle or adopter capability baseline is created in this repository. This is a framework feature spec using R-number IDs, not a delta against a nonexistent framework capability. Adopter fixtures exercise stable namespaced capability IDs and approved deltas.

Working documents stay ignored under docs/assurance and uncommitted. Preserve completed increment 2/7 work and evidence. No native/model evaluation attempt, temporary fixture trust grant, commit, push, PR, merge or additional worktree is authorized. Implementation requires settled behavior decisions, human spec approval and an approved plan.

## Non-goals

ADR approval/status schemas; deciding an adopter's architecture; deriving constraints from ADR prose; automatic dependency discovery or input adapters (increment 5); installing Cargo/import-linter; anchor validation; new waivers; full architecture-coverage claims; rerunning completed native campaigns.

## Assumptions

User-approved decisions: D1 uses provenance-only references and explicit Inputs for ADR freshness; D2 retains mechanical, MANUAL and UNDECLARED outcomes; D3 requires exactly one local Markdown link resolving within the knowledge bundle, with INVALID for malformed or missing targets. No fixed ADR directory, new approval/status schema or anchor validation is required. Existing prose-only requirement-edit evidence reuse remains applicable. A local Markdown decision document needs no new ADR frontmatter type or approval authority.

## Open questions

None. The user accepted all three recommendations and approved this specification. The spec is ready for planning.

## Investigation evidence

- Historical roadmap: `git show 4031aab:docs/assurance/architecture.md`, sections 2 and 6: ordinary capability requirements governed by ADRs, using existing constraint commands.
- `.ai/scripts/assurance.py:80`: current declaration parser recognizes Verify, Inputs and Accept-risk; Governed-by has no assurance semantics.
- `.ai/scripts/assurance.py:135`: discovery covers ordinary structured capabilities without a special architecture type.
- `.ai/scripts/assurance.py:318`: evidence matching uses the current command and scope; MANUAL and UNDECLARED are distinct.
- `.ai/scripts/assurance.py:388`: touched-requirement gate selection and blocking statuses.
- `.ai/scripts/brownfield.py:74`: requirement blocks retain indented body text.
- `.ai/scripts/okf.py:556` and `:785`: existing local link resolution/target validation conventions; no established section-anchor validation.
- `.ai/lifecycle.md:181`: public declaration, evidence, gate and delta contracts through line 205.
- `docs/assurance/closeout-2-review-enforcement.md`: completed and pushed checkpoint at 6205344; historical evidence scopes and consumed allocations remain preserved.
