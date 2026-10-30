# Implementation Plan: assurance documentation section and recording-row input profile

Approved by human:enramosjr in this chat on 2026-10-29 America/Chicago: “Approved. Implement the 5k plan through independent review and verification. Keep all changes uncommitted; no push, PR, merge, or base refresh.” Based on approved `docs/assurance/specification-5k.md`, R1–R6 and D1–D4. L2; planner role; Python principal engineer. Required read-only planner delegation completed. Intent is recorded. Implementation through independent review and verification is authorized; all changes remain uncommitted.

## Objective

Add exactly `python-assurance-doc-contract` through the existing literal input exporter for:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Assurance.test_assurance_documented
```

Provide independent source-boundary, actual execution/count, identity and freshness evidence while preserving all ten delivered profiles.

## Success criteria

- R1: Only the approved repository-root argv gains registration; all ten complete prior profiles, exports, tests and positive siblings remain intact.
- R2: Exactly five approved ordered inputs/rationales; independent section/two-read/two-tuple/body/row oracle and reviewed setup pins reject drift and freshly demonstrated reachable additions.
- R3: Public text/JSON export preserves path validation, supplements, refusals, nonmutation and nonexecution.
- R4: Guide publishes bounded static claims and explicit/manual/advisory adoption without changing assurance mechanisms or selected assertions.
- R5: Framework fixtures prove one actual passing selected test, identities, every freshness outcome and 29 intended assertion failures.
- R6: Adopter fixtures prove VERIFIED/STALE/UNVERIFIED behavior and receipt exclusion; three broken controls fail their intended criteria.

## Current state

`assurance_inputs.py:17–179` holds ten literal profiles. `check_paths:243–267` and `suggest:270–294` already implement path/inventory validation, exact root/argv selection and ordered supplements. No exporter algorithm change is needed.

`test_lifecycle_conformance.py:255–267` has six top-level statements: section assignment, non-None assertion, body assignment, two token loops and final row assertion. It reads `.ai/lifecycle.md` twice. The loops contain twenty and seven literal tokens. Its own assertions access no lifecycle runtime attribute.

The Recording row is at `.ai/lifecycle.md:175`, outside the first capture beginning after line 179 and ending before `## Evals` at line 291. The capture includes third-level Python-profile and governed-architecture subsections.

Reusable mechanisms in `test_assurance_inputs.py`:

- `Fixture:34–121`: disposable repositories, bounded subprocesses, public export/refusal and lifecycle helpers.
- `report_setup_digest:993–1014`: reviewed setup/called-body fingerprints.
- `TierDocFixture:3829–3937`: count-first execution, selected-byte snapshots, restoration and complete-profile comparisons.
- Eight TierDoc classes at `3940–4363`: public exports, boundary challenges, framework/adopter freshness and nested broken controls.

The TierDoc runtime-baseline helper at `3830–3853` and runtime TIERS/REQUIRED oracle are unsuitable here and will not be reused. Its preservation helper pins only nine profiles; the new comparison pins all ten against delivered HEAD `22c65521b281fce485ec5d10e45359cded53ec3f`.

Shared boundaries remain root/import/text setup, disk_tmp's called scratch.require_disk, eager lifecycle/review_guard/ledger initialization, lazy setup and protected/nested decorate construction. Uncalled producer bodies are not reached claims.

## Proposed approach

Change exactly three existing tracked files:

1. `.ai/scripts/assurance_inputs.py`: append one literal profile and five rationales.
2. `.ai/scripts/tests/test_assurance_inputs.py`: append independent `ASSURANCE_DOC_*` declarations, `AssuranceDocFixture` and eight approved acceptance classes before the existing unittest entry point.
3. `.ai/lifecycle.md`: append adjacent profile documentation while preserving predecessor paragraphs byte-for-byte.

