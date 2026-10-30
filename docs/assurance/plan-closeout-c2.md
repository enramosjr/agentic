# Implementation Plan: precision-aware mechanical evidence ordering

Approved by human:enramosjr in this chat, 2026-10-29 America/Chicago: "I approve the C2 implementation plan. Proceed through implementation, independent review and verification. Keep changes uncommitted, preserve the C1 proof gap, and keep 5o unapproved with all profile work paused." Specification: docs/assurance/specification-closeout-c2.md, approved by human:enramosjr; Intent recorded. This approval authorizes this plan through Verify, with changes UNCOMMITTED and no delivery action.

All repository commands use cwd `/home/enramosjr/Projects/agentic-assurance-7`, existing branch `claude/assurance-increment-7`, HEAD `02dd97586873f24a604224aa5ad186a60c4104e7`. No base refresh, new worktree or branch switch.

5o remains unapproved. All profile work remains paused. The remaining C1 per-class broken-variant proof gap remains open; C2 controls must not be relabeled as its closure.

## Objective

Implement the approved C2 contract: order matching mechanical requirement evidence by the precision represented in its recorded UTC completion time, fail closed when that order is unresolved, and produce subsecond completion times without changing other timestamp, fingerprint, report or gate contracts.

## Success criteria

| Requirement | Observable result |
| --- | --- |
| R1 | The provably latest matching execution determines outcome/freshness independently of filename, ledger index, enumeration or publication order. |
| R2 | All three accepted req producer paths record six fractional UTC digits at command completion; each producer retains its existing fingerprint fields and capture timing. |
| R3 | Legacy and fractional timestamps use precision intervals; unresolved distinct executions yield UNVERIFIED, including same-record and all-PASS ties. |
| R4 | Malformed matching ordering data yields a named reconciliation diagnostic, never an older PASS fallback; unrelated identities do not contaminate selection. |
| R5 | Real CLI executions establish both outcome directions, storage states and sleep-free measurement handoff with deterministic clocks. |
| R6 | Existing matching, freshness, schema, exit mapping, receipt exclusions, attestation, general reuse and gate policy remain intact. |
| R7 | The guide states the bounded contract, and exactly seven confirmed control variants across five mechanisms are rejected for their intended reasons. |

## Current state

- assurance.py207–247 loads eligible req entries and suppresses the active task's published copy. Evidence.order returns raw timestamp text, filename and index; evaluate367–393 selects its maximum after exact matching.
- lifecycle.py1011–1047 records an execution timestamp after completion and before publication, using whole-second now(). This function serves explicit assure --run and generic run.
- lifecycle.py1245–1287 captures requirement fingerprints before acceptance execution, assigns completion time per requirement, and publishes the batch later.
- ledger.audit204–220 checks supported keys rather than timestamp grammar. General reuse does not use Evidence.order.
- review_guard.append_evidence554–585 hashes and publishes exact ledger entries under existing ownership/state-lock rules. Its local transition sequence is not a universal completion order.
- assurance_measure.py148–152 spaces handoff tasks by1.05 seconds. Approved metric constants remain in test_assurance_measure.py; no historical result is updated by this plan.
- test_assurance_attested.py23 normalizes whole-second mechanical report timestamps. Its normalization must narrowly accept fractional mechanical timestamps while preserving golden expectations.
- learning.timestamp validates lesson/rule timestamps as whole seconds. Global now(), stage times, lessons and task IDs must remain unchanged.
- Existing test_assurance.Case copies scripts into temporary adopters and drives the public CLI. GateCase/DeltaCase in test_assurance_gate.py provide real lifecycle preparation, gate assertions and exact-match delta acceptance.
- test_assurance_inputs.py993–1014 pins import-time statements, top-level signatures/decorators and selected setup bodies in lifecycle, scratch, ledger, review_guard and conformance. A new lifecycle import/helper/signature or changed conformance class would require paused profile-oracle work. Existing function-body-only producer changes avoid that expansion.
- Repository commands/source document unittest, the stdlib-only script runner and Python3.9+. No pyproject/setup/tox or active CI workflow was found by the task-specific inventory; do not add another toolchain.

