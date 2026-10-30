# Spec: static analysis/convergence documentation input profile

Approved by human:enramosjr in this chat on 2026-10-29 America/Chicago: “Approved. Proceed with the implementation plan for 5h using the recommended D1–D4 decisions.” L2; analyst role; Python principal engineer. Acceptance commands name future checks, not results. Specification approval authorizes planning only; implementation requires a separately approved plan.

## Problem and outcome

Maintainers have seven delivered literal Python input profiles but no profile for the existing exact-method analysis/convergence documentation check. Add one explicitly adopted profile through the existing exporter, with reviewed repository inputs and controlled freshness evidence. Framework mode has no knowledge bundle or structured capability baseline; this standalone specification creates neither and revises no historical evidence.

## Users and scenarios

A maintainer invokes the exporter from the repository root for exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Tiers.test_analyze_and_converge_are_documented
```

Proposed ID: `python-analysis-convergence-doc-contract`. The method loops over three literal paths and requires `lifecycle.py analyze` and `lifecycle.py converge` in each whole document through `text(path)`. A separate literal policy read requires `cites a passing converge run of an identical command on the current tree`. These are seven case-sensitive substring assertions, not seven tests. The method executes no extracted command, accesses no lifecycle attribute and copies nothing. Exactly one actual passing test is a future acceptance expectation, not current runtime proof.

Approved ordered scope:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.ai/lifecycle.md
.ai/docs/lifecycle.md
.ai/validation-policy.md
```

The first pattern conservatively covers production eager imports and lazy-loader/decorator construction, including unused non-test descendants and future supported scripts. Extra invalidation is deliberate and requires D2 approval. The exclusion restores only the selected module and imported test helper. The last three literals are direct document reads, explicit despite general Markdown freshness exemptions. Root AGENTS is not this method's direct read; prior-profile compatibility fixtures retain their own required inputs. Class, sibling and module-wide execution are outside this exact-method claim.

## Requirements

- R1: The exporter MUST register only the exact repository-root argv above as `python-analysis-convergence-doc-contract`. Class/module, sibling, discovery, option, alias and other-interpreter variants MUST remain unregistered unless already registered. All seven delivered profiles MUST retain their complete IDs, argv, ordered inputs, rationales and behavior.
- R2: The profile MUST export exactly the seven ordered patterns above before positive supplements, with per-pattern rationales distinguishing conservative import/setup scope, test exclusion/restoration and direct reads. An independent source-derived oracle MUST cover the selected method, BOTH its bounded tuple-loop binding and separate literal text read, the called text helper, eager initialization, called require_disk, lazy setup and protected/nested decorate construction. It MUST independently derive and deduplicate all three direct documents, verify both loop text calls consume the bound path and verify the separate literal call boundary, retaining a reviewed method fingerprint. Literal-call-only and loop-only extraction MUST NOT suffice. Guards MUST reject boundary drift and confirmed reachable excluded additions. Unrelated tests/documents MUST remain excluded. Conservative pins MUST NOT imply universal dataflow discovery or reachability of uncalled wrapped producer bodies.
- R3: Public text/JSON export MUST preserve existing token/Inputs/rationale parity, supplement order, root/path/inventory validation, nonexecution and refusal behavior. Export MUST neither import/execute the selected test nor validate document assertions, adopt Inputs or record evidence. Missing required literals and unsafe/unsupported paths or unknown commands MUST refuse nonzero with a reason and no usable candidate. Existing documents with failing assertions MUST remain exportable through path-only validation.
- R4: Adoption MUST remain explicit, advisory and manual. Existing inference, full suites, matching, freshness, schemas, gates and producer receipt exclusions MUST remain unchanged. The guide MUST name the exact command/ID, substring-only claim, conservative extra invalidation and runtime/read-completeness limits. It MUST NOT claim section placement, valid commands, actual analysis/convergence, evidence matching/reuse correctness, record behavior, governance/enforcement, native hooks, agent/model behavior, session qualification or VERIFIED evidence from export.
- R5: An isolated framework fixture MUST drive public export and real lifecycle run/reuse. Independent captured unittest output MUST prove exactly one test executed and passed before exit interpretation. Recorded argv, ordered inputs and exit MUST match export; selected repository bytes MUST remain unchanged during execution. Evidence MUST REUSE unchanged and after unrelated-test/non-input-document edits; it MUST RERUN after separate assertion-preserving edits to each of the three direct documents, target, disk helper, representative production import and new supported non-test script. Edits MUST restore original bytes. The invoking framework MUST acquire no knowledge bundle. Seven separate static-failure fixtures MUST make the actual selected command fail while export succeeds: remove each of the two command tokens from each of the three documents, plus remove the separately required policy phrase. Each removal MUST remove every occurrence of the selected token/phrase in that document, confirm changed bytes and establish the intended assertion failure. Freshness mutations and static-failure fixtures MUST remain distinct.
- R6: A separate ordinary adopter fixture MUST explicitly adopt public export, become VERIFIED after independently proven actual one-test execution, remain VERIFIED after unrelated-test/non-input-document edits, and become STALE after each direct-document, target/helper, representative production import and new supported non-test script edit. Unmatched ordered declarations and argv identity MUST yield UNVERIFIED under existing rules; receipt exclusion MUST remain effective. Five confirmed disposable broken controls MUST be rejected: omission of each of the three direct documents, loose command matching and acceptance of actual zero-test execution. Each omission MUST fail its intended freshness assertion while assertion-preserving edits leave the selected check passing. The zero control MUST ignore the selector in an actual empty disposable suite, independently confirm Ran 0 tests, and reject count before Python-dependent exit interpretation. A missing exact method yielding one loader failure is insufficient. Every control MUST confirm mutation bytes and its intended failure without altering historical evidence.

