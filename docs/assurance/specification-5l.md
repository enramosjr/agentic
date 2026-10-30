# Spec: AGENTS encoded-text budget input profile

Approved by human:enramosjr in this chat on 2026-10-29 America/Chicago: “Approved. Proceed with the implementation plan for 5l using the recommended D1–D4 decisions, including the five boundary cases. Keep implementation pending separate plan approval.” L2; analyst role; Python principal engineer. Spec approval permits planning only; implementation requires SEPARATE plan approval. Acceptance commands are future checks, not execution evidence.

## Problem and outcome

Maintainers have eleven delivered literal Python input profiles, but no exact-method profile for the existing AGENTS budget check. Add one explicitly adopted profile through the existing exporter, with reviewed repository-file inputs and controlled freshness evidence. This framework has no knowledge bundle or structured capability baseline; this standalone specification initializes neither and revises no historical evidence.

## Users and scenarios

A maintainer requests public export from the repository root for exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py AgentsBudget.test_agents_md_stays_below_its_cold_start_budget
```

Proposed ID: `python-agents-budget-contract`. Broader class/module and sibling registration are outside scope.

The selected source at test_lifecycle_conformance.py:167–168 is one assertion within one test:

```python
self.assertLess(len(text("AGENTS.md").encode()), 30_000)
```

`text` at lines26–27 returns `(ROOT / path).read_text()` without encoding/newline arguments. Default text decoding and universal-newline translation precede no-argument UTF-8 `str.encode()`. The strict comparison counts the re-encoded returned string, which can differ from raw file bytes. It measures neither characters nor tokens nor latency. Source extraction is not actual execution/count proof.

AgentsBudget class construction sets BASELINES and compiles NORMATIVE. The selected method calls neither baseline nor flat: historical Git calls, skip behavior, linked-document reads and normative/heading preservation belong to sibling tests. There is no selected lifecycle runtime-attribute assertion, extracted/lifecycle command execution or file copy. Shared imports and setup still matter.

Proposed ordered scope:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
AGENTS.md
```

Production scope conservatively covers eager imports, lazy/decorator construction, unused non-test descendants and future supported scripts. Extra invalidation is intentional and requires D2 approval. Exclude unrelated tests before restoring the selected module/helper. AGENTS.md is the sole direct document, explicit despite Markdown freshness exemptions. Lifecycle documents and validation-policy are not this method's direct reads; predecessor compatibility fixtures retain their own required inputs.

## Requirements