## Proposed approach

### Precision parsing and selection

Add private helpers inside assurance.py; add no production module or dependency.

1. Match only the approved ASCII UTC grammar with zero or1–6 fractional digits.
2. Validate calendar/time components with the existing datetime module.
3. Convert the date ordinal and time components to an integer microsecond lower bound.
4. Set interval width to1,000,000 microseconds for whole-second values, or10**(6-fractional_digits) for fractional values.
5. Represent the interval as integer [lower, upper). Integer arithmetic avoids floats and permits the upper endpoint after the last representable calendar microsecond without constructing an overflowing datetime.
6. Preserve exact candidate filtering before parsing time. Any malformed otherwise-matching candidate produces the approved UNVERIFIED metadata-reconciliation result, regardless of its outcome.
7. Find the candidate with the greatest lower endpoint, then require that endpoint to be at or after every other distinct candidate's upper endpoint. If not, return the ambiguity result.

This is linear in candidate count. No outcome, filename or index participates in precedence. Sort diagnostic record/index identities for stable display only. Uncertainty yields UNVERIFIED, basis none and evidence null; preserve the governance attachment performed by existing result(), rather than bypassing existing output construction.

Replace evaluate's current maximum selection and remove the now-unused Evidence.order property after confirming its only production caller is replaced. Preserve loader eligibility, active-copy suppression and freshness evaluation. Distinct entries remain distinct even when their bytes match. No ledger-audit/schema change is required for reader-side timestamp validation.

### Producer changes without setup-pin drift

Do not add lifecycle imports, helper definitions, signatures or decorators. Inside execute_check's existing body, record `datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")` only for labels beginning req:, retaining now() for other labels. Use the same expression inside the existing convergence snapshot.update at completion. Existing imports already supply datetime/timezone. Leave initial pre-run snapshot timing and later publication where they are.

This small expression duplication avoids changing lifecycle setup/signature pins or requiring paused profile work. Direct run retains its existing optional fingerprint absence; no runtime=True or new profile inference is added.

### Fixture clocks and actual outcomes

Inject a test-only datetime subclass into disposable copied lifecycle.py at its existing datetime import. It reads controlled fixture clock data and supplies a datetime to the existing formatting calls. Confirm the injection bytes before execution and restore/read-confirm them. No production environment flag, clock override, new hook or source helper is added.

The seam must also work before the repair: existing now().strftime still truncates fractional clock data, giving a meaningful behavioral RED. For measurement, advance controlled fractional clock values deterministically across producer calls within a bounded second, including separate tasks; do not use real sleeps to establish precedence.

For outcome pairs, use a disclosed test-only environment outcome value read by the same unchanged check command. Assert actual process exits and unchanged recorded argv, selected file bytes and applicable runtime fingerprint. This is controlled nondeterminism, not a complete dependency-declaration claim. Child environment differences must not introduce an unrelated freshness explanation.

Use real persisted fixture records, not fabricated statuses. Rename published fixture record files to reverse lexical order without rewriting their evidence. Exercise an archived older record plus active later task, both records published with the fixture active-state file temporarily absent, and active/published duplicate suppression. Construct delayed publication separately from recorded completion; do not use append index as completion proof. Restore all moved state/record files and confirm bytes before disposal. No actual historical artifact is touched.

Framework fixtures exercise run req producers/reuse without knowledge. Assurance and gate statuses run through real CLI in ordinary adopter fixtures; do not pretend framework assure evaluates nonexistent framework capability requirements.

## Boundaries and ownership

One implementer owns the connected source and fixture work; do not split overlapping files into concurrent editing lanes. An independent reviewer and one final-gate validator receive read-only/frozen-candidate responsibilities later.

