# Implementation Plan: stage documentation and runtime stage-name input profile

Draft for separate human approval. Based on approved `docs/assurance/specification-5i.md`, R1-R6 and D1-D4. L2; planner role; Python principal engineer. Required read-only planner delegation completed. Intent is recorded; Plan approval and implementation are pending.

## Objective

Add `python-stage-doc-contract` for exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Tiers.test_every_stage_the_script_gates_is_described_in_the_lifecycle
```

Use the existing literal exporter and explicit adoption to establish bounded repository-file freshness for the selected method's five heading-substring checks and runtime stage-name set assertion, preserving all eight delivered profiles.

## Success criteria

- R1: Only the approved exact argv gains the new ID; eight prior complete profile dictionaries and behavior remain intact.
- R2: Five approved ordered patterns have accurate rationales and an independent source-derived method/setup guard.
- R3: Export preserves formats, token parity, supplements, validation, refusal, immutability and nonexecution.
- R4: The guide accurately limits claims and retains explicit, manual, advisory adoption.
- R5: Framework fixtures independently prove exactly one passing test, stable selected bytes, required REUSE/RERUN outcomes and six intended assertion failures.
- R6: Ordinary-adopter fixtures prove VERIFIED/STALE/UNVERIFIED states, identity and receipt exclusion; three broken controls fail their intended criteria.

## Current state

`assurance_inputs.py:17-148` contains eight literal profiles. Export matches exact argv and validates declared paths without executing the selected test.

`test_lifecycle_conformance.py:197-201` has three statements: a literal `.ai/lifecycle.md` read, a heading-label tuple loop with interpolated substring assertions, and `set(lifecycle.STAGES)` equality. It does not check Stage 2, stage enforcement, section bodies, ordering, duplicates or tuple type.

Root/import setup and `text` are at lines 15-27. `disk_tmp.py:10-20` imports scratch and calls `require_disk`; `scratch.py:11-26` may read mount state. Lifecycle imports scratch/review_guard, constructs lazy modules at lines 48-66, defines STAGES at line 71 and applies protected decorators at lines 1011,1209,1321. `review_guard.py:23-26,629-639` covers eager ledger/scratch imports and protected/nested decorate construction. The selected test invokes no wrapped producer.

Reusable mechanisms in `test_assurance_inputs.py`:

- `Fixture:34-121`: disposable repositories, bounded subprocesses, public export and lifecycle helpers.
- `report_setup_digest:993-1014`: conservative import/class/signature/decorator and called-body fingerprints.
- `AnalysisConvergenceDocFixture:2821-2903`: selected-byte snapshots, independent count-first execution, restoration and predecessor comparison.
- Dependency guards/mutations:2996-3121; framework/failure/adopter/control mechanisms:3145-3301.
- Existing guide subsection: `.ai/lifecycle.md:210-246`.

The predecessor fixture compares seven profiles against an older commit; it cannot supply the required eight-profile baseline unchanged. Structured search found no proposed exact candidate refusal requiring replacement. Existing positive sibling registrations remain preserved.

## Proposed approach

Change exactly three existing tracked files:

1. `.ai/scripts/assurance_inputs.py`: append one literal profile with five rationales.
2. `.ai/scripts/tests/test_assurance_inputs.py`: independent StageDoc declarations, fixture and eight acceptance classes.
3. `.ai/lifecycle.md`: extend the existing profile subsection.

Derive `StageDocFixture` directly from `Fixture`. Reuse base helpers and `report_setup_digest` unchanged. Copy the selected module/helper, sole direct document and compatibility-only inputs needed to export all eight predecessors. Compatibility copies do not define selected reads.

Approved ordered declaration:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.ai/lifecycle.md
```

No exporter algorithm, selected assertion, schema, dependency, persistence or gate change is required.

## Boundaries and invariants

Every repository command uses explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Retain branch `claude/assurance-increment-7` and delivered HEAD `0efa2240b6109f6e69fe7a5dacaa3f9be16482c2`. No base refresh, switch/reset or new worktree.

One implementer owns all three tracked files and fixture changes, working sequentially because the tests share one module. Independent review is read-only. Preserve eight complete profiles, matching, inference, full suites, schemas, gates, freshness and receipt exclusions.

Restore disposable mutations with cleanup/finally. Freshness edits preserve selected assertions; deliberate assertion failures are separate. All `docs/assurance` artifacts remain ignored/local/uncommitted. Preserve historical evidence. Only disposable ordinary adopters initialize knowledge.

No native/model/session/trust action, historical rescoring, autonomy driver or delivery is included. Stop verified/uncommitted.

## Implementation steps

### Step 1: Exact registration and export reject incomplete implementation

R1, R3; test module first, then exporter catalog.

Write independent command, input, document and setup declarations. Add `StageDocFixture`, `StageDocProfileTests` and `StageDocExportTests` before the catalog entry.

