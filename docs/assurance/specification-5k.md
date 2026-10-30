# Spec: assurance documentation section and recording-row input profile

Approved by human:enramosjr in this chat on 2026-10-29 America/Chicago: “Approved. Proceed with the implementation plan for 5k using the recommended D1–D4 decisions. Keep implementation pending separate plan approval.” L2; analyst role; Python principal engineer. Specification approval authorizes planning only; implementation requires SEPARATE plan approval. Acceptance commands below are future checks, not execution evidence.

## Problem and outcome

Maintainers have ten delivered literal Python input profiles but no exact-method profile for the existing assurance-documentation check. Add one explicitly adopted profile through the existing exporter, with reviewed repository inputs and controlled freshness evidence. This framework has no knowledge bundle or structured capability baseline; this standalone specification initializes neither and revises no historical evidence.

## Users and scenarios

A maintainer invokes the exporter from the repository root for exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Assurance.test_assurance_documented
```

Proposed ID: `python-assurance-doc-contract`. Broader Assurance class/module and sibling registration are outside scope.

The selected method calls `text(".ai/lifecycle.md")` inside `re.search(r"(?s)## Assurance status\n(.*?)(?=\n## )", ...)`, asserts the match is not None, assigns `body = section.group(1)`, and requires these case-sensitive substrings in body through TWO separate literal tuples/loops:

```text
Tuple 1 (20):
- Verify:
- Inputs:
VERIFIED
STALE
FAILED
UNVERIFIED
INVALID
MANUAL
UNDECLARED
lifecycle.py assure
--run
--changed
--strict
covers only that command on those inputs
whole tree
squash
runtime executable changed
does not combine with
python3 .ai/scripts/assurance_demo.py
python3 .ai/scripts/assurance_measure.py

Tuple 2 (7):
judgment (attested, not verified):
## Validation Reviewed
Accept-risk:
risk_acceptance
not bound to
`note:`
unauthenticated
```

It separately calls `text(".ai/lifecycle.md")` for `assertRegex` with `r"(?m)^\| Assurance \| `assure"` and message `Recording table row`. These are TWO literal reads of ONE document. The source-derived count is 27 substring assertions plus the section-match and row-regex assertions: 29 assertions within ONE test, not 29 tests. Actual execution/count proof remains a separate future obligation. The selected body directly accesses no lifecycle runtime attribute, executes no extracted/lifecycle command and copies no files. Shared imports/setup still matter.

The section regex is unanchored and DOTALL. It takes the first matching capture, requires literal heading text followed by newline, and requires a later newline/`## ` prefix for termination. It is not a Markdown parser: a longer heading prefix can still contain the unanchored start substring. At the delivered baseline the capture begins after line 179 and ends before `## Evals` at line 291, including `### Python validation input profiles` and `### Governed architecture constraints`. Inline `## Validation Reviewed` is a body token, not a terminating newline/heading prefix. Future guide additions inside the capture participate in its token checks. The separate MULTILINE row regex checks a start prefix only, without an end anchor; it validates neither a complete table row nor its command. The existing matching row is outside the captured body, at line 175. Presence checks establish no documentation semantics, statuses, actual assure behavior, freshness/enforcement, command validity, authentication or native/model/session qualification.