## Acceptance

Proposed AnalysisConvergenceDoc classes below belong in `.ai/scripts/tests/test_assurance_inputs.py`; they do not yet exist. Missing classes, counts or end states fail acceptance. These commands MUST NOT execute during initial drafting. Boundary guards are conservative review guards, not general dependency discovery.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py AnalysisConvergenceDocProfileTests` checks exact ID/argv/root matching, variant refusal, complete preservation of all seven prior entries/rationales/behavior and the narrowly updated prior audit sibling expectation.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py AnalysisConvergenceDocDependencyTests` checks ordered scope/rationales, independent actual ledger selection, BOTH source-derived read forms and their deduplicated three-document union, import/called-body boundaries, unrelated exclusions and future supported non-test descendants. Each newly claimed reachable mutation MUST first fail actual selected execution with its excluded data absent, then pass exactly one test with that data supplied, before intended dependency-review rejection. Cover selected method, text helper, imported excluded helper and source-justified eager/called setup paths; derive final variants from source rather than inheriting thirteen prior controls. Confirm bytes; insert AST body changes after docstrings and before the earliest decorator of the first statement. Uncalled bodies may be conservatively pinned but MUST NOT be described as reached.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py AnalysisConvergenceDocExportTests` checks public formats, supplements, immutability/nonexecution, every missing required literal and unsafe boundary, and path-only export of existing documents that fail selected assertions.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py AnalysisConvergenceDocCompatibilityTests` checks guide claim/limitations and preservation of seven profiles, inference/full suites, matching, schemas, gates and receipts through existing mechanisms. Prior compatibility fixtures retain their own required documents.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py AnalysisConvergenceDocFrameworkEndToEndTests AnalysisConvergenceDocFailureTests` checks independent actual one-test proof, byte stability, identities and each framework freshness outcome, separately from seven confirmed static assertion failures.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py AnalysisConvergenceDocAdopterEndToEndTests AnalysisConvergenceDocControlTests` checks every adopter state/identity and receipt exclusion plus five confirmed broken controls, including all three direct-document omissions and independent actual-zero rejection.

## Constraints

Use the existing literal catalog/export mechanism, Python 3.9+, standard library and unittest conventions. No new options, schemas, normalization, loader, inference, adoption automation, gates or approval authority. Inventory follows existing tracked/supported nonignored-untracked ledger rules. Executable/runtime environment, temporary storage/mount state, ignored files and external mutable data remain outside repository-file claims. Unresolved additional reads require review and retention of current scope.

Existing `AuditDocProfileTests.test_exact_registration_and_prior_profiles` explicitly expects the proposed candidate argv to refuse (`test_assurance_inputs.py:2442`). Approved registration necessarily permits replacing that single now-registered sibling refusal expectation with the approved exact-profile expectation, supplying its required policy input to that fixture if needed. This does not permit changing the audit profile entry/rationale/behavior or weakening any remaining variant refusal. Preservation means contract compatibility, not byte-for-byte preservation of obsolete negative assertions.

Use only `/home/enramosjr/Projects/agentic-assurance-7`, existing branch `claude/assurance-increment-7`, delivered HEAD `8cb4d804a620e0761c2bab45846e7cd62c98ddd4`. Keep ALL docs/assurance ignored/local/uncommitted. Preserve 5g and earlier records and their original source/runtime scopes; historical results verify no eighth profile. During drafting: no source edits, product tests, implementation plan, native/model evaluations, session registration/allocation, fixture trust grants, historical rescoring/evidence modification, new worktree, base refresh, invoking-framework knowledge bundle, commit/push/PR/merge or autonomy driver. Prior delivery authorization is fulfilled.