Derive the new fixture directly from `Fixture`; reuse generic utilities unchanged. Compatibility-only document copies support previous public exports but do not define selected reads. Expected values remain independent of `PROFILES`.

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.ai/lifecycle.md
```

No algorithm, schema, dependency, persistence, matching, inference, gate or receipt-mechanism change is proposed.

## Boundaries and invariants

Every repository command uses explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Retain branch `claude/assurance-increment-7` and delivered HEAD `22c65521b281fce485ec5d10e45359cded53ec3f`; no base refresh, switch/reset or new worktree.

One implementer owns all three files sequentially. Independent review is read-only; no parallel edit lanes are proposed because the checks share one test module.

Preserve selected assertions, all ten complete profiles and existing mechanisms. Conservative scope includes unused/future supported non-test descendants. Framework knowledge remains absent; only disposable ordinary-adopter fixtures initialize their own knowledge.

Keep all docs/assurance artifacts ignored/local/uncommitted. Preserve historical evidence. Confirm mutation bytes, restore originals in cleanup/finally and assert restoration. Keep source extraction, actual execution/count proof, freshness edits, intended assertion failures and broken controls distinct.

No native/model/session/trust work, historical rescoring, autonomy driver, commit/push/PR/merge or delivery is included.

## Implementation steps

### Step 1: Exact registration and public export fail before catalog addition

R1, R3. Write new independent declarations, fixture, `AssuranceDocProfileTests` and `AssuranceDocExportTests` first.

Pin the delivered catalog by reading its literal PROFILES at `22c65521b281fce485ec5d10e45359cded53ec3f`; require all ten expected IDs and compare complete dictionaries plus public export argv/inputs/rationales. Preserve existing sibling positives and generic refusal expectations.

Check exact command/root registration, variants, text/JSON/token parity, ordered supplements, missing literals, unsafe paths and nonmutation. Sentinel selected-module/helper contents prove export does not execute them. Existing nonconforming documents remain exportable.

Record absent-registration RED, append only the approved catalog entry/rationales, then record identical GREEN:

```text
python3 .ai/scripts/lifecycle.py redgreen red -- python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocProfileTests AssuranceDocExportTests
python3 .ai/scripts/lifecycle.py redgreen green -- python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocProfileTests AssuranceDocExportTests
```

RED must fail for absent registration, not fixture/import errors.

### Step 2: Independent source and setup guards reject boundary drift

R2. Implement `AssuranceDocDependencyTests`.

Verify five-pattern order, rationales and actual `ledger.input_paths` membership. Include target/helper, sole document, production imports, future supported script and non-Python production descendant. Exclude unrelated tests/documents and compatibility-only files after subtracting actual inputs.

Independently inspect the six method statements. Resolve exact section regex/DOTALL flag, literal first read and match assignment; non-None assertion and body assignment through group(1); both distinct literal tuples, lengths/order, bindings and corresponding assertIn(term, body, term); separate second literal read and MULTILINE whole-document row-prefix regex. Require exactly two text calls, both using the sole approved path. Retain reviewed method/setup fingerprints; expectations must not regenerate themselves from current source during a test.

Freshly derive reachable challenges from current setup, selected method, text, require_disk, lazy, protected/nested decorate and an imported excluded helper. Each claimed reached addition must confirm bytes and excluded membership, fail actual execution with intended data absent, pass exactly one selected test after supplying it, then produce intended boundary rejection. Insert body additions after docstrings and before the first statement's earliest decorator. Historical thirteen-variant results do not prove this profile; uncalled bodies remain conservative pins.

Check: `python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocDependencyTests`. Deliberately broken disposable variants demonstrate sensitivity of later-written guard logic.

### Step 3: Guide documents the static contract and preserves compatibility

R1, R3, R4. Complete `AssuranceDocExportTests` and add `AssuranceDocCompatibilityTests`.

Document exact command/ID, five inputs, two reads of one document, first capture, twenty-plus-seven token checks, separate row-prefix regex and 29 assertions within one test. State conservative extra invalidation, explicit/manual/advisory adoption and all approved semantic/runtime/read-completeness limits.

Add prose inside the existing profile subsection without introducing a newline/`## ` boundary or new literal start marker that changes the selected capture. Inline descriptions must not terminate extraction. New guide prose participates in all-occurrence token-removal fixtures.