Proposed ordered scope:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.ai/lifecycle.md
```

The production scope conservatively includes eager imports, lazy-loader/decorator construction, unused non-test descendants and future supported scripts. Extra invalidation is deliberate and needs D2 approval. Exclude unrelated tests before restoring the selected module and imported helper. The final literal is the sole direct document, explicit despite Markdown freshness exemptions. Root AGENTS, `.ai/docs/lifecycle.md` and validation-policy are not this method's direct reads. Predecessor compatibility fixtures retain their own required inputs, including AGENTS for earlier profiles.

## Requirements

- R1: The exporter MUST register only the exact repository-root argv above as `python-assurance-doc-contract`. Class/module, sibling, discovery, option, alias and other-interpreter variants MUST remain unregistered unless already registered. All ten delivered profiles MUST retain their complete IDs, argv, ordered inputs, rationales, exports, tests, positive sibling registrations and behavior.
- R2: The profile MUST export exactly the five ordered patterns above before positive supplements, with per-pattern rationales. An independent source-derived oracle MUST resolve the section regex/flags, BOTH literal text calls and sole path, assigned match/body/group(1), BOTH distinct literal tuples and loop bindings, substring assertions into captured body, and separate whole-document row regex. Reviewed method and relevant setup fingerprints MUST remain pinned. The boundary MUST cover root/import/text setup, disk_tmp/called scratch.require_disk, eager lifecycle/review_guard/ledger initialization, lazy setup and protected/nested decorate construction. Guards MUST reject boundary drift and freshly confirmed reachable excluded additions. Conservative pins MUST NOT imply universal dependency discovery or execution of uncalled producer bodies. Unrelated tests/non-input documents MUST remain excluded. Source extraction MUST remain separate from actual selected execution/count evidence; no TIERS/REQUIRED/STAGES runtime oracle is part of this method's assertions.
- R3: Public text/JSON export MUST preserve existing token/Inputs/rationale parity, supplement order, root/path/inventory validation, nonexecution and refusal behavior. Export MUST neither import/execute the selected test nor evaluate its assertions, adopt Inputs or record evidence. Missing required literals and unsafe/unsupported paths or unknown commands MUST refuse nonzero with a reason and no usable candidate. Existing inputs with failing selected assertions MUST remain exportable through path-only validation.
- R4: Adoption MUST remain explicit, advisory and manual. Existing inference, full suites, matching, freshness, schemas, gates and producer receipt exclusions MUST remain unchanged. The guide MUST name the exact command/ID, two reads of one document, section/capture and both token-loop checks, separate row-prefix check, conservative extra invalidation and read-completeness limits. It MUST state the regex/presence/semantics limits above and distinguish 29 assertions from one test. Export MUST NOT imply VERIFIED evidence or dynamic governance/native/model/session qualification, and selected assertions MUST remain unchanged.
- R5: An isolated framework fixture MUST drive public export and real lifecycle run/reuse. Independently captured unittest output MUST prove exactly one selected test executed and passed before exit interpretation; source extraction alone MUST NOT supply this proof. Recorded argv, ordered inputs and exit MUST match export, with selected repository bytes unchanged during execution. Evidence MUST REUSE unchanged and after unrelated-test/non-input-document edits, and MUST RERUN after separate assertion-preserving edits to the sole direct document, target, disk helper, representative production import and new supported non-test script. Edits MUST restore original bytes. The invoking framework MUST acquire no knowledge bundle. TWENTY-NINE separate disposable failures MUST fail actual selected execution at the intended assertion while export succeeds: eliminate all section-regex matches (one), remove all occurrences of each of the 27 body tokens from the actual captured scope separately (27), and eliminate all whole-document row-prefix matches (one). Each MUST confirm mutation bytes, exactly one selected test, the intended assertion failure and restoration. Earlier assertions MUST remain satisfied for each targeted failure. Removing VERIFIED necessarily also removes its substring occurrence within later UNVERIFIED; this later collateral loss is permitted, while the first failure MUST be VERIFIED. UNVERIFIED removal MUST preserve other earlier VERIFIED occurrences. Section failure MUST NOT fall through to another matching capture; body failures MUST retain the intended capture boundaries and avoid incidental earlier failures; row failure MUST retain all body checks. Assertion-preserving freshness edits MUST remain distinct from static failures. Different tuple counts, capture/matching structure or inability to isolate intended first failures MUST stop for scope review rather than silently change approved breadth.
- R6: A separate ordinary adopter fixture MUST explicitly adopt public export, become VERIFIED after independently proven actual one-test execution, remain VERIFIED after unrelated-test/non-input-document edits, and become STALE after separate edits to the sole direct document, target/helper, representative production import and new supported non-test script. Unmatched ordered declarations and argv identity MUST yield UNVERIFIED under existing rules; receipt exclusions MUST remain effective. THREE confirmed disposable broken controls MUST be rejected: sole-direct-document omission, loose command matching and acceptance of actual zero-test execution. Omission MUST fail the intended freshness assertion while the assertion-preserving document edit leaves the selected check passing. Actual-zero MUST ignore the selector in an actual disposable empty suite, independently confirm Ran 0 tests, then reject count before Python-dependent exit interpretation. A missing method yielding one loader _FailedTest is insufficient. Every control MUST confirm mutation bytes and its intended failure without modifying historical evidence.

## Acceptance

Proposed AssuranceDoc classes below belong in `.ai/scripts/tests/test_assurance_inputs.py`; they do not yet exist. Missing classes, counts or end states fail acceptance. These commands MUST NOT run during drafting. Independent two-pass review and the required full framework gate follow implementation; no historical result verifies this eleventh profile.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocProfileTests` checks exact ID/argv/root matching, variant refusal and complete preservation of all ten prior entries/rationales/behavior and positive siblings. Fresh inspected source supplies no obsolete negative expectation to replace.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocDependencyTests` checks five ordered patterns/rationales, independent ledger selection, section/two-call/two-tuple/body/row oracle and reviewed method/setup pins, unrelated exclusions and future supported non-test descendants. Every newly claimed reachable addition MUST first fail actual selected execution with excluded data absent, then pass exactly one selected test after supplying data, before intended boundary rejection. Derive variants afresh from current source, not thirteen historical variants. Confirm bytes; insert AST body mutations after docstrings and BEFORE the first statement's earliest decorator. Uncalled producer bodies may be pinned, never claimed reached.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocExportTests` checks public formats, supplements, immutability/nonexecution, every missing required literal and unsafe boundary, and path-only export when existing inputs fail selected assertions.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocCompatibilityTests` checks guide claims/limits and preservation of all ten complete profiles, inference/full suites, matching, freshness, schemas, gates and receipt exclusions through existing mechanisms. Prior compatibility fixtures retain their required documents; the new profile does not inherit their direct reads.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocFrameworkEndToEndTests AssuranceDocFailureTests` checks independent actual one-test/count proof, byte stability, identities and all framework freshness outcomes, separately from all 29 confirmed intended assertion failures, including overlap, first-capture and row-outside-capture controls described in R5.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocAdopterEndToEndTests AssuranceDocControlTests` checks every adopter state/identity and receipt exclusion plus three confirmed broken controls, including sole-doc omission and independent actual-zero rejection.

## Constraints

Failure isolation is assertion-specific: the section case MUST fail assertIsNotNone rather than group access; a heading demotion to `###` alone is insufficient for an unanchored regex. No failure may qualify through import/setup/CLI failure, AttributeError, fallback capture, an earlier incidental missing token or zero-test execution. The independent source oracle MUST resolve the non-None match assertion as well as the assignments and both token/row assertions. Twenty-seven target-token cases do not assert twenty-seven mutually independent predicates.