| File | Allowed change |
| --- | --- |
| .ai/scripts/assurance.py | Private interval/selection helpers, mechanical uncertainty results, removal of unused mechanical ordering property. |
| .ai/scripts/lifecycle.py | Two existing function-body timestamp expressions only; no setup, signature, decorator or global-clock change. |
| .ai/scripts/assurance_measure.py | Remove only handoff ordering sleep/comment and its now-unused time import. |
| .ai/scripts/tests/test_assurance_ordering.py | NEW: seven approved acceptance classes, shared fixtures and seven controls. Direct unittest entry point required. |
| .ai/scripts/tests/test_assurance_attested.py | Narrow timestamp normalization repair and regression, preserving golden expectations and attestation-stage semantics. |
| .ai/lifecycle.md | Bounded mechanical ordering, diagnostics, legacy/clock limitations and remediation. |

Do not change assurance_inputs.py, test_assurance_inputs.py, conformance classes, catalog cardinality guards, profile pins, ledger schema or review protection. Preserve all fourteen complete profiles. If implementation proves another file requires an edit, establish its concrete cause and return the scope question before expanding; do not weaken an unrelated test or hide the change in a pin refresh.

## Implementation steps

### Step 1: Establish the real cross-task ordering regression

Requirements: R1, R2, R5. File: new test_assurance_ordering.py.

Write the module with a direct unittest entry point and fixtures importing only existing modules. First add `MechanicalOrderingEndToEndTests.test_later_failure_wins_across_tasks`: real CLI executions in different tasks, one controlled UTC second with distinguishable fractional completion values, reversed lexical record names, identical recorded identities, and an assertion that the later failing execution produces FAILED.

Record RED before production changes. Require exactly the named test to execute and the failure to be the wrong selected mechanical outcome, not a missing helper/import, syntax error, unusable fixture or zero discovery. Then add old-FAIL/new-PASS and both storage-state arrangements. Do not let the fake clock bypass the old formatter, which would conceal the bug.

Failing-closed check: the named regression and MechanicalOrderingEndToEndTests, with raw process/count/result evidence retained. This is the initial lifecycle redgreen pair's exact command; later GREEN uses that same selector.

### Step 2: Make mechanical selection precision-aware and fail closed

Requirements: R1, R3, R4. Files: assurance.py and new Selection/Legacy/InvalidMetadata acceptance classes.

Write behavioral tests first for strict grammar and calendar values; leap dates/invalid time components; whole-second and1–6-digit intervals; adjacency, overlap and zero-padding; year-end upper-bound arithmetic; a single legacy candidate and disjoint legacy candidates; same-record/cross-record/all-PASS ties and distinct byte-equal executions; malformed matching metadata versus irrelevant bad metadata; no filename/index fallback; latest FAILED/timeout/VERIFIED/STALE; named uncertainty diagnostics, basis none and evidence null. Expected intervals/results must be handwritten independently of the production parser.

Implement integer parsing and the linear unique-latest selector. Retain existing eligibility/matching before parsing, loader duplicate behavior, result construction and freshness checks. Bad relevant metadata must remain reconcilable evidence uncertainty, not a reason to silently discard it and use an older PASS.

Checks: MechanicalOrderingSelectionTests, MechanicalOrderingLegacyTests and MechanicalOrderingInvalidMetadataTests. New pure-logic tests precede implementation or are shown to fail on a confirmed broken variant.

### Step 3: Record precise requirement completion times without changing fingerprints

Requirements: R2, R6. Files: existing lifecycle function bodies, new ProducerTests, attestation normalization fixture.

Write producer-format/timing regressions first for assure --run, direct run req:<ID>, and exact-match delta convergence. Read their actual persisted entries and assert six fractional UTC digits captured after completion. Two delta obligations must have their separate completion values rather than one common publication time. A copied check can advance the fixture clock as it finishes, distinguishing start from completion; a separate delayed-publication case distinguishes completion from publication.

Assert existing input/runtime fingerprints are pre-run only where that producer records them; confirm unchanged field presence/absence. Implement only the two body expressions described above. Keep now(), ordinary timestamps and fingerprint capture unchanged.