Parse literal PROFILES from delivered HEAD `0efa2240b6109f6e69fe7a5dacaa3f9be16482c2`; require all eight expected predecessor IDs and compare complete dictionaries plus public export argv/inputs/rationales.

Check exact registration, root and variant refusal, public formats/token parity, supplement order, every required-literal/path/inventory refusal and export immutability. Poison selected module/helper to establish nonexecution while keeping exporter dependencies usable. Existing assertion-failing document contents remain exportable.

Record absent-profile RED, then append only the approved entry/rationales and record identical GREEN:

```text
python3 .ai/scripts/tests/test_assurance_inputs.py StageDocProfileTests StageDocExportTests
```

The RED must be missing registration, not fixture/import failure. Preserve existing refusals and positive sibling expectations unchanged.

### Step 2: Independent source and setup guards reject boundary drift

R2; `StageDocDependencyTests`.

Check declaration order, rationales and actual `ledger.input_paths` selection. Include selected/helper/direct/setup files, a supported future script and non-Python production descendant. Exclude unrelated tests/documents and compatibility-only inputs after subtracting `.ai/lifecycle.md`.

Review six setup fingerprint surfaces: selected module, disk_tmp, scratch, lifecycle, review_guard and ledger. Keep fixed reviewed expectations rather than computing expected hashes from current bytes at runtime. Pin the selected method independently.

Build an AST oracle for the actual three-statement method:

- Resolve the literal document read and assigned document variable.
- Resolve all five literal heading labels; verify loop binding and `## ` + bound heading + newline interpolation passed to `assertIn` with that document.
- Verify `assertEqual(set(lifecycle.STAGES), literal_expected_set)` and the five expected names.
- Reject additional/unaccounted reads or changed method structure.

The loop binds labels, not paths. Source structure and fingerprints establish no observed runtime STAGES value.

Source inspection supports proposed mutations at six eager module initializations; selected method, `text`, `require_disk`, `lazy`, `protected`, nested `decorate`; and a selected-module import of an excluded helper. These thirteen proposed sites require fresh proof, not inherited reachability.

For every claimed reached site: confirm changed bytes and excluded data membership; actual selected execution must fail with intended missing-data `FileNotFoundError`; supply data and independently prove exactly one passing test; then require nested boundary acceptance to fail specifically on its review guard. Insert body changes after docstrings and before the first statement's earliest decorator. Uncalled wrapped bodies remain conservative pins.

Check:

```text
python3 .ai/scripts/tests/test_assurance_inputs.py StageDocDependencyTests
```

These deliberately broken variants establish sensitivity of later-written guard logic.

### Step 3: Guide states the bounded contract and preserves compatibility

R1, R4; `StageDocCompatibilityTests`, then guide prose.

Check eight predecessors, inference/full-suite refusal, schema/review flags and existing matching/gate/receipt mechanisms.

Document exact command/ID, five ordered patterns, sole direct document, five heading checks plus runtime set equality within one test, conservative extra invalidation and explicit/manual/advisory adoption. State limits: no Stage 2 check, semantic section/body correctness, order/duplicate/type guarantee or actual gate enforcement. Export remains path-only and nonexecuting.

Check:

```text
python3 .ai/scripts/tests/test_assurance_inputs.py StageDocCompatibilityTests
```

Guide prose is test-first exempt. Any intentional lifecycle-run diagnostic failure receives corrected PASS under the same label after reuse permits rerun.

### Step 4: Framework freshness and six assertion failures are observable

R3, R5; framework E2E and failure classes.

Independently capture selected execution. Require one unambiguous unittest count equal to one before exit interpretation; success also requires exit zero and `OK`. Snapshot selected bytes and assert stability.

Drive public export and real lifecycle run/reuse. Compare recorded argv, ordered inputs and exit to export. Require REUSE unchanged and after separate unrelated-test/non-input-document edits. Require RERUN after separate assertion-preserving edits to direct document, selected module, disk helper, representative production import and a new supported script. Restore bytes and require REUSE. Direct-document freshness edits must still pass selected execution. Framework knowledge remains absent.

Add six separate assertion failures: remove every occurrence of each of the five exact heading substrings, one case at a time; separately mutate only the disposable lifecycle STAGES assignment to introduce set-member drift.

Confirm changed bytes, successful export, exactly one executed test and intended selected assertion failure. The STAGES case must reach the set equality assertion, without import or CLI errors. Restore bytes; keep failure cases separate from freshness edits.

Check:

```text
python3 .ai/scripts/tests/test_assurance_inputs.py StageDocFrameworkEndToEndTests StageDocFailureTests
```

### Step 5: Adopter states and three controls reject false evidence

R1, R4, R6; adopter E2E and control classes.

A separate ordinary adopter explicitly adopts public export in its own capability. Require initial UNVERIFIED, independent one-test proof, actual `assure --run`, stable selected bytes and VERIFIED.

