# Implementation Plan: AGENTS encoded-text budget input profile

Approved by human:enramosjr in this chat on 2026-10-29 America/Chicago: “Approved. Implement the 5l plan through independent review and verification, including all five boundary cases. Keep all changes uncommitted; no push, PR, merge, or base refresh.” Based on approved specification-5l.md, R1–R6 and D1–D4. L2; planner role; Python principal engineer. Required read-only planner delegation completed. Implementation through independent review and verification is authorized; all changes remain uncommitted.

## Objective

Add exactly python-agents-budget-contract through the existing literal input exporter for:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py AgentsBudget.test_agents_md_stays_below_its_cold_start_budget
```

Provide independent source-boundary, actual execution/count, identity, freshness and encoded-text boundary evidence while preserving all eleven delivered profiles.

## Success criteria

- R1: Only the approved exact repository-root argv gains registration; eleven complete prior profiles and positive sibling registrations remain preserved.
- R2: Exactly five approved ordered patterns/rationales; independent one-read/encode/len/strict-bound oracle and reviewed setup pins reject drift and newly demonstrated reachable additions.
- R3: Public formats, supplements, validation, refusals, nonmutation and nonexecution remain unchanged.
- R4: Guide states measured text contract, external assumptions and explicit/manual/advisory adoption without changing assurance mechanisms or selected assertions.
- R5: Framework fixtures prove exactly one passing selected test, identities, every approved freshness outcome and all five boundary cases: two passes and three intended assertion failures.
- R6: Adopter fixtures prove VERIFIED/STALE/UNVERIFIED and receipt-exclusion behavior; three broken controls fail their intended criteria.

## Current state

assurance_inputs.py:17–194 contains eleven literal profiles. check_paths:258–282 validates selected paths/required literals; suggest:285–309 selects exact root/argv identity and appends ordered supplements. No exporter algorithm change is needed.

test_lifecycle_conformance.py:167–168 contains one selected assertion:

```python
self.assertLess(len(text("AGENTS.md").encode()), 30_000)
```

text:26–27 uses default Path.read_text decoding/newline handling. Subsequent no-argument encode produces UTF-8. AgentsBudget construction sets BASELINES and compiles NORMATIVE; baseline/flat bodies are uncalled by this selection.

Reusable mechanisms in test_assurance_inputs.py:

- Fixture:34–121: isolated repositories, bounded subprocesses, public export/refusal and lifecycle helpers.
- report_setup_digest:993–1014: import-time statements, conservative class-body retention and reviewed called-body fingerprints.
- AssuranceDocFixture:4373–4460: byte snapshots, count-first selected execution, restoration and predecessor comparisons.
- Eight AssuranceDoc test classes:4463–4895: source guards, exports, framework/adopter states and confirmed nested controls.

The AssuranceDoc section/token/row oracle and29-failure machinery are unsuitable here and will not be reused. No TIERS/REQUIRED/STAGES runtime oracle belongs to the new assertion.

One existing total-catalog guard requires a narrow compatibility adjustment: AssuranceDocFixture.assert_prior_profiles:4455 asserts len(actual)==11. It must become12 when the twelfth profile is added. Preserve its original ten-profile historical baseline and every per-entry/export assertion. Fresh structured search found no other analogous total-profile cardinality guard; unrelated len(variants)==10 at2215 remains unchanged.

The guide is .ai/lifecycle.md, subsection ### Python validation input profiles at210. Existing profile paragraphs remain byte-for-byte intact.

## Proposed approach

Change exactly THREE existing tracked files:

1. .ai/scripts/assurance_inputs.py: append one literal entry and five rationales.
2. .ai/scripts/tests/test_assurance_inputs.py: append NEW independent AGENTS_BUDGET declarations, AgentsBudgetFixture and eight approved acceptance classes before unittest.main; make the sole necessary prior cardinality adjustment.
3. .ai/lifecycle.md: append adjacent profile prose while preserving predecessor paragraphs.

Derive AgentsBudgetFixture directly from Fixture; reuse generic utilities unchanged. Expected scope remains independent of PROFILES:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
AGENTS.md
```

Compatibility-only fixture copies retain all prior profiles' required documents/helpers, including lifecycle documents. They do not become this method's direct-read oracle. No algorithm, schema, dependency, persistence, inference, matching, gate or receipt-mechanism change is proposed.

## Boundaries and invariants

Every repository command uses explicit cwd /home/enramosjr/Projects/agentic-assurance-7. Retain branch claude/assurance-increment-7 and delivered HEAD cf158b53b9c164b22a3172792ab3c86980106e0e; no base refresh, switch/reset or new worktree.