- R1: The exporter MUST register only the exact repository-root argv above as python-agents-budget-contract. Class/module, sibling, discovery, option, alias and other-interpreter variants MUST remain unregistered unless already registered. All eleven delivered profiles MUST retain their complete entries, IDs, argv, ordered inputs, rationales, exports, tests, positive sibling registrations and behavior.
- R2: The profile MUST export exactly the five ordered patterns above before positive supplements, with per-pattern rationales. An independent source-derived oracle MUST resolve the exact class/method, sole literal text call/path, nested no-argument encode(), len(), strict assertLess and literal 30000 bound. Reviewed method and relevant setup fingerprints MUST remain pinned. Boundary guards MUST cover root/import/text setup, disk_tmp/called scratch.require_disk, eager lifecycle/review_guard/ledger initialization, lazy setup and protected/nested decorate construction. Guards MUST reject drift and freshly confirmed reachable excluded additions. Conservative pins MUST NOT imply general dependency discovery or execution of uncalled baseline/flat/producer bodies. Source extraction MUST remain separate from actual execution/count proof. No section/token/row or TIERS/REQUIRED/STAGES oracle is part of this assertion.
- R3: Public text/JSON export MUST preserve token/Inputs/rationale parity, supplement order, root/path/inventory validation, nonexecution and refusal behavior. Export MUST neither import/execute the selected test, evaluate its assertion, adopt Inputs nor record evidence. Missing required literals and unsafe/unsupported paths or unknown commands MUST refuse nonzero with a reason and no usable candidate. Existing inputs that fail the selected assertion MUST remain exportable through path-only validation.
- R4: Adoption MUST remain explicit, advisory and manual. Inference, full suites, matching, freshness, schemas, gates and producer receipt exclusions MUST remain unchanged. The guide MUST describe the exact command/ID, one read/one strict assertion within one test, default decoding/newline translation followed by UTF-8 re-encoding, conservative extra invalidation and repository-file completeness limits. It MUST distinguish re-encoded text from raw bytes, character/token counts, latency, semantics, historical/normative preservation and governance/enforcement/native/model/session qualification. Export MUST NOT imply VERIFIED evidence. Selected source/assertion MUST remain unchanged.
- R5: An isolated framework fixture MUST drive public export and real lifecycle run/reuse. Independently captured unittest output MUST prove exactly one selected test executed and passed before exit interpretation. Recorded argv, ordered inputs and exit MUST match export; selected repository bytes MUST remain unchanged during execution. Evidence MUST REUSE unchanged and after unrelated-test/non-input-document edits, and MUST RERUN after separate assertion-preserving edits to AGENTS.md, target, disk helper, representative production import and new supported non-test script. Edits MUST restore exact bytes and document edits MUST have observed passing margin. The invoking framework MUST acquire no knowledge bundle. FIVE disposable encoding/boundary cases MUST prove the matrix below: TWO passes and THREE intended assertLess failures. Each MUST confirm fixture bytes, independent expected decoded/re-encoded lengths, exactly one selected execution, intended outcome and restoration. Export MUST succeed for every existing valid-text fixture. Freshness edits MUST remain separate from assertion-failure fixtures. No decode/import/setup/CLI/zero-test failure may qualify as a threshold failure. If decoding, source shape, boundary values or isolation differs, work MUST stop for scope review rather than silently change approved breadth.
- R6: A separate ordinary adopter fixture MUST explicitly adopt public export, become VERIFIED after independently proven actual one-test execution, remain VERIFIED after unrelated-test/non-input-document edits, and become STALE after separate assertion-preserving edits to sole document, target/helper, representative production import and new supported non-test script. Unmatched ordered declarations and argv identity MUST yield UNVERIFIED under existing rules; receipt exclusions MUST remain effective. THREE confirmed disposable broken controls MUST be rejected: sole-document omission, loose command matching and acceptance of actual zero-test execution. Omission MUST fail the intended freshness assertion while the document edit leaves the selected test passing. Actual-zero MUST ignore the selector in an actual empty suite, independently confirm Ran 0 tests, then reject count before Python-dependent exit interpretation; one loader _FailedTest is insufficient. Every control MUST confirm mutation bytes and its intended failure without historical evidence edits.

## Acceptance

Proposed AgentsBudget classes belong in .ai/scripts/tests/test_assurance_inputs.py and do not yet exist. Missing classes/counts/end states fail acceptance. These commands MUST NOT run during drafting. Independent two-pass review and the required full framework gate follow implementation; historical results verify no twelfth profile.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetProfileTests` checks exact ID/argv/root matching, variant refusal and complete preservation of all eleven prior profiles and positive siblings. Fresh inspected source supplies no obsolete negative expectation to replace.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetDependencyTests` checks ordered patterns/rationales, independent ledger selection, one-read/encode/len/strict-bound oracle, reviewed method/setup pins, unrelated exclusions and future supported non-test descendants. Every newly claimed reachable addition MUST first fail actual selected execution with excluded data absent, then pass exactly one selected test after supplying data, before intended boundary rejection. Derive and enumerate variants afresh; historical thirteen variants supply no next-profile proof. Confirm mutation bytes; insert AST body additions after docstrings and BEFORE the earliest decorator of the first statement. Uncalled bodies may be pinned, never claimed reached.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetExportTests` checks public formats, supplements, immutability/nonexecution, every missing required literal and unsafe boundary, and path-only export for assertion-failing valid-text inputs.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetCompatibilityTests` checks guide claims/limits and preservation of all eleven complete profiles, inference/full suites, matching, freshness, schemas, gates and receipt exclusions through existing mechanisms. Prior fixtures retain their own required documents.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetFrameworkEndToEndTests AgentsBudgetFailureTests` checks independent actual-one/count proof, byte stability, identities and framework freshness outcomes, plus all five encoding/boundary cases with exactly two passes and three intended assertion failures as specified below.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetAdopterEndToEndTests AgentsBudgetControlTests` checks every adopter state/identity and receipt exclusion plus three confirmed broken controls, including sole-doc omission and actual-zero count-first rejection.