Preserve predecessor guide paragraphs byte-for-byte. Check all ten prior exports, existing inference/full-suite refusals, schema/review status, matching and receipt behavior through existing mechanisms.

Checks: approved export and compatibility commands below. Guide prose is test-first exempt; executable guard logic receives deliberate broken-variant evidence.

### Step 4: Actual execution and framework freshness precede 29 intended failures

R3, R5. Implement `AssuranceDocFrameworkEndToEndTests` and `AssuranceDocFailureTests`.

Capture actual selected unittest output independently. Require exactly one unambiguous count equal to one before interpreting exit, then appropriate success/failure markers. Snapshot selected repository bytes and assert stability.

Drive public export and real lifecycle run/reuse; compare recorded argv, ordered inputs and exit. Require REUSE unchanged and after separate unrelated-test/non-input-document edits. Require RERUN after separate assertion-preserving changes to the sole document, target, disk helper, representative production import and new supported script. Restore bytes and require recovery. Document freshness edits must still pass actual selected execution.

Construct exactly 29 separate failures:

1. Eliminate every actual section-regex match; require intended assertIsNotNone failure.
2. For each of 27 tokens, replace every occurrence within the actual selected capture, including new guide prose. Preserve capture boundaries and every earlier assertion.
3. Eliminate every whole-document row-prefix match while preserving extraction and all body tokens; require the final Recording-table assertion.

For VERIFIED, permit collateral removal within later UNVERIFIED but prove VERIFIED is the first failure. UNVERIFIED's separate case preserves other earlier VERIFIED occurrences. Do not count fallback capture, AttributeError, import/setup/CLI failure or zero execution as success.

Each case must confirm bytes, remain exportable, execute exactly one selected test, identify its intended assertion and restore originals. Stop for scope review on count/structure/isolation mismatch.

Check: approved combined framework/failure acceptance command below.

### Step 5: Adopter states and three controls reject false evidence

R1, R4, R6. Implement `AssuranceDocAdopterEndToEndTests` and `AssuranceDocControlTests`.

A separate ordinary adopter explicitly adopts public export. Require initial UNVERIFIED, independent actual one-test proof, real assurance run, stable bytes and VERIFIED. Unrelated edits retain VERIFIED; each approved input/new-script edit yields STALE; restoration recovers VERIFIED. Reordered declarations or changed argv yield UNVERIFIED. Compare evidence argv/inputs/exit and preserve producer receipt exclusion.

Three independent nested controls:

- Omit the sole direct document and its rationale: selected assertions still pass after a preserving edit, but intended freshness acceptance fails.
- Loosen exact command matching: intended variant-refusal criterion fails.
- Substitute an actual empty suite that ignores the selector: independently confirm Ran 0 tests, then reject count before version-dependent exit interpretation. A missing-method loader failure is insufficient.

Confirm control bytes and precisely the intended nested failure, with no unrelated errors or recursion into controls.

Check: approved combined adopter/control acceptance command below.

### Step 6: Convergence, independent review and frozen verification close the slice

R1–R6. Finish edits/self-review, guide synchronization, trace and affected-path evaluation. Run six acceptance groups once through convergence, requiring 6 PASS / 0 FAIL / 0 MANUAL.

Obtain independent two-pass review and preserve its complete canonical report. Repair blockers narrowly and re-review substantive changes. Close/report retrospective before Verify using supported observations or an evidence-backed no-new-lessons result; no binding promotion without approval.

Freeze on the retained base: explicit no-base-refresh instructions override the general refresh recommendation. Run one full framework gate after review under background supervision. Preserve tested source/runtime scope; suppressed child output establishes no full-suite count. Record lifecycle stages only after their checks hold. Stop verified/uncommitted without delivery.