Extend `test_assurance_attested.normalise`'s mechanical at= pattern by optional1–6 fractional digits. Add a focused fixture regression for old/new timestamps with unchanged nonvolatile text and unchanged golden content. Do not alter the production attestation selector or its whole-second stage timestamps.

Checks: MechanicalOrderingProducerTests, the new fixture normalization regression and existing attestation compatibility cases. The full attestation module runs once as focused integration when these edits are complete, not after unrelated parser-only repairs.

### Step 4: Prove the connected CLI, gate and sleep-free handoff paths

Requirements: R1, R5, R6. Files: new E2E/Compatibility fixtures and assurance_measure.py.

Finish both real outcome directions/storage arrangements; actual process counts/exits; delayed publication; the controlled rollback case illustrating the approved recorded-time limitation; and framework-mode writer/reuse without knowledge. Assure status outcomes belong to ordinary adopter fixtures.

Prepare actual L2 and L3 adopter task prerequisites using existing GateCase/DeltaCase helpers. Seed unresolved matching evidence and assert Verify refuses without a recorded Verify or implicit obligation run. Run a provably later matching success; reestablish only genuinely stale ordinary prerequisites, then assert normal Verify succeeds. Failure must reach the assurance gate rather than an unrelated prerequisite.

First write a handoff regression that rejects ordering sleep and drives the actual measurement CLI/handoff under deterministic copied clocks. Remove the1.05-second avoidance and unused import, retaining all original metric expectations and historical files. Assert expected handoff detection and post-rerun status, plus the approved counts when the measurement integration suite runs.

Checks: MechanicalOrderingEndToEndTests and MechanicalOrderingCompatibilityTests; existing measurement scenario/report integration. Existing measurement module runs once when its repair is complete. No repeated historical campaign or native evaluation.

### Step 5: State the bounded contract and reject exactly seven broken variants

Requirements: R7 and the R1–R6 mechanisms. Files: lifecycle guide and new ControlsTests.

Document recorded completion/precision intervals, legacy/same-record/all-PASS ambiguity, UNVERIFIED/basis-none/no-selected-evidence, explicit later-run remediation for well-formed overlap, malformed metadata reconciliation, unchanged schema/contracts, clock-reversal/unsynchronized-host limits and no historical migration. Preserve existing guide terms so conformance methods remain unchanged. Test the new guide statements from the new test module.

Each control is a confirmed source mutation in a disposable copy, never a historical evidence edit. Use these proposed guard methods in the named new classes; implementation may choose equivalent method names without changing criterion or counts.

| # | Broken variant | Specific assertion/guard |
| --- | --- | --- |
| 1 | Cross-record filename tiebreak on unresolved intervals | LegacyTests.test_cross_record_overlap_has_no_filename_tiebreak: UNVERIFIED regardless of reversed names. |
| 2 | Same-record index tiebreak | LegacyTests.test_same_record_overlap_has_no_index_tiebreak: tied distinct events are UNVERIFIED. |
| 3 | Whole-second req timestamp truncation | ProducerTests.test_requirement_completion_precision: six digits; paired real CLI outcome guards must still work. |
| 4 | Convergence batch-publication timestamp substitution | ProducerTests.test_converge_records_each_completion: persisted times match distinct command completions. |
| 5 | Legacy timestamp treated as an exact point | LegacyTests.test_legacy_fractional_overlap_is_unverified: no invented within-second precedence. |
| 6 | Older-PASS fallback on overlap | LegacyTests.test_overlap_does_not_fall_back_to_a_pass: ambiguity result, no selected evidence. |
| 7 | Older-PASS fallback after malformed matching time | InvalidMetadataTests.test_bad_matching_time_cannot_restore_an_older_pass: metadata reconciliation, no VERIFIED. |