## Encoding and boundary matrix

Fixtures use independently constructed valid UTF-8 bytes. Confirm the selected child's default decoder is UTF-8 using an independent disposable probe under the same launch environment; declare/confirm this fixture assumption without changing the selected argv/source or exporter environment policy. Refuse/stop if the assumption is unmet. Expected strings/counts MUST be derived independently of the selected text helper and source oracle, with actual raw bytes confirmed. ASCII/LF cases use N-1 ASCII `a` bytes followed by LF, hence N decoded characters and N re-encoded bytes.

| Case | Actual fixture bytes | Expected normalized characters | Expected re-encoded length | Actual selected outcome |
| --- | --- | --- | --- | --- |
| Below | 29998 ASCII a + LF | 29999 | 29999 | one test PASS |
| Equal | 29999 ASCII a + LF | 30000 | 30000 | one test; intended assertLess FAIL |
| Above | 30000 ASCII a + LF | 30001 | 30001 | one test; intended assertLess FAIL |
| Multibyte | UTF-8 encoding of 15000 U+00E9 characters | 15000 | 30000 | one test; intended assertLess FAIL |
| Newlines | ASCII a, CR, LF repeated 10000 times, raw length30000 | 20000 after universal-newline translation | 20000 | one test PASS |

CR and LF denote actual carriage-return and line-feed bytes. The multibyte failure distinguishes encoded length from character count; the CRLF pass distinguishes normalized/re-encoded length from raw-file size. These are FIVE cases with THREE intended assertion failures, not the preceding profile's29 assertions. There is only ONE selected assertion and ONE test per execution. Invalid decoding is outside this matrix and cannot stand in for threshold evidence.

## Constraints

Use the existing literal catalog/export mechanism, Python3.9+, standard library and unittest conventions. No new options, schemas, normalization, loader, inference, adoption automation, gates or approval authority. Inventory retains tracked/supported nonignored-untracked ledger rules. Runtime executable/default decoding/locale/environment, mount state, temporary storage, ignored files and external mutable data remain outside repository-file completeness claims. Unresolved additional reads require review and retention of current scope.

Preserve all ELEVEN complete profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract, python-installer-doc-contract, python-validation-policy-contract, python-audit-doc-contract, python-analysis-convergence-doc-contract, python-stage-doc-contract, python-tier-doc-contract and python-assurance-doc-contract.

Run EVERY repository command with explicit cwd /home/enramosjr/Projects/agentic-assurance-7. Retain branch claude/assurance-increment-7 and delivered HEAD cf158b53b9c164b22a3172792ab3c86980106e0e. Keep ALL docs/assurance ignored/local/UNCOMMITTED. Preserve5k/5j/5i/5h and earlier evidence and tested source/runtime scopes. During drafting: no source edits, product tests/runtime candidate import, implementation plan, native/model evaluation, session registration/allocation, fixture trust grant, historical rescoring/evidence modification, new worktree, base refresh, invoking-framework knowledge bundle, commit/push/PR/merge or autonomy driver. Native allocations remain consumed;5k delivery authorization is fulfilled and does not carry forward.

## Non-goals

Class/module/sibling registration; strengthening selected assertions; raw-file-size, character/token, cold-start latency or performance claims; semantic/normative/heading/history preservation; lifecycle runtime attribute validation; extracted-command execution; dynamic governance/enforcement, authentication or native/model/session qualification; general dependency discovery; minimum input set; reduced full gates; automatic adoption or savings claims; planning before spec approval or implementation before separate plan approval.