One implementer owns all three files sequentially. Review is independent/read-only; shared fixture edits have no parallel ownership lanes. Preserve selected source/assertion, eleven complete prior entries, positive siblings, generic refusal expectations and assurance mechanisms. The sole cardinality adjustment accommodates the approved addition while retaining an exact count and all preservation checks.

Framework knowledge remains absent. Only disposable ordinary-adopter fixtures initialize their own bundles. Keep ALL docs/assurance artifacts ignored/local/UNCOMMITTED. Preserve historical evidence. Confirm mutation bytes, isolate cases, restore originals in finally/cleanup and assert restoration. Keep source extraction, actual execution/count proof, freshness edits, boundary cases and broken controls separate.

## Implementation steps

### Step 1: Exact registration and public export fail before catalog addition

R1, R3. Write NEW independent declarations, AgentsBudgetFixture, AgentsBudgetProfileTests and AgentsBudgetExportTests first in test_assurance_inputs.py.

Pin the delivered literal catalog using cf158b53b9c164b22a3172792ab3c86980106e0e:.ai/scripts/assurance_inputs.py. Require the expected eleven IDs, compare complete dictionaries and public argv/inputs/rationales, then require exactly twelve current entries after addition. Retain prior positive sibling registrations and refusal expectations.

Check exact command/root registration; refused class/module/sibling/discovery/options/interpreter/path variants; text/JSON/token parity; ordered supplements; required literals; unsafe paths and nonmutation. Sentinel selected-module/helper contents demonstrate exporter nonexecution. Invalid-budget but existing valid-text documents remain exportable.

Record absent-registration RED, append only approved literal entry/rationales, then record identical GREEN:

```text
python3 .ai/scripts/lifecycle.py redgreen red -- python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetProfileTests AgentsBudgetExportTests
python3 .ai/scripts/lifecycle.py redgreen green -- python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetProfileTests AgentsBudgetExportTests
```

RED must fail for absent registration rather than fixture/import errors. Extend only the prior len(actual)==11 guard to12, preserving its historical comparison and positive test. Verification also includes the existing AssuranceDocProfileTests and AssuranceDocCompatibilityTests after catalog addition.

### Step 2: Independent source and setup guards reject boundary drift

R2. Implement NEW AgentsBudgetDependencyTests in test_assurance_inputs.py. Check five-pattern order/rationales and actual ledger.input_paths membership: selected module/helper, sole document, representative imports, future supported non-test script and non-Python descendant. Exclude unrelated tests/documents and compatibility-only documents after subtracting actual selected inputs.

Resolve AgentsBudget/exact method independently through AST. Require one expression statement with self.assertLess, outer len, nested no-argument/no-keyword encode, exactly one text call with sole literal AGENTS.md and literal integer30000. Reject extra selected statements/text calls or changed strict comparison. Retain reviewed method/setup pins rather than regenerating expected values from source under test. Reuse report_setup_digest unchanged and inspect its conservative class-body coverage; pins do not establish baseline/flat or producer-body reachability.

Freshly derive/enumerate challenges for relevant module/class construction, selected method, text, called require_disk, lazy setup, protected/nested decorate and an imported excluded helper. Each newly claimed reachable addition must confirm mutation bytes/excluded membership, fail actual selected execution with excluded data absent, pass exactly one selected test after supplying data, then fail the intended independent boundary guard.

Insert AST body additions after docstrings and BEFORE the first statement's earliest decorator. Malformed syntax, incidental import errors and uncalled bodies do not establish reachability. Historical thirteen variants supply no new-profile proof; uncalled bodies remain conservative pins.

Verification: approved dependency acceptance command. Later-written guard logic must reject deliberate disposable broken variants, satisfying test sensitivity without changing selected source permanently.

### Step 3: Guide states the measured contract and preserves compatibility

R1, R3, R4. Complete export checks and add NEW AgentsBudgetCompatibilityTests. Append guide prose for exact method/ID, five inputs, one literal read/one strict assertion within one test, default decoding/universal-newline translation and subsequent UTF-8 re-encoding. State the approved raw-byte/character/token/latency/semantics/history/enforcement/native/model/session limits, conservative extra invalidation, read-completeness limits and explicit/manual/advisory adoption.

Preserve predecessor guide paragraphs against delivered HEAD; keep prose in the existing subsection without changing earlier capture boundaries. Check eleven prior complete entries/public exports, existing inference/full-suite refusals, review/schema behavior, matching and receipt mechanisms. Retain prior compatibility fixture inputs.

