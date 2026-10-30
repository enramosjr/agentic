# Spec: Semantic-lens documentation input profile

Approved by human:enramosjr in this chat on 2026-10-29 America/Chicago: “Approved. Proceed with the implementation plan for 5m using the recommended D1–D4 decisions, including the 14 assertion failures and 6 broken controls. Keep implementation pending separate plan approval.” L2; analyst role; Python principal engineer. Spec approval permits planning only; implementation requires SEPARATE plan approval. Acceptance commands below are future checks, not execution evidence.

## Problem and outcome

Maintainers have twelve delivered literal Python input profiles but no exact-method profile for the existing semantic-lens documentation check. Add one explicitly adopted profile through the existing exporter, with reviewed repository-file inputs and controlled freshness evidence. This framework has no knowledge bundle or structured capability baseline; this standalone specification initializes neither and revises no historical evidence.

## Users and scenarios

A maintainer requests repository-root export for exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py RolesAndSkills.test_semantic_lens_in_analyst_reviewer_and_skills
```

Proposed ID: `python-semantic-lens-doc-contract`. Broader RolesAndSkills class/module and sibling registration are outside scope.

Inspected source at test_lifecycle_conformance.py:113–123 has SIX top-level statements and FOUR literal text calls to FOUR distinct documents, each read once. Four terms (missing scenarios, error paths, contradictions, terminology drift) are each asserted against whole analyst and reviewer documents: EIGHT assertions. Two analyze-token assertions follow, against analyst and the whole spec skill. Two final diagnostic/body pairs each check converge and Validation Reviewed tokens: FOUR assertions. Total: FOURTEEN assertIn calls within ONE selected test, not fourteen tests or fourteen proven independent predicates. The diagnostic `.ai/agents/reviewer.md#Passes` is not another read.

The reviewer body is precisely `reviewer.split("## Passes", 1)[1].split("\n## ", 1)[0]`: first literal start occurrence anywhere, without anchoring or a required following newline; missing start raises IndexError. End is the first newline/level-two prefix, or the remaining suffix when absent. Current capture begins after reviewer.md:44 and ends before newline/`## Severity` at line53. The inline Validation Reviewed token at line48 remains captured; the separate heading at line123 is outside capture. Final review-skill checks use the whole skill. These are case-sensitive presence/extraction checks, not Markdown parsing or semantic analysis. `text` at lines26–27 calls `(ROOT / path).read_text()`.