## Non-goals

Class/module/sibling registration; changing selected assertions or governance contracts; documentation semantics, section placement, command validity, actual analysis/convergence, actual evidence/reuse/enforcement/record behavior; extracted-command execution; native/model/session qualification; general dependency discovery; minimum input set; reduced full gates; automatic adoption; savings claims; planning before specification approval.

## Assumptions

D1-D4 below are approved decisions. The approved ID is `python-analysis-convergence-doc-contract`; descriptions of the ID/candidate as proposed above retain original drafting context and are superseded by this approval. Static inspection establishes candidate scope only. Future controlled fixture evidence cannot establish universal dependency completeness or runtime portability. Framework mode has no capability baseline to merge or bundle to initialize. Historical PASS/REUSE does not verify this profile. No eighth-profile product test has run during drafting.

## Open questions

None. The user approved the specification and recommended D1-D4. Ready for planning only.

## Approved decisions

The recommended defaults below are approved; alternatives remain as decision context. The initial-drafting restriction on writing an implementation plan is now fulfilled; all implementation and delivery restrictions remain pending separate authorization.

- D1: Approve the exact method and `python-analysis-convergence-doc-contract`, select another candidate or stop expansion? Recommended: approve this exact method/ID only; registration scope is a human contract choice.
- D2: Approve seven ordered patterns with conservative extra production invalidation, or require a smaller independently justified closure? Recommended: seven with stated limits and an independent mixed tuple-loop plus separate-literal oracle.
- D3: Approve R2/R5/R6's source-derived boundary controls, independent actual one-test proof, framework/adopter freshness/identity matrix, seven static failures and five omission/matching/count controls? Recommended: yes. Final reachable dependency variants MUST follow actual source and fresh reachability proof, not historical counts.
- D4: Preserve all seven complete profiles and existing inference/suites/schemas/matching/freshness/gates/receipts, retain explicit advisory/manual adoption, and claim substring presence only? Recommended: yes.

## Investigation evidence

Nonexecuting source inspection only:

- `.ai/scripts/tests/test_lifecycle_conformance.py:15-27,208-212`: root/import setup, called text helper, three-path literal tuple and separate literal policy read. No lifecycle attribute access, extracted-command execution or copying in the selected method.
- `.ai/scripts/assurance_inputs.py:17-137,195-246`: seven complete literal entries, exact argv matching, path-only validation and advisory limits.
- Independent read-only analyst inspection: `disk_tmp.py:10-20`, `scratch.py:11-26` cover eager helper/called disk validation and possible environment/cache mutation. `lifecycle.py:41-66,1011,1209,1321,1994-1995`, `review_guard.py:23-26,629-639`, `ledger.py:10-22` cover production imports, lazy setup and protected/nested decorate construction. review_guard eagerly imports ledger, so lifecycle.lazy("ledger") may return that existing module. The selected method calls no wrapped producer; importing lifecycle does not invoke its main entry point. Runtime/storage/mount effects remain outside repository-file claims.
- `.ai/scripts/tests/test_assurance_inputs.py:2442,2509-2577`: prior negative expectation and reviewed setup/method pins/loop-only oracle. The latter cannot alone cover this method's additional literal read. Thirteen prior mutations establish no eighth-profile proof.
- Analyst structured search: `.ai/lifecycle.md:44,59,163,167`, `.ai/docs/lifecycle.md:8,10`, `.ai/validation-policy.md:27` contain required tokens/phrase; multiple occurrences require complete token removal in future static-failure controls.
- `docs/assurance/handoff-5h.md` and leading authoritative delivery update in `implementation-5g.md`: delivered identity, restrictions and historical evidence scopes. Prior setup pins and thirteen reached variants are mechanism references only, not eighth-profile proof.
- Local `repo.py context --json`: framework, expected branch/HEAD, clean tracked state; local refs only, no new remote check. New L2 declared after context; Intent unapproved.

## Draft validation

- `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5h.md` -> exit 1, only High open-questions finding for D1-D4; these are deliberate human-approval blockers, not resolved contracts.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5h.md` -> exit 0, six requirements traced. Structural evidence only; no acceptance command executed.
- `git check-ignore docs/assurance/specification-5h.md` -> exit 0, ignored path confirmed.
- Required read-only analyst independently confirmed mixed read boundary and shared import/called-helper/lazy/decorator construction; identified the obsolete audit sibling refusal expectation and proposed its narrow update. Python-persona considerations affecting the draft: import-time side effects, called-helper boundaries, storage/environment exclusions and independent actual test-count proof.

The initial analysis failure above is historical drafting evidence. Human approval now resolves D1-D4 and authorizes an implementation plan only. No source edits or product tests occurred.