The shortened class prefixes in this table denote the full approved MechanicalOrderingLegacyTests/ProducerTests/InvalidMetadataTests names. ControlsTests runs only specific nonrecursive guards, never itself. For each variant: establish the unmutated guard PASS, confirm changed bytes, require the intended nonempty assertion failure, reject syntax/import/loader failures as kills, then restore/read-confirm exact bytes. Seven variant outcomes across five mechanisms are reported; no inflated count from repeated subTest failures.

Check: MechanicalOrderingControlsTests, exactly seven confirmed rejections plus guide assertions. These controls do not discharge C1's unrelated original per-class proof gap.

### Step 6: Freeze and close the C2 slice through review and verification

Requirements: R1–R7. Finish focused repairs first, then:

1. Trace approved spec through this plan and new tests; confirm protected profile/conformance files have no diff from delivered HEAD.
2. Evaluate framework-aware OKF impact, synchronize the existing guide and record no invoking knowledge bundle.
3. Execute seven approved acceptance groups through convergence once on the complete candidate. Do not rerun equivalent standalone acceptance after convergence supplies a current PASS.
4. Obtain independent two-pass implementation review; save the complete canonical report unchanged. This later product review is distinct from read-only plan review.
5. Resolve findings and rerun only invalidated evidence under reuse policy. If convergence inputs change, obtain current acceptance before final review/Verify; no silent stale PASS reuse.
6. Freeze the reviewed candidate on the user-prescribed current base (no fetch/merge/base refresh), then run the required full framework gate once. The explicit no-base-refresh boundary takes precedence over the policy's usual prefreeze update preference.
7. Record actual candidate/runtime/commands/outcomes, final scan/diff/audit and retrospective before Verify. Do not infer counts from suppressed lifecycle output.

No tier/stage policy changes are proposed, so no real-agent lifecycle evaluation is required solely for this repair. Do not upgrade historical native evidence. C2 completion does not close C1 or the entire initiative. No commit/push/PR/merge without separate delivery authorization.

## Testing strategy

Use behavioral unit tests for interval selection and actual CLI fixtures for producers, outcomes, record storage and gate behavior. The first RED must reproduce wrong cross-task selection on pre-change production source. All other new logic tests precede their implementation or demonstrably fail under a confirmed broken variant.

No broad existing expectation may be weakened to accommodate ambiguity. If an existing synthetic fixture intentionally contains tied legacy times, first identify the exact stated criterion. Adjust data only when the criterion requires distinguishable completions; assert UNVERIFIED when ambiguity is the subject. Any necessary source/test edit outside the file list returns for explicit scope resolution before implementation.

Fixture timeout waits may trigger actual timeout behavior, but are not used as evidence of chronological order. Record raw test counts and exact statuses; process startup or file existence is not E2E success. Mutation guards require actual target assertions to fail.

## Validation commands

All product commands below are FUTURE, after separate plan approval. New file/class/method selectors are proposed and do not exist yet. No command below was run to draft this plan.

Initial actual regression:

```text
python3 .ai/scripts/lifecycle.py redgreen red -- python3 .ai/scripts/tests/test_assurance_ordering.py MechanicalOrderingEndToEndTests.test_later_failure_wins_across_tasks
python3 .ai/scripts/lifecycle.py redgreen green -- python3 .ai/scripts/tests/test_assurance_ordering.py MechanicalOrderingEndToEndTests.test_later_failure_wins_across_tasks
```

Focused groups, recorded through lifecycle.py run where applicable:

```text
python3 .ai/scripts/tests/test_assurance_ordering.py MechanicalOrderingSelectionTests MechanicalOrderingLegacyTests MechanicalOrderingInvalidMetadataTests
python3 .ai/scripts/tests/test_assurance_ordering.py MechanicalOrderingProducerTests
python3 .ai/scripts/tests/test_assurance_ordering.py MechanicalOrderingEndToEndTests MechanicalOrderingCompatibilityTests
python3 .ai/scripts/tests/test_assurance_ordering.py MechanicalOrderingControlsTests
python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_attested.py
python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_measure.py
```