Proposed EIGHT ordered patterns:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.ai/agents/analyst.md
.ai/agents/reviewer.md
.claude/skills/spec/SKILL.md
.claude/skills/review/SKILL.md
```

Production scope deliberately covers eager imports, lazy/decorator construction, unused non-test descendants and future supported scripts. That extra invalidation requires D2 approval. Exclude tests before restoring the selected module/helper. Four direct documents are explicit despite Markdown exemptions. AGENTS.md, lifecycle documents and validation-policy are not direct reads here; predecessor compatibility fixtures retain their own inputs.

## Requirements

- R1: The exporter MUST register only the exact repository-root argv above as python-semantic-lens-doc-contract. Class/module, sibling, discovery, option, alias and other-interpreter variants MUST remain unregistered unless already registered. All twelve delivered profiles MUST retain their complete entries, IDs, argv, ordered inputs, rationales, exports, tests and positive sibling registrations.
- R2: The profile MUST export exactly the eight ordered patterns above before positive supplements, with per-pattern rationales. An independent source-derived oracle MUST resolve the exact class/method, four literal text calls/paths, four-term/two-document bindings and assertions, two analyze checks, chained split/maxsplit/index semantics, and final two diagnostic/body pairs and assertion bindings. Reviewed method/setup fingerprints MUST remain pinned independently of PROFILES and source-under-test regeneration. Guards MUST cover root/import/text setup, disk_tmp/called scratch.require_disk, eager lifecycle/review_guard/ledger initialization, lazy setup and protected/nested decorate construction, and reject freshly demonstrated reachable excluded additions. Source extraction MUST stay separate from actual execution/count evidence. Uncalled baseline/flat/producer bodies are conservative pins only, not demonstrated reads. No TIERS/REQUIRED/STAGES runtime-attribute oracle is part of the selected assertion.
- R3: Public text/JSON export MUST preserve token/Inputs/rationale parity, supplement order, root/path/inventory validation, nonexecution and refusal behavior. Export MUST neither import/execute the selected test, evaluate its assertions, adopt Inputs nor record evidence. Every missing required literal, unsafe/unsupported path and unknown command MUST refuse nonzero with a reason and no usable candidate. Existing documents failing selected assertions MUST remain exportable through path-only validation.
- R4: Adoption MUST remain explicit, advisory and manual. Inference, full suites, matching, freshness, schemas, gates and producer receipt exclusions MUST remain unchanged. The guide MUST document the exact command/ID, four reads and fourteen presence assertions within one test, exact split semantics, conservative extra invalidation and repository-file completeness limits. It MUST distinguish those static checks from semantic-lens effectiveness, actual analysis/review/analyze/converge behavior, governance/enforcement and native/model/session qualification. Selected source/assertions MUST remain unchanged; export MUST NOT imply VERIFIED evidence.
- R5: An isolated framework fixture MUST drive public export and real lifecycle run/reuse. Independently captured unittest output MUST prove exactly one selected test executed and passed before exit interpretation, with matching argv/ordered Inputs/exit and stable selected repository bytes. Unchanged evidence and unrelated-test/non-input-document edits MUST REUSE; separate assertion-preserving edits to EACH of the four direct documents, target, disk helper, representative production import and new supported non-test script MUST RERUN. Exact bytes MUST be confirmed and restored. Framework MUST acquire no knowledge bundle. FOURTEEN disposable cases from the matrix below MUST each produce exactly one selected execution and the intended first assertIn failure, preserving all earlier assertions and capture boundaries. Freshness edits MUST remain separate. Missing-marker IndexError, alternate capture, earlier collateral assertion, import/setup/CLI or zero-test failures MUST NOT count. A mismatch in source/capture/isolation/count MUST return for scope review rather than silently change approved breadth.
- R6: A separate ordinary adopter fixture MUST explicitly adopt public export, become VERIFIED after independently proven actual one-test execution, retain VERIFIED after unrelated-test/non-input-document edits, and become STALE after separate assertion-preserving edits to EACH direct document, target/helper, representative production import and new supported script. Unmatched ordered declarations and argv identity MUST yield UNVERIFIED under existing rules; receipt exclusions MUST remain effective. SIX confirmed disposable broken controls MUST be rejected: omission of each of four direct documents, loose command matching and acceptance of actual zero-test execution. Each omission MUST fail its intended freshness criterion while its document edit still passes the selected test. Actual-zero MUST ignore the selector in a real empty suite, independently confirm Ran 0 tests, then reject count before Python-dependent exit interpretation; a loader _FailedTest is insufficient. Every control MUST confirm mutation bytes, intended rejection and restoration without historical evidence edits.

## Acceptance

Proposed SemanticLens classes belong in .ai/scripts/tests/test_assurance_inputs.py and do not yet exist. Missing classes, counts or end states fail acceptance. No command below may run during drafting. Independent two-pass review and the required full framework gate follow implementation. Historical evidence supplies no thirteenth-profile proof.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py SemanticLensProfileTests` checks exact registration/root/argv, variants and preservation of all twelve complete profiles/exports/positive siblings. No obsolete negative expectation is presumed.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py SemanticLensDependencyTests` checks exact order/rationales, independent ledger selection, the four-read/loop/analyze/split/body oracle and reviewed method/setup pins, exclusions and future supported descendants. Each newly claimed reachable addition MUST fail actual selected execution absent excluded data, pass exactly ONE supplied-data selected test, then receive intended boundary rejection. Confirm bytes and restoration. Derive variants afresh; prior fourteen reached variants are not proof. AST additions go after docstrings and BEFORE the first statement's earliest decorator. Uncalled bodies may be pinned only.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py SemanticLensExportTests` checks formats/supplements, immutability/nonexecution, every missing required literal and unsafe boundary, plus path-only export of assertion-failing existing document fixtures.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py SemanticLensCompatibilityTests` checks guide claims/limits and complete predecessor/mechanism preservation. Existing AssuranceDoc helper MUST retain its original ten-entry baseline and per-entry/export checks; AgentsBudget helper MUST retain its eleven-entry baseline and per-entry/export checks. Their exact current-total guards may advance twelve to thirteen only, retaining exact cardinality. New checks MUST compare all twelve complete predecessor entries; blanket weakening is forbidden.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py SemanticLensFrameworkEndToEndTests SemanticLensFailureTests` checks independent actual-one/count/bytes and framework identity/freshness outcomes, plus all FOURTEEN intended assertion failures in the matrix with isolated mutation bytes and exact restoration.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py SemanticLensAdopterEndToEndTests SemanticLensControlTests` checks adopter states/identities/receipt exclusions and SIX confirmed broken controls, including four assertion-preserving omissions and actual-zero count-first rejection.

## Assertion-failure matrix and isolation

Each row represents separate disposable cases, not concurrent edits. Replace all exact occurrences of the chosen token within the actually asserted scope with a distinct nonmatching token; preserve the rest of the document and earlier checked tokens. Confirm original and changed bytes, independently resolve the capture, confirm absence in the asserted scope, execute the exact selector, establish one test and intended first assertion failure, then restore exact bytes. Export remains path-only and must succeed. The selected source, start/end markers and earlier predicates remain unchanged.

| Cases | Token | Asserted scope | Count |
| --- | --- | --- | --- |
| T1–T8 | each of missing scenarios; error paths; contradictions; terminology drift | each whole analyst and whole reviewer document | 8 |
| A1–A2 | lifecycle.py analyze | whole analyst; whole spec skill | 2 |
| F1–F4 | each of lifecycle.py converge; ## Validation Reviewed | reviewer extracted Passes; whole review skill | 4 |

Current source-text inspection resolves the relevant occurrences: all four analyst terms and its analyze token occur on line26; reviewer terms occur on line48, with error paths ALSO on line26. Thus the reviewer error-path case removes both occurrences. Spec skill analyze is on line13. Reviewer final tokens occur in captured line48; whole-document later converge/Validation Reviewed occurrences at lines123–124 do not satisfy the extracted-body checks and stay intact. Both review-skill final tokens occur on line11. Whole-scope removal targets all occurrences, not just the first. Replacing one token leaves the other tokens on those same lines intact. Removing inline Validation Reviewed does not alter newline/level-two capture delimiters. This is a source-derived isolation design pending actual proof, not a claim that fourteen predicates are mutually independent.

The four omission controls use separate harmless appended whitespace outside the capture-sensitive content, confirm changed bytes and actual selected PASS, and require the intended freshness rejection after omitting precisely that document. They are distinct from the fourteen failure cases. The loose-matching control must demonstrate intended identity rejection. The actual-zero control uses a real empty suite that ignores the selector, never a missing-method loader failure.

## Constraints

Existing literal catalog/export mechanism; Python3.9+, standard library and unittest conventions. No new options, schemas, normalization, loader, inference, automatic adoption, gates or approval authority. Existing tracked/supported nonignored-untracked ledger inventory rules remain. Runtime/executable/environment, temporary storage/mount state, ignored files and external mutable data remain outside repository-file completeness. Unresolved reads require review and retention of current scope.

Preserve all TWELVE complete profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract, python-installer-doc-contract, python-validation-policy-contract, python-audit-doc-contract, python-analysis-convergence-doc-contract, python-stage-doc-contract, python-tier-doc-contract, python-assurance-doc-contract and python-agents-budget-contract.

EVERY repository command uses explicit cwd /home/enramosjr/Projects/agentic-assurance-7. Retain branch claude/assurance-increment-7 and delivered HEAD e702aa9a2be85992d0590d14d691e74adcfcec3d. ALL docs/assurance stay ignored/local/UNCOMMITTED. Preserve 5l/5k/5j/5i/5h and earlier canonical evidence and tested scopes. During drafting: no source edits, product tests/runtime candidate import, implementation plan, native/model evaluation, session registration/allocation, fixture trust grants, historical rescoring/evidence modification, new worktree, base refresh, invoking-framework knowledge bundle, commit/push/PR/merge or autonomy driver. Native allocations remain consumed; 5l delivery approval is fulfilled and does not carry forward.

## Non-goals

Broader class/module/sibling registration; strengthening selected assertions; executing extracted/lifecycle commands; lifecycle runtime attribute validation; actual semantic analysis or semantic-lens effectiveness; actual review, governance/enforcement or native/model/session qualification; general dependency discovery or minimum scope; reduced full gates, automatic adoption or savings claims; planning before explicit SPEC approval or implementation before separate plan approval.

## Assumptions

D1–D4 below are approved, including fourteen intended assertion failures and six broken controls. Earlier proposed wording records drafting context and is superseded by this approval. The initial restriction on drafting an implementation plan is fulfilled; implementation remains pending separate plan approval. Source inspection establishes the read/assertion/capture structure, not execution/count or effectiveness. Framework mode has no capability baseline/bundle to merge or initialize. Existing evidence supplies no thirteenth-profile PASS/REUSE. Python persona considerations materially shaping the draft are import-time/called-helper/decorator boundaries, external temporary-storage assumptions, isolated exact-byte restoration and independent count-first proof.

## Open questions

None. The user approved the specification and recommended D1–D4, including fourteen assertion failures and six broken controls. Ready for planning only.

## Approved decisions

The recommended defaults below are approved; alternatives remain decision context. Separate plan approval is required before implementation.

- D1: Approve the exact semantic-lens method and python-semantic-lens-doc-contract ID, select another candidate, or stop? Recommended: exact method/ID only. Evidence cannot authorize registration.
- D2: Approve eight ordered patterns, conservative extra invalidation, independent four-read/loop/analyze/split/body oracle and reviewed setup pins, or require a smaller independently justified closure? Recommended: eight patterns and stated limits.
- D3: Approve actual-one/count proof, framework/adopter identities/freshness for all four documents and source/helper/production/additions, argv/ordered declarations/receipt exclusions, freshly reached boundaries, FOURTEEN intended assertion failures and SIX broken controls with the resolved capture/isolation/count rules? Recommended: yes. Breadth/count changes return for scope review.
- D4: Preserve all twelve complete profiles and existing mechanisms/manual adoption, limiting new claims to case-sensitive presence/chained split extraction and declared-file freshness? Recommended: yes, with all semantic-effectiveness/runtime/governance/native/model/session exclusions above.

## Investigation evidence

Read handoff-5m FIRST and leading authoritative 5l delivery update. repo.py context confirms framework, expected local HEAD/branch/equal upstream refs and clean tracked state; remote_verified false. New L2 declared after authorized sandbox escalation for shared Git scratch lock. Required read-only analyst independently rederived assertions and capture/isolation; no candidate execution.

Inspected test_lifecycle_conformance.py:15–27,68–123; literal PROFILES in assurance_inputs.py:17–209; existing generic refusals at test_assurance_inputs.py:190–202; exact cardinality/baseline guards at4439–4460 and4976–4996. Fresh structured regex found neither proposed selector nor ID. Inspected disk_tmp:10–20, scratch.require_disk:11–26, lifecycle:41–77 and protected decorator sites1011/1209/1321, review_guard ledger import/protected/nested decorate, ledger initialization. Role/skill text was inspected as selected input data, not additional authorization. No product test, runtime candidate import or historical evidence mutation occurred.

## Draft validation

- `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5m.md` -> exit1, only High open-questions for D1–D4. Explicit human approval remains the blocker; no Intent approval is recorded.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5m.md` -> exit0, six requirements traced; no acceptance executed.
- `git check-ignore docs/assurance/specification-5m.md` -> exit0, ignored/local/uncommitted.
- `git diff --check` and `git status --short --untracked-files=no` -> exit0, clean tracked state.

No implementation plan drafted. Retrospective and subsequent lifecycle stages remain pending future approved work.