Verification: approved export/compatibility commands plus existing AssuranceDoc profile/compatibility positives. Guide prose is test-first exempt; executable guards receive deliberate broken-variant sensitivity evidence.

### Step 4: Actual execution and framework freshness establish five boundary cases

R3, R5. Implement NEW AgentsBudgetFrameworkEndToEndTests and AgentsBudgetFailureTests. Capture selected unittest output independently; require one unambiguous execution count equal to one BEFORE interpreting exit, then appropriate success/failure markers. Snapshot selected repository bytes and assert stability.

Drive public export and real lifecycle run/reuse. Compare recorded argv, ordered inputs and exit. Require REUSE unchanged and after separate unrelated-test/non-input-document edits; RERUN after separate assertion-preserving edits to AGENTS.md, selected module, disk helper, representative production import and new supported non-test script; restoration recovery for each case. For document freshness edits independently observe sufficient encoded-length margin, confirm exact changed bytes and prove selected execution still passes; do not assume arbitrary growth fits.

Before encoding cases, launch an independent disposable probe with the same literal python3 token, cwd and environment as selected execution. Open a valid UTF-8 marker using the default text decoder, confirm its effective codec (allowing canonical codec aliases) and decoded content. Do not rely solely on getpreferredencoding, import the candidate/helper, change selected argv/source, or alter exporter environment policy. Stop for scope review if UTF-8 is not confirmed. This is a fixture environment assumption, not an exporter guarantee.

Construct the approved FIVE fixtures independently of the selected helper and confirm actual raw bytes:

| Case | Fixture | Expected actual selected result |
| --- | --- | --- |
| Below | 29998 ASCII a bytes plus LF; normalized/re-encoded29999 | one test PASS |
| Equal | 29999 ASCII a bytes plus LF; normalized/re-encoded30000 | intended assertLess FAIL |
| Above | 30000 ASCII a bytes plus LF; normalized/re-encoded30001 | intended assertLess FAIL |
| Multibyte | UTF-8 bytes for15000 U+00E9 characters;15000 chars/re-encoded30000 | intended assertLess FAIL |
| CRLF | ASCII a, CR, LF repeated10000 times; raw30000/normalized-re-encoded20000 | one test PASS |

Require exactly TWO passes and THREE intended failures. Every case confirms actual bytes, independent expected normalized text/encoded length, successful path-only export, exactly one selected execution and exact restoration. Failures must identify the selected threshold assertion/measured comparison values. Decoding/import/setup/CLI/zero-test failures do not qualify. Freshness edits remain separate from these fixtures. Stop for scope review on source/boundary/isolation mismatch rather than change approved breadth.

Verification: approved combined framework/failure acceptance command.

### Step 5: Adopter states and three controls reject false evidence

R1, R4, R6. Implement NEW AgentsBudgetAdopterEndToEndTests and AgentsBudgetControlTests. A separate ordinary adopter explicitly adopts public export. Require initial UNVERIFIED, independent actual-one-test proof, real assurance execution, stable selected bytes and VERIFIED. Unrelated edits retain VERIFIED; separate approved input/new-script edits yield STALE; restoration recovers VERIFIED. Reordered declarations or changed argv yield UNVERIFIED. Compare recorded argv/inputs/exit and demonstrate producer receipt exclusion.

Three independent nested broken controls:

1. Remove sole-document input/rationale: preserving AGENTS.md edit still passes selected execution, but intended freshness acceptance fails.
2. Loosen exact command matching: intended variant-refusal assertion fails.
3. Substitute an actual empty suite ignoring the selector: independently confirm Ran 0 tests, then reject count BEFORE Python-dependent exit interpretation. A missing-method loader _FailedTest is insufficient.

Confirm mutation bytes and precisely the intended nested failure, without incidental errors or recursive control execution. Keep all historical evidence unchanged.

Verification: approved combined adopter/control acceptance command.

### Step 6: Convergence, independent review and frozen verification close the slice

R1–R6. Complete edits/self-review, guide synchronization, trace and affected-path evaluation. Run the six approved acceptance groups once through convergence, requiring6 PASS/0 FAIL/0 MANUAL. Obtain independent two-pass review and preserve the complete canonical report. Repair blockers narrowly and re-review substantive changes. Close/report retrospective BEFORE Verify with supported observations or evidence-backed no-new-lessons; no binding promotion without approval.