The narrow slice E2E is MechanicalOrderingEndToEndTests; its passing identical acceptance command from convergence supplies final E2E evidence instead of another run. Existing attestation/measurement suites run at their integration boundary, not repeatedly in the edit loop. Before repeating a check, run lifecycle.py reuse LABEL_OR_CMD; REUSE prohibits rerunning unchanged inputs.

Fast prefreeze/source-boundary guard:

```text
git diff --exit-code 02dd97586873f24a604224aa5ad186a60c4104e7 -- .ai/scripts/assurance_inputs.py .ai/scripts/tests/test_assurance_inputs.py .ai/scripts/tests/test_lifecycle_conformance.py
git diff --check
```

Trace and acceptance:

```text
python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-closeout-c2.md --plan docs/assurance/plan-closeout-c2.md --tests .ai/scripts/tests/test_assurance_ordering.py
python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-closeout-c2.md
```

Full gate once on the final reviewed frozen candidate:

```text
python3 .ai/scripts/lifecycle.py run closeout-c2-framework -- python3 .ai/scripts/run_tests.py -j 8
```

One final-gate validator owns background supervision. Use wait_check.py start/wait according to repository policy; retain default documented wait limits and do not poll with short sleeps, ps, log tails or repeated full-context reads. Root reports phase changes and actual completion. The full gate is justified by changed shared assurance/lifecycle/measurement behavior and contains all prior-profile regression coverage; it must not be substituted by focused checks.

Final diff/scan/audit checks run via lifecycle.py run with recorded labels as required; retrospective closes before stage verify. Check eligibility with reuse before repeating labels. Historical evidence is cited with its exact source/runtime scope, never rescored as this candidate's PASS.

## Requirement trace

| Requirement | Steps | Acceptance class |
| --- | --- | --- |
| R1 | 1, 2, 4 | MechanicalOrderingSelectionTests |
| R2 | 1, 3 | MechanicalOrderingProducerTests |
| R3 | 2 | MechanicalOrderingLegacyTests |
| R4 | 2, 4 | MechanicalOrderingInvalidMetadataTests |
| R5 | 1, 4 | MechanicalOrderingEndToEndTests |
| R6 | 3, 4 | MechanicalOrderingCompatibilityTests |
| R7 | 5 | MechanicalOrderingControlsTests |
| R1–R7 | 6 | Convergence, independent review, final integrated gate and Verify |

## OKF impact

Framework mode has no knowledge/. Planned-path okf.py affected exits1/no bundle: INAPPLICABLE, not PASS. Update existing lifecycle guide, preserve ignored working docs and Git-scratch receipts. Do not initialize knowledge or invent log/records results. The C1 recovery artifacts and all5n/earlier canonical reports remain unchanged.

## Risks and mitigations

- Legacy evidence can become ambiguous: intentional approved behavior; test well-formed rerun remediation separately from malformed-data reconciliation.
- False precision: integer interval arithmetic retains represented units; strict calendar checks and year-end boundaries prevent accidental rounding/overflow.
- Profile-pin drift: no lifecycle setup/import/signature/decorator changes, no conformance-class or profile edits; explicit diff guard and final full suite enforce the boundary.
- Publication confused with completion: distinct convergence clocks and delayed-publication controls exercise the difference.
- Golden formatting drift: normalize only optional mechanical fractional timestamps while preserving golden content and attestation stage times.
- Control inflation: exactly seven variants, confirmed bytes, nonempty intended assertions and restoration.
- Clock reversal: remains a disclosed limitation, not silently solved or claimed.

## Out of scope

C1 proof-gap execution/closure; C3 tutorial work; profile additions/pin refreshes or5o; general reuse/attestation redesign; new schema/store/event order; historical record repair/rescoring; native/model/session/trust work; base refresh/worktree changes; autonomy; delivery actions; full initiative completion claims.

## Open decisions

None. The user approved this plan through implementation, independent review and Verify, with changes uncommitted. A concrete implementation discovery that contradicts the approved boundary returns for scope resolution rather than being hidden as a mechanical choice. C1 remains open and 5o/profile work remains paused.