## Testing strategy

Registration is test-first. Later-written guards must reject deliberate broken variants. Source oracle, actual count, freshness, failures and controls supply distinct evidence.

Use focused checks in the loop. Final convergence owns completed slice E2Es; do not duplicate unchanged E2Es. Before repeating any check, run `lifecycle.py reuse LABEL_OR_CMD`; never rerun REUSE. Correct deliberately failed lifecycle labels with a PASS under the same label. One integrated full gate covers prior-profile regression.

Load/reuse validation-policy sections before Gate 4 and minutes-long checks; justify expensive execution by acceptance/input scope and absence of a covering valid PASS.

## Validation commands

All use explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. New classes become runnable only after separate implementation authorization. The six approved acceptance commands are unchanged:

```text
python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocProfileTests
python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocDependencyTests
python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocExportTests
python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocCompatibilityTests
python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocFrameworkEndToEndTests AssuranceDocFailureTests
python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocAdopterEndToEndTests AssuranceDocControlTests
```

Final acceptance and full gate:

```text
python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-5k.md
python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5k.md --plan docs/assurance/plan-5k.md --tests .ai/scripts/tests/test_assurance_inputs.py
python3 .ai/scripts/lifecycle.py run inputs-5k-framework -- python3 .ai/scripts/run_tests.py -j 8
```

Retain new ignored converge-5k.log, framework-5k.log, implementation report and independent review. Use repository background/wait mechanisms for long checks, without repeated unchanged suites. No tier/stage-rule changes require real-agent evaluation. No product test, selected execution or runtime candidate import runs during planning.

## OKF impact

Planning `okf.py affected` on the three proposed files returned exit 1/no framework bundle. Synchronization is inapplicable: never initialize invoking-framework knowledge, baseline/log or claim records PASS. Update the existing guide; keep planning and evidence artifacts ignored.

## Risks and mitigations

- Wrong inherited oracle: inspect actual six statements, both tuples/read calls and flags; omit prior runtime-attribute machinery.
- Capture changes or overlap: derive mutations from current first capture, include guide occurrences and prove intended first failure.
- False reachability/count evidence: require absent-data failure, supplied-data exactly-one PASS and intended boundary rejection.
- Mutation contamination: confirm bytes, isolate cases, restore and assert recovery.
- Regression/evidence inflation: compare all ten complete profiles against delivered HEAD, preserve old records and run one integrated gate.

## Out of scope

Selected-test changes; broader registration; documentation semantics or Markdown/table parsing; actual assurance/status/enforcement behavior; runtime attribute observation; algorithm/schema/dependency/gate changes; generalized dependency discovery; automatic adoption; reduced gates; native/model/session/trust work; historical rescoring; base/worktree/branch changes; commit/push/PR/merge.

## Open decisions

None. Approved D1–D4 settle behavioral scope. The user separately approved this plan and implementation through independent review and verification; no delivery is authorized.

Read-only planner investigation completed. No writes, product tests, runtime candidate import, native/model/session actions or delivery operations occurred in that delegation. Parent persisted this ignored plan only.

## Planning validation

- Approved specification analysis and trace -> exit 0 before Intent recorded with `--approved-by human:enramosjr`.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5k.md --plan docs/assurance/plan-5k.md` -> exit 0; all six requirements traced.
- `git check-ignore docs/assurance/specification-5k.md docs/assurance/plan-5k.md` -> exit 0; both paths ignored.
- `git diff --check` and `git status --short --untracked-files=no` -> exit 0; tracked state clean.
- Lifecycle status after Intent: L2 feature; Intent complete; Plan/Review/Verify still required. No Plan approval or Plan stage inferred.
- Local context confirms retained delivered HEAD/branch and clean tracked state; local refs only, remote_verified false. No new remote check.

No implementation or product check ran. Retrospective and verification remain future approved-work stages, not closed by planning.