Unrelated edits retain VERIFIED; each input/new-script edit becomes STALE and restoration returns VERIFIED. Reordered inputs and changed argv become UNVERIFIED. Compare recorded identities/exit including producer receipt exclusion; receipt-only additions retain VERIFIED.

Three disposable broken controls omit the sole direct document, loosen exact command matching, or substitute an actual empty suite ignoring the selector. Confirm mutation bytes and intended nested acceptance failure without unrelated errors. Omission must fail freshness while assertion-preserving document edits still pass execution. The empty suite must independently report `Ran 0 tests`; count rejection precedes Python-dependent exit interpretation. A loader `_FailedTest` is insufficient. Never recurse into control classes.

Check:

```text
python3 .ai/scripts/tests/test_assurance_inputs.py StageDocAdopterEndToEndTests StageDocControlTests
```

### Step 6: Converge, independently review and verify the frozen candidate

R1-R6; three tracked files plus new ignored reports/evidence.

Complete edits, trace all requirements, evaluate affected paths and check diff/whitespace. Run approved acceptance through converge once on the completed candidate, requiring 6 PASS / 0 FAIL / 0 MANUAL. No historical result covers this ninth profile.

Obtain independent two-pass review; preserve the complete canonical returned report unchanged. Repair blockers and re-review substantive changes. Close and report retrospective before Verify.

Freeze on the existing authorized base. Run the full framework gate once under background supervision, retaining source/runtime scope. Suppressed successful output establishes no full-suite count. Record Review/Verify only when their exits hold. Stop verified/uncommitted.

## Testing strategy

Use public interfaces, real inventory, bounded subprocesses, byte snapshots/restoration and count-before-exit. Initial RED/GREEN proves registration sensitivity. Confirmed broken variants challenge later-written boundary, freshness, matching and count logic.

Converge supplies connected framework/adopter E2Es and deliberate assertion failures on the completed candidate; do not duplicate unchanged completed E2Es. Before any repeated check run `lifecycle.py reuse`; do not repeat REUSE results. Correct deliberate failed run labels under the same labels.

Python considerations affecting this plan: import-time effects, called-helper/decorator construction, resource bounds, Python 3.9 compatibility and independent runtime count evidence.

## Validation commands

Future product checks; none run before plan approval. Nonexecuting trace is permitted during planning:

```text
python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5i.md --plan docs/assurance/plan-5i.md --tests .ai/scripts/tests/test_assurance_inputs.py
python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-5i.md
python3 .ai/scripts/lifecycle.py run inputs-5i-diff -- git diff --check
python3 .ai/scripts/lifecycle.py run inputs-5i-scan -- python3 .ai/scripts/lifecycle.py scan-diff
python3 .ai/scripts/lifecycle.py run inputs-5i-framework -- python3 .ai/scripts/run_tests.py -j 8
python3 .ai/scripts/lifecycle.py audit
```

Six acceptance selectors are fixed by the approved spec. Record focused checks with run/redgreen. Load applicable validation-policy sections before Gate 4 or long checks; inspect background supervision usage before launch. No real-agent evaluation is required because tier/stage rules remain unchanged.

## OKF impact

Planning `okf.py affected` for the three tracked files exited 1 because this framework has no knowledge bundle. Synchronization is INAPPLICABLE, not records PASS. Never initialize invoking-framework knowledge or invent capability/log evidence. Synchronize the existing guide and retain new ignored reports without changing history.

## Risks and mitigations

- Wrong oracle: inspect literal read, label binding/interpolation and runtime attribute/set comparison independently.
- Source-only runtime claim: require actual selected execution/count and intended STAGES assertion drift.
- Missing predecessor: compare/export eight complete dictionaries from delivered HEAD.
- Compatibility copies mistaken for reads: keep them outside the sole-document oracle.
- Unreached mutations or false zero: missing-data/supplied-data proof and independent count-first checks.
- Inflated history: record new evidence with exact source/runtime scope.

## Out of scope

Selected-test edits, broader registration, exporter/lifecycle/ledger algorithm changes, universal dependency discovery, automatic adoption, reduced gates, native/model/session/trust actions, historical evidence changes, base refresh/new worktree, invoking-framework knowledge and commit/push/PR/merge.

## Open decisions

None. Approved D1-D4 settle behavior and scope. Ready for separate human plan approval; implementation remains pending.

## Planning evidence

Read-only planner inspected the method, shared setup, current fixture/guard/E2E/control mechanisms and guide. No product tests or source edits occurred. `okf.py affected` confirmed no framework bundle. Parent recorded approved Intent; approved-spec analysis and six-requirement trace passed. Plan remains unrecorded pending human approval.

After persistence: `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5i.md --plan docs/assurance/plan-5i.md` -> exit 0, six requirements traced. `git check-ignore docs/assurance/specification-5i.md docs/assurance/plan-5i.md` -> exit 0, both ignored. Local `repo.py context --json` confirms expected branch/HEAD and clean tracked state; local refs only, no new remote check. These are structural/local-state checks, not product acceptance evidence.