Use the existing literal catalog/export mechanism, Python 3.9+, standard library and unittest conventions. No new options, schemas, normalization, loader, inference, adoption automation, gates or approval authority. Inventory follows existing tracked/supported nonignored-untracked ledger rules. Runtime executable/environment, temporary storage/mount state, ignored files and external mutable data remain outside repository-file claims. Unresolved additional reads require review and retention of current scope.

Preserve all TEN complete profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract, python-installer-doc-contract, python-validation-policy-contract, python-audit-doc-contract, python-analysis-convergence-doc-contract, python-stage-doc-contract and python-tier-doc-contract.

Use ONLY `/home/enramosjr/Projects/agentic-assurance-7`, existing branch `claude/assurance-increment-7`, delivered HEAD `22c65521b281fce485ec5d10e45359cded53ec3f`. Keep ALL docs/assurance ignored/local/UNCOMMITTED. Preserve 5j/5i/5h and earlier evidence and tested source/runtime scopes; those results verify no eleventh profile. During drafting: no source edits, product tests/runtime candidate import, implementation plan, native/model evaluation, session registration/allocation, fixture trust grant, historical rescoring/evidence modification, new worktree, base refresh, invoking-framework knowledge bundle, commit/push/PR/merge or autonomy driver. All native allocations remain consumed; 5j delivery authorization is fulfilled and does not carry forward.

## Non-goals

Class/module/sibling registration; strengthening selected assertions; Markdown parsing, semantic documentation validation or complete table/command validation; actual statuses, assure execution/freshness/enforcement, governance behavior or authentication; runtime TIERS/REQUIRED/STAGES values; extracted-command execution; native/model/session qualification; general dependency discovery; minimum input set; reduced full gates; automatic adoption; savings claims; planning before spec approval or implementation before separate plan approval.

## Assumptions

