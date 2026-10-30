# Spec: stage documentation and runtime stage-name input profile

Approved by human:enramosjr in this chat on 2026-10-29 America/Chicago: “Approved. Proceed with the implementation plan for 5i using the recommended D1–D4 decisions. Keep implementation pending separate plan approval.” L2; analyst role; Python principal engineer. Acceptance commands name future checks, not results. Specification approval authorizes planning only; implementation requires a separately approved plan.

## Problem and outcome

Maintainers have eight delivered literal Python input profiles but no exact-method profile for the existing stage documentation and runtime stage-name check. Add one explicitly adopted profile through the existing exporter, with reviewed repository inputs and controlled freshness evidence. Framework mode has no knowledge bundle or structured capability baseline; this standalone specification creates neither and revises no historical evidence.

## Users and scenarios

A maintainer invokes the exporter from the repository root for exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Tiers.test_every_stage_the_script_gates_is_described_in_the_lifecycle
```

Proposed ID: `python-stage-doc-contract`.

The selected method reads `.ai/lifecycle.md` once through a literal `text` call. It iterates five literal heading labels and requires the corresponding exact `## {heading}\n` substrings:

- Stage 0: Intent
- Stage 1: Plan
- Stage 3: Review
- Stage 4: Verify and sync
- Stage 5: Ship

Stage 2 is not checked. The method separately requires `set(lifecycle.STAGES)` to equal `{"intent", "plan", "review", "verify", "ship"}`. These are five substring checks and one runtime set-equality assertion within ONE test. Set equality ignores order and duplicate values and establishes no tuple type. Heading substring presence establishes no section structure, body correctness, ordering or actual stage enforcement. The method executes no lifecycle command or extracted command and copies nothing. Exactly one actual passing test is a future acceptance expectation, not current runtime proof.