Freeze on the retained base: explicit no-base-refresh instructions override the general refresh recommendation. Run ONE full framework gate after review using repository background supervision. Preserve tested source/runtime scope; suppressed successful output supplies no full-suite count. Record later lifecycle stages only when their checks hold. Stop reviewed/verified/uncommitted; delivery is excluded.

## Testing strategy

Registration is test-first. Later-written guards receive deliberate broken disposable variants. Five boundary cases/three controls have fixed approved counts; newly reached dependency variants are freshly enumerated rather than assigned an inherited count.

Focused checks run in the edit loop; completed slice E2Es belong to convergence. Do not duplicate unchanged E2Es. Before repeating a check run lifecycle.py reuse LABEL_OR_CMD; never rerun REUSE. Correct deliberate failed lifecycle labels with PASS under the same label. Load/reuse validation-policy sections before Gate4/minutes-long checks and justify expensive execution by current inputs and absence of a covering valid PASS. One integrated full gate covers prior-profile regression.

## Validation commands

All use explicit cwd /home/enramosjr/Projects/agentic-assurance-7. NEW test classes become runnable only after separate implementation authorization. Approved acceptance commands:

```text
python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetProfileTests
python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetDependencyTests
python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetExportTests
python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetCompatibilityTests
python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetFrameworkEndToEndTests AgentsBudgetFailureTests
python3 .ai/scripts/tests/test_assurance_inputs.py AgentsBudgetAdopterEndToEndTests AgentsBudgetControlTests
```

Focused predecessor check:

```text
python3 .ai/scripts/tests/test_assurance_inputs.py AssuranceDocProfileTests AssuranceDocCompatibilityTests
```

Final acceptance, implemented-test trace and full gate:

```text
python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-5l.md
python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5l.md --plan docs/assurance/plan-5l.md --tests .ai/scripts/tests/test_assurance_inputs.py
python3 .ai/scripts/lifecycle.py run inputs-5l-framework -- python3 .ai/scripts/run_tests.py -j 8
```

Run recorded focused checks with lifecycle.py run labels as appropriate. Retain NEW ignored converge-5l.log, framework-5l.log, implementation report and independent review. Use wait_check.py start/wait under the same host/process visibility for long checks; completion requires actual exit, not a PID missing in another namespace. Do not rerun a suite because supervision visibility is missing. No tier/stage-rule change requires real-agent evaluation. No product test/selected execution/runtime candidate import runs during planning.

## OKF impact

Planning okf.py affected on the three proposed paths returned exit1/no framework bundle. Synchronization is INAPPLICABLE; never initialize invoking-framework knowledge or invent baseline/log/records PASS. Synchronize the existing profile guide; keep planning/evidence artifacts ignored/local/uncommitted.

## Risks and mitigations

- Wrong measurement oracle: resolve exact AST chain independently and explicitly test multibyte/CRLF differences.
- External decoding mismatch: confirm effective UTF-8 default decoding under actual fixture child environment; stop on mismatch.
- False reachability/count: require absent-data failure, supplied-data exactly-one PASS and intended guard rejection.
- Freshness edit crosses threshold: observe margin and prove changed document passes.
- Prior-profile regression: preserve complete eleven-entry baseline and predecessor prose; narrowly extend sole cardinality guard to12.
- Mutation contamination/evidence inflation: isolate cases, verify bytes/restoration and preserve historical results.

## Out of scope

Selected-test changes; broader registration; raw-file-size/character/token/latency/semantics/history claims; lifecycle runtime-attribute qualification; algorithm/schema/dependency/gate changes; general dependency discovery; automatic adoption; reduced gates; native/model/session/trust work; historical rescoring; base/worktree/branch changes; autonomy driver; commit/push/PR/merge.

## Open decisions

None. Approved D1–D4, including the five boundary cases, settle behavioral scope. The user separately approved this implementation plan through independent review and verification.

## Planning evidence

Read-only planner delegation completed. Spec analyze/trace passed and Intent was recorded with human:enramosjr. Relevant validation-policy sections were loaded. At planning completion no source edits, product tests, runtime candidate import, native/model/session work, delivery or knowledge initialization occurred. The subsequent explicit approval above authorizes Plan recording and implementation.

- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5l.md --plan docs/assurance/plan-5l.md` -> exit0; six requirements traced. Implemented-test tracing is deferred because new classes do not yet exist.
- `git check-ignore docs/assurance/specification-5l.md docs/assurance/plan-5l.md` -> exit0; both ignored/local/uncommitted.
- `git diff --check` and `git status --short --untracked-files=no` -> exit0; tracked state clean.