D1–D4 below are approved decisions. Earlier descriptions as proposed retain drafting context and are superseded by this approval. The initial restriction on writing an implementation plan is fulfilled; implementation remains pending separate plan approval. Static source inspection establishes the two reads, 20+7 distinct tokens and source assertion count, not actual selected execution/count proof. Capture locations describe the delivered baseline; the matcher, not fixed line numbers, defines the scope. Framework mode has no capability baseline to merge or bundle to initialize. Historical evidence supplies no eleventh-profile PASS/REUSE. No candidate product check or runtime candidate import has run during drafting.

## Open questions

None. The user approved the specification and recommended D1–D4. Ready for planning only.

## Approved decisions

The recommended defaults below are approved; alternatives remain as decision context. All other restrictions remain, including separate plan approval before implementation.

- D1: Approve exactly Assurance.test_assurance_documented and python-assurance-doc-contract, choose another candidate or stop? Recommended: the exact method/ID only. Evidence cannot grant new registration authorization.
- D2: Approve the five ordered patterns and conservative extra production invalidation, or require a smaller independently justified closure? Recommended: five, with the independent section/two-call/two-tuple/body/row oracle and reviewed setup pins. Scope/invalidation breadth needs human choice.
- D3: Approve independent actual one-test proof, framework/adopter identity/freshness, argv/ordered-declaration identity, receipts and source-derived boundary challenges, including 29 intended first-assertion failures and three broken controls? Recommended: yes, with VERIFIED/UNVERIFIED overlap and capture boundaries as specified. Counts and acceptance breadth require approval; any source/mutation mismatch returns for review.
- D4: Preserve all ten complete profiles and existing mechanisms/manual adoption, limiting claims to the selected section extraction, case-sensitive body substrings and separate row-prefix presence? Recommended: yes, including all stated semantic/runtime/native/model/session limits.

## Investigation evidence

Nonexecuting inspection only:

- `docs/assurance/handoff-5k.md`, read first, and leading authoritative Delivery complete update in `implementation-5j.md`: checkout identity, closed delivery and restrictions. Older pending sections are superseded.
- `.ai/scripts/tests/test_lifecycle_conformance.py:15-27,252-267,297-298`: root/import/text setup, exact section/capture/two-tuples/two-reads/row assertions and unittest entry point.
- `.ai/lifecycle.md:175,179-291`: Recording row outside body, actual section capture including level-three subsections, inline Validation Reviewed token and next level-two delimiter.
- `.ai/scripts/assurance_inputs.py:17-179` and `test_assurance_inputs.py:175-202`: ten literal profiles and generic refusal cases. Fresh structured search found neither proposed ID nor selector in catalog/tests; no obsolete negative replacement is assumed.
- `.ai/scripts/lifecycle.py:41-77,1011,1209,1321`: eager imports, lazy setup and decorator applications; no runtime attribute assertion in the selected method.
- `.ai/scripts/tests/disk_tmp.py:10-20`, `.ai/scripts/scratch.py:11-26`: called require_disk and external cache/mount/environment boundaries.
- `.ai/scripts/review_guard.py:23-26,629-639`, `.ai/scripts/ledger.py:10-22`: eager initialization and protected/nested decorate construction. Uncalled wrapped producer bodies are not reached claims.
- Local `repo.py context --json` confirms framework, expected branch/HEAD and clean tracked state; local refs only, remote_verified false. No new remote check. New L2 declared after context; Intent remains unapproved.

Python persona materially affects import-time/called-helper boundaries, external storage/environment exclusions and count-first actual execution proof. The required read-only analyst rederived token count, whole-capture scope and the VERIFIED/UNVERIFIED overlap. No source/product execution or implementation plan is part of this draft.

## Draft validation

- `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5k.md` -> exit 1; only High open-questions finding for D1–D4. This is an intentional human-approval blocker, not a resolved contract.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5k.md` -> exit 0; six requirements traced. No acceptance command executed.
- `git check-ignore docs/assurance/specification-5k.md` -> exit 0; draft remains ignored/local/uncommitted.
- `git diff --check` and `git status --short --untracked-files=no` -> exit 0; tracked state clean.

New L2 declaration initially hit a read-only lifecycle scratch lock in the sandbox; the same authorized command succeeded with sandbox escalation. Intent is not recorded or approved. No product suite, selected test, runtime candidate import or implementation plan ran. Framework OKF synchronization is inapplicable because there is no bundle; no knowledge/log or records PASS is created or claimed. Retrospective and later lifecycle gates remain pending future approved work, not closed by this draft.