Proposed ordered scope:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.ai/lifecycle.md
```

The first pattern conservatively covers production eager imports, runtime STAGES definition/access and lazy-loader/decorator construction, including unused non-test descendants and future supported scripts. Extra invalidation is deliberate and requires D2 approval. The exclusion restores only the selected module and imported test helper. The final literal is the direct document read, explicit despite general Markdown freshness exemptions. Root AGENTS, `.ai/docs/lifecycle.md` and validation-policy are not this method's direct reads; prior-profile compatibility fixtures retain their own required inputs. Broader Tiers class, sibling and module registration are outside this claim.

## Requirements

- R1: The exporter MUST register only the exact repository-root argv above as `python-stage-doc-contract`. Class/module, sibling, discovery, option, alias and other-interpreter variants MUST remain unregistered unless already registered. All eight delivered profiles MUST retain their complete IDs, argv, ordered inputs, rationales and behavior.
- R2: The profile MUST export exactly the five ordered patterns above before positive supplements, with per-pattern rationales distinguishing conservative production/setup scope, test exclusion/restoration and the direct document read. An independent source-derived oracle MUST resolve the selected method's literal document call, heading-label tuple, interpolation and runtime `lifecycle.STAGES` attribute/set comparison, retaining reviewed method and relevant setup fingerprints. It MUST cover the called text helper, eager initialization, called require_disk, lazy setup and protected/nested decorate construction. A path-loop oracle, document-literal extraction alone or source-only STAGES extraction MUST NOT suffice. Guards MUST reject boundary drift and confirmed reachable excluded additions. Unrelated tests/documents MUST remain excluded. Conservative pins MUST NOT imply universal dependency discovery or reachability of uncalled wrapped producer bodies; source extraction MUST NOT be presented as runtime STAGES proof.
- R3: Public text/JSON export MUST preserve existing token/Inputs/rationale parity, supplement order, root/path/inventory validation, nonexecution and refusal behavior. Export MUST neither import/execute the selected test nor evaluate its document/runtime assertions, adopt Inputs or record evidence. Missing required literals and unsafe/unsupported paths or unknown commands MUST refuse nonzero with a reason and no usable candidate. Existing documents with failing selected assertions MUST remain exportable through path-only validation.
- R4: Adoption MUST remain explicit, advisory and manual. Existing inference, full suites, matching, freshness, schemas, gates and producer receipt exclusions MUST remain unchanged. The guide MUST name the exact command/ID, five heading-substring checks, observed runtime stage-name set, conservative extra invalidation and runtime/read-completeness limits. It MUST NOT claim documentation semantics, section/body correctness, stage order, uniqueness or tuple type, actual gates/enforcement, native hooks, agent/model behavior, session qualification or VERIFIED evidence from export.
- R5: An isolated framework fixture MUST drive public export and real lifecycle run/reuse. Independent captured unittest output MUST prove exactly one test executed and passed before exit interpretation. Recorded argv, ordered inputs and exit MUST match export; selected repository bytes MUST remain unchanged during execution. Evidence MUST REUSE unchanged and after unrelated-test/non-input-document edits; it MUST RERUN after separate assertion-preserving edits to the direct document, target, disk helper, representative production import and new supported non-test script. Edits MUST restore original bytes. The invoking framework MUST acquire no knowledge bundle. Six separate static-failure fixtures MUST make actual selected execution fail while export succeeds: remove every occurrence of each of the five exact required heading substrings from the direct document, separately, and introduce disposable lifecycle.STAGES set-member drift. Each fixture MUST confirm changed bytes and the intended selected assertion failure. The STAGES case MUST reach the runtime set assertion, rather than fail import or CLI setup. Freshness mutations and static-failure fixtures MUST remain distinct.
- R6: A separate ordinary adopter fixture MUST explicitly adopt public export, become VERIFIED after independently proven actual one-test execution, remain VERIFIED after unrelated-test/non-input-document edits, and become STALE after each direct-document, target/helper, representative production import and new supported non-test script edit. Unmatched ordered declarations and argv identity MUST yield UNVERIFIED under existing rules; receipt exclusion MUST remain effective. Three confirmed disposable broken controls MUST be rejected: omission of the sole direct document, loose command matching and acceptance of actual zero-test execution. Omission MUST fail the intended freshness assertion while assertion-preserving edits leave the selected check passing. The zero control MUST ignore the selector in an actual empty disposable suite, independently confirm Ran 0 tests, and reject count before Python-dependent exit interpretation. A missing exact method yielding one loader failure is insufficient. Every control MUST confirm mutation bytes and its intended failure without altering historical evidence.

## Acceptance

Proposed StageDoc classes below belong in `.ai/scripts/tests/test_assurance_inputs.py`; they do not yet exist. Missing classes, counts or end states fail acceptance. These commands MUST NOT execute during initial drafting. Boundary guards are conservative review guards, not general dependency discovery.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py StageDocProfileTests` checks exact ID/argv/root matching, variant refusal and complete preservation of all eight prior entries/rationales/behavior. Existing registered sibling expectations remain preserved; no obsolete candidate-refusal replacement is currently justified by inspected source.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py StageDocDependencyTests` checks ordered scope/rationales, independent actual ledger selection, source-derived literal document/heading tuple/interpolation/runtime attribute-set boundaries, import/called-body boundaries, unrelated exclusions and future supported non-test descendants. Each newly claimed reachable mutation MUST first fail actual selected execution with excluded data absent, then pass exactly one test with data supplied, before intended dependency-review rejection. Cover selected method, text helper, imported excluded helper and source-justified eager/called setup paths; derive variants from source rather than inheriting thirteen prior controls. Confirm bytes; insert AST body changes after docstrings and before the earliest decorator of the first statement. Uncalled bodies may be conservatively pinned but MUST NOT be described as reached.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py StageDocExportTests` checks public formats, supplements, immutability/nonexecution, every missing required literal and unsafe boundary, and path-only export when existing inputs fail selected assertions.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py StageDocCompatibilityTests` checks guide claims/limitations and preservation of eight profiles, inference/full suites, matching, schemas, gates and receipts through existing mechanisms. Prior compatibility fixtures retain their own required documents.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py StageDocFrameworkEndToEndTests StageDocFailureTests` checks independent actual one-test proof, byte stability, identities and each framework freshness outcome, separately from six confirmed selected assertion failures, including actual runtime STAGES drift.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py StageDocAdopterEndToEndTests StageDocControlTests` checks every adopter state/identity and receipt exclusion plus three confirmed broken controls, including sole-direct-document omission and independent actual-zero rejection.

## Constraints

Use the existing literal catalog/export mechanism, Python 3.9+, standard library and unittest conventions. No new options, schemas, normalization, loader, inference, adoption automation, gates or approval authority. Inventory follows existing tracked/supported nonignored-untracked ledger rules. Executable/runtime environment, temporary storage/mount state, ignored files and external mutable data remain outside repository-file claims. Unresolved additional reads require review and retention of current scope.

Preserve the eight delivered profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract, python-installer-doc-contract, python-validation-policy-contract, python-audit-doc-contract and python-analysis-convergence-doc-contract. Inspected tests contain no literal proposed exact candidate refusal requiring a 5h-style replacement. Do not weaken other refusals or alter existing positive sibling registrations.

Use only `/home/enramosjr/Projects/agentic-assurance-7`, existing branch `claude/assurance-increment-7`, delivered HEAD `0efa2240b6109f6e69fe7a5dacaa3f9be16482c2`. Keep ALL docs/assurance ignored/local/uncommitted. Preserve 5h and earlier records and their source/runtime scopes; historical results verify no ninth profile. During drafting: no source edits, product tests, implementation plan, native/model evaluations, session registration/allocation, fixture trust grants, historical rescoring/evidence modification, new worktree, base refresh, invoking-framework knowledge bundle, commit/push/PR/merge or autonomy driver. Prior delivery authorization is fulfilled.

## Non-goals

Class/module/sibling registration; changing selected assertions or governance contracts; actual stage gates/enforcement; documentation semantics, section/body correctness; order, duplicate or tuple-type guarantees; extracted-command execution; native/model/session qualification; general dependency discovery; minimum input set; reduced full gates; automatic adoption; savings claims; planning before specification approval.

## Assumptions

D1-D4 below are approved decisions. The approved ID is `python-stage-doc-contract`; descriptions above as proposed retain drafting context and are superseded by this approval. Static inspection establishes candidate scope only. Future controlled fixture evidence cannot establish universal dependency completeness or runtime portability. Framework mode has no capability baseline to merge or bundle to initialize. Historical PASS/REUSE does not verify this profile. No ninth-profile product test ran during drafting.

## Open questions

None. The user approved the specification and recommended D1-D4. Ready for planning only.

## Approved decisions

The recommended defaults below are approved; alternatives remain as decision context. The initial-drafting restriction on writing an implementation plan is fulfilled; implementation and delivery restrictions remain pending separate authorization.

- D1: Approve the exact method and `python-stage-doc-contract`, select another candidate or stop expansion? Recommended: approve this exact method/ID only.
- D2: Approve five ordered patterns with conservative extra production invalidation, or require a smaller independently justified closure? Recommended: five with stated limits and an independent literal-document, heading/interpolation and runtime attribute-set oracle.
- D3: Approve source-derived boundary controls, independent actual one-test proof, framework/adopter freshness/identity matrix, six static failures and three omission/matching/count controls? Recommended: yes. Final reachable dependency variants MUST follow actual source and fresh reachability proof, not historical counts.
- D4: Preserve all eight complete profiles and existing inference/suites/schemas/matching/freshness/gates/receipts, retain explicit advisory/manual adoption, and limit claims to five heading substrings plus observed runtime STAGES-set equality? Recommended: yes.

## Investigation evidence

Nonexecuting source inspection only:

- `.ai/scripts/tests/test_lifecycle_conformance.py:15-27,197-201,297-298`: root/import setup, called text helper, literal direct document read, five heading labels/interpolation, runtime attribute/set comparison and unittest entry point. Labels contain colons; no Stage 2 check.
- `.ai/scripts/lifecycle.py:41-76`: eager scratch/review_guard imports, lazy-loader setup and literal STAGES definition. Source definition is not proof of the value observed during selected execution.
- `.ai/scripts/tests/disk_tmp.py:10-20` and `.ai/scripts/scratch.py:11-26`: imported helper calls require_disk; mount probes and possible cache/environment mutations remain outside repository-file claims.
- `.ai/scripts/review_guard.py:23-26,629-639` and `.ai/scripts/ledger.py:10-22`: eager ledger/scratch initialization and protected/nested decorate construction. Lifecycle lazy("ledger") can return the eagerly imported existing module. Construction does not establish execution of wrapped producer bodies.
- `.ai/scripts/lifecycle.py:1011,1209,1321,1994-1995`: decorator applications construct wrappers; imported lifecycle does not invoke its main entry point.
- `.ai/scripts/assurance_inputs.py:17-148`: eight complete literal profiles. Candidate is absent.
- Structured search of `.ai/scripts/tests/test_assurance_inputs.py` found no literal proposed exact candidate; no obsolete negative assertion replacement is authorized by this inspection. Existing audit/analysis compatibility expectations remain preserved.
- `docs/assurance/handoff-5i.md` and leading authoritative delivery update in `implementation-5h.md`: delivered identity, restrictions and historical evidence scopes. Prior setup pins and thirteen reached variants are mechanism references only, not ninth-profile proof.
- Required read-only analyst returned this draft and D1-D4 after independent source inspection. Python-persona considerations affecting the draft: import-time effects, called-helper versus uncalled-wrapper boundaries, external storage/environment exclusions and independent count-first runtime proof.
- Local `repo.py context --json`: framework, expected branch/HEAD, clean tracked state; local refs only, no new remote check. New L2 declared after context; Intent unapproved.

## Draft validation

- `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5i.md` -> exit 1, only High open-questions finding for D1-D4. These are deliberate human-approval blockers, not resolved contracts.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5i.md` -> exit 0, six requirements traced. Structural evidence only; no acceptance command executed.
- `git check-ignore docs/assurance/specification-5i.md` -> exit 0, ignored path confirmed.
- `git status --short --untracked-files=no` -> exit 0, empty output: tracked status clean. No new remote check.

The initial analysis finding above is historical drafting evidence. Human approval now resolves D1-D4 and authorizes an implementation plan only. No source edits or product tests occurred.