## Assumptions

D1–D4 and the five boundary cases below are approved. Earlier proposed wording retains drafting context and is superseded by this approval. The initial restriction on drafting an implementation plan is fulfilled; implementation remains pending separate plan approval. Source inspection establishes one direct document read and one strict assertion, not actual execution/count. UTF-8 default decoding will be independently confirmed for the disposable acceptance environment; it is no guarantee about other runtimes. Newline translation is part of the selected read_text behavior and is tested separately. No candidate product check/runtime import has run during drafting. Framework mode has no capability baseline/bundle to merge or initialize. Existing evidence supplies no twelfth-profile PASS/REUSE.

## Open questions

None. The user approved the specification and recommended D1–D4, including the five boundary cases. Ready for planning only.

## Approved decisions

The recommended defaults below are approved. Alternatives remain as decision context; separate plan approval is still required before implementation.

- D1: Approve exactly AgentsBudget.test_agents_md_stays_below_its_cold_start_budget and python-agents-budget-contract, choose another candidate, or stop? Recommended: exact method/ID only. Evidence cannot authorize registration.
- D2: Approve the five ordered patterns, conservative extra production invalidation and independent one-read/encode/len/strict-bound oracle with reviewed setup pins, or require a smaller independently justified closure? Recommended: the five patterns and stated limits. Invalidation breadth needs human choice.
- D3: Approve actual-one-test proof; framework/adopter identity/freshness, exact argv/ordered declarations and receipts; freshly demonstrated reached boundaries; FIVE encoding/boundary cases (TWO passes, THREE intended failures), UTF-8 environment confirmation and THREE broken controls? Recommended: yes, including explicit CRLF and multibyte cases. Acceptance breadth and counts need human approval; mismatch returns for review.
- D4: Preserve all eleven complete profiles and existing mechanisms/manual adoption, limiting new claims to the strict re-encoded-text budget and declared repository-file freshness? Recommended: yes, with all stated raw-byte/character/token/latency/semantics/history/enforcement/native/model/session limits.

## Investigation evidence

Nonexecuting inspection only:

- handoff-5l.md read FIRST, followed by the authoritative Delivery complete update in implementation-5k.md: closed delivery, restrictions and no transferred implementation/delivery approval.
- repo.py context --json: framework, expected branch/HEAD, clean tracked state and equal local upstream refs; remote_verified false, no new remote check.
- test_lifecycle_conformance.py:15–27,150–187: root/import/text setup, exact selected method and sibling-only historical helpers.
- disk_tmp.py:10–20; scratch.py:11–26: called storage probe and external environment/mount boundary.
- lifecycle.py:41–77,1011,1209,1321; review_guard.py:23–26,629–639; ledger.py:10–29: eager imports, lazy setup, decorator construction and constants. Wrapped producer bodies remain uncalled by this selected test.
- Fresh structured regex search in assurance_inputs.py/test_assurance_inputs.py found neither proposed selector nor ID. Existing generic RefusalTests190–202 cover discovery/full-runner/unsafe cases; no obsolete negative replacement is presumed.
- Required read-only analyst independently recommended the five-case2PASS/3FAIL matrix and UTF-8 probe. Python persona materially affected import-time/called-helper boundaries, external decoding/storage limits and independent count-first execution proof.

## Draft validation

- `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5l.md` -> exit1; only High open-questions finding for D1–D4. This is the explicit human-approval blocker, not a resolved contract.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5l.md` -> exit0; six requirements traced. No acceptance command executed.
- `git check-ignore docs/assurance/specification-5l.md` -> exit0; draft remains ignored/local/uncommitted.
- `git diff --check` and `git status --short --untracked-files=no` -> exit0; tracked state clean.

The initial validation above describes the unapproved draft. Human specification approval is recorded at the top; analyze/trace and Intent recording follow before planning. New L2 declaration initially hit a read-only shared Git scratch lock; the same authorized command succeeded with sandbox escalation. No source/product/native/model/session action or knowledge bundle was created. Retrospective and later gates remain pending future approved work.
