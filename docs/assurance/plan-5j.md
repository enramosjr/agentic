# Implementation Plan: tier documentation and runtime tier/key-set input profile

Proposed, awaiting separate human plan approval. Based on approved `docs/assurance/specification-5j.md`, R1–R6 and D1–D4. L2; planner role; Python principal engineer. Required read-only planner delegation completed. Intent is recorded. No implementation is authorized until the user approves this plan.

## Objective

Add the exact-method `python-tier-doc-contract` profile through the existing literal input exporter, with independent dependency-boundary, execution-count, identity and freshness verification. Preserve all nine delivered profiles and existing assurance mechanisms.

Exact command:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Tiers.test_tier_definitions_agree_across_agents_lifecycle_and_script
```

## Success criteria

- R1: Only the approved repository-root argv gains the profile; all nine predecessor entries, rationales, exports and positive registrations remain intact.
- R2: Exactly six approved ordered patterns/rationales and an independent runtime-loop/two-read/interpolation/set oracle; reviewed drift and freshly demonstrated reachable excluded additions are rejected.
- R3: Public text/JSON export remains read-only, nonexecuting and path-based, with existing supplement/refusal behavior.
- R4: Guide claims describe conservative invalidation and observed-runtime assertions with all approved limits.
- R5: Framework fixtures independently establish one passing test and runtime baseline, identities, every freshness outcome and nine intended failures on the separately confirmed four-tier baseline.
- R6: Adopter fixtures prove existing VERIFIED/STALE/UNVERIFIED behavior and receipt exclusion; four confirmed broken controls fail for intended reasons.

## Current state

`assurance_inputs.py:17–163` contains nine literal profiles. `catalog_checked`, `check_paths` and `suggest` already validate catalog shape, inventory/path support and exact argv/root identity; no algorithm change is needed.

`test_lifecycle_conformance.py:191–195` loops over runtime `lifecycle.TIERS`, requires `f"**{tier}**"` in literal AGENTS.md, requires unescaped regex `rf"\| {tier} "` in literal .ai/lifecycle.md, then compares `set(lifecycle.REQUIRED)` with `set(lifecycle.TIERS)`. Leave it unchanged. `lifecycle.py:70–77` source currently defines four tier values and matching REQUIRED mapping keys; source literals are not runtime observation.

Root/import setup and `text` are at test_lifecycle_conformance.py:15–27. disk_tmp.py:10–20 calls scratch.require_disk; scratch.py:11–26 probes mount/storage state. Lifecycle eagerly imports scratch/review_guard and constructs lazy loaders and protected decorators. review_guard.py:23–26,629–639 eagerly imports ledger/scratch and constructs nested decorate; wrapper construction does not establish producer-body execution.

Reusable test mechanisms:

- `Fixture`, test_assurance_inputs.py:34–121: isolated repositories, bounded subprocesses, public export/refusal and lifecycle helpers.
- `report_setup_digest`:993–1014: conservative setup and selected called-body fingerprints.
- `StageDocFixture` and eight classes:3320–3814: analogous count-first execution, byte stability/restoration, public export, freshness, adopter and broken controls. Their heading-tuple/STAGES oracle does not fit this candidate.
- StageDoc's preservation helper pins an older eight-profile commit; the new helper must compare all NINE complete profiles against delivered HEAD `f2c0b6db99e797b99781034a7f8b4b44b17f5f00`.
- `.ai/lifecycle.md:248–250`: latest profile guide paragraphs; extend adjacent documentation without changing predecessor prose.

Fresh inspected refusal expectations use generic unregistered variants; no obsolete candidate negative needs replacement. `okf.py affected` on the three proposed files reports no framework knowledge bundle; synchronization uses the existing guide.

## Proposed approach

Change exactly three existing tracked files:

1. `.ai/scripts/assurance_inputs.py`: append one literal entry with six rationales.
2. `.ai/scripts/tests/test_assurance_inputs.py`: append independent TIER_DOC constants, TierDocFixture and eight acceptance classes.
3. `.ai/lifecycle.md`: document exact command/declaration and bounded claims.

Derive TierDocFixture directly from Fixture. Reuse generic utilities unchanged; do not alter predecessor fixtures/pins/tests. Copy selected files and compatibility-only inputs needed by predecessor public exports; those copies do not define selected reads. Define expected values independently of PROFILES.

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
AGENTS.md
.ai/lifecycle.md
```

No algorithm, schema, persistence, dependency, matching, inference, normalization, gate or receipt mechanism changes.

## Boundaries and invariants

Every repository command uses explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Retain existing branch `claude/assurance-increment-7` and delivered HEAD `f2c0b6db99e797b99781034a7f8b4b44b17f5f00`; no base refresh, switch/reset or worktree creation. One implementer owns all three tracked files and fixtures sequentially; independent review is read-only. No parallel edit lanes are proposed because all tests share one module.

Preserve selected assertions, all nine complete profiles/rationales/tests/positive siblings and existing assurance mechanisms. Both direct documents remain explicit despite Markdown exemptions. Conservative production coverage includes unused/future supported non-test descendants. Conservative pins do not imply uncalled wrapped bodies were reached.

Keep all docs/assurance ignored/local/uncommitted and preserve historical evidence. Only disposable ordinary adopters initialize knowledge; the invoking framework never does. Restore disposable mutations in cleanup/finally. Keep freshness edits, static failures and control mutations separate. Runtime/executable/environment, ignored/external data and storage/mount state remain outside repository-file claims.

No native/model/session/trust actions, historical rescoring, autonomy driver, commit/push/PR/merge or Ship/delivery. This plan proposes verification with changes left uncommitted.

## Implementation steps

### Step 1: Exact registration and public export fail before catalog addition

R1, R3; test_assurance_inputs.py first, then assurance_inputs.py.

Write independent TIER_DOC command/input/document declarations, TierDocFixture, TierDocProfileTests and TierDocExportTests. Read literal PROFILES from delivered f2c0b6db99e797b99781034a7f8b4b44b17f5f00, require nine expected IDs, and compare complete dictionaries and public export argv/inputs/rationales.

Check exact registration, root/argv variants, formats/token parity, ordered supplements, required literal/path/inventory refusals and nonmutation. Use sentinel selected module/helper contents to prove export does not import/execute them while retaining usable exporter dependencies. Existing documents with failing assertions remain exportable. Preserve existing generic refusals and sibling positives.

Record absent-profile RED, then append only the literal entry/rationales and record identical GREEN:

```text
python3 .ai/scripts/lifecycle.py redgreen red -- python3 .ai/scripts/tests/test_assurance_inputs.py TierDocProfileTests TierDocExportTests
python3 .ai/scripts/lifecycle.py redgreen green -- python3 .ai/scripts/tests/test_assurance_inputs.py TierDocProfileTests TierDocExportTests
```

The RED must identify absent registration, not fixture/import failure. The two commands occur sequentially around the catalog change.

### Step 2: Independent source/setup guards reject boundary drift

R2; new TierDocDependencyTests and reviewed pins in test_assurance_inputs.py.

Verify ordered patterns/rationales and actual ledger.input_paths selection. Include selected module/helper, BOTH documents, production imports, a future supported script and non-Python production descendant. Exclude unrelated tests/non-input documents and compatibility-only files after subtracting direct inputs.

Inspect the AST independently: require the loop target and lifecycle.TIERS iterator; BOTH literal text calls within the loop; assertIn with bold interpolation of the bound tier; assertRegex with the distinct unescaped pipe/space interpolation; and final assertEqual of runtime REQUIRED/TIERS through set. Reject additional reads and unreviewed structure. Pin reviewed method and six setup surfaces: selected module, disk_tmp, scratch, lifecycle, review_guard and ledger. Fixed reviewed expectations must not be generated from current source during a test.

Derive mutation sites from current eager setup, selected method, text, require_disk, lazy, protected/nested decorate and supported import of an excluded helper. Do not impose historical count thirteen. Each claimed reachable addition must confirm mutation bytes and excluded-data absence/membership, fail actual selected execution for intended missing-data access, pass exactly one selected test after supplying data, then trigger intended boundary rejection. Insert body mutations after docstrings and BEFORE the earliest decorator of the first statement. Uncalled bodies remain conservative pins.

Check: `python3 .ai/scripts/tests/test_assurance_inputs.py TierDocDependencyTests`. Deliberate disposable broken variants establish sensitivity of later-written guard logic.

### Step 3: Guide publishes the bounded contract and preserves compatibility

R1, R3, R4; TierDocExportTests/TierDocCompatibilityTests and .ai/lifecycle.md.

Complete export checks: text/JSON parity, input-line parsing, supplement order, review status, byte nonmutation/nonexecution and missing/ignored/escaping/unsupported literals, unsafe supplements, wrong root and unknown argv. Check nine predecessor public exports and existing inference/full-suite refusal, matching, schemas, gates and receipt mechanisms.

Document exact exporter command/ID and six patterns, repeated literal reads, observed-tier bold/regex presence and observed REQUIRED/TIERS set equality. State conservative extra invalidation and all taxonomy/vacuity/type/order/uniqueness/REQUIRED-value/unescaped-regex/semantics/enforcement limits. Export remains path-only; adoption explicit/manual/advisory. Guide prose is test-first exempt; required guide claims get automated assertions.

Checks: TierDocExportTests and TierDocCompatibilityTests via the approved commands below. Correct any deliberately failed lifecycle-run label with a PASS under the same label, after reuse permits rerun.

### Step 4: Actual execution, runtime baseline and framework outcomes are proven separately

R3, R5; TierDocFrameworkEndToEndTests and TierDocFailureTests.

Capture actual selected execution independently. Require one unambiguous unittest count equal to one before exit interpretation, plus appropriate success/failure markers. Snapshot selected repository bytes before/after and assert stability.

Observe TIERS and REQUIRED iteration separately in a disposable subprocess using the same fixture interpreter/environment and selected-module setup. Do not alter selected command/assertions/bytes. Compare runtime values with independently inspected source baseline. Any baseline mismatch stops for human scope/count review, not a changed selected method or silently adjusted matrix.

Drive public export and real lifecycle run/reuse; compare ledger argv, ordered inputs and exit with export. Require REUSE unchanged and after separate unrelated-test/non-input-document edits. Require RERUN for separate assertion-preserving changes to EACH direct document, selected module, disk helper, representative production import and new supported script. Confirm bytes and restore, requiring REUSE recovery. Document freshness edits must still pass actual selected execution. Invoking-framework knowledge remains absent.

After separate runtime confirmation of the four-tier baseline, construct nine failures: four AGENTS cases removing EVERY occurrence of each bold tier token; four lifecycle-document cases removing EVERY match of each corresponding tier regex; one REQUIRED-key drift preserving TIERS and import/CLI setup. Each must remain exportable, execute exactly one selected test, fail its intended assertion and restore bytes. REQUIRED drift must identify intended changed set membership and reach final equality. Freshness and failure fixtures remain distinct.

Check: the approved combined framework/failure acceptance command below.

### Step 5: Adopter states and four broken controls reject false evidence

R1, R4, R6; TierDocAdopterEndToEndTests and TierDocControlTests.

Use a separate disposable ordinary adopter with explicit public-export adoption. Require initial UNVERIFIED, independent actual one-test proof, actual assurance run, stable input bytes and VERIFIED. Unrelated edits retain VERIFIED; EACH input/new-script edit yields STALE, then restored bytes recover VERIFIED. Reordered declarations/changed argv yield UNVERIFIED. Compare recorded argv/ordered inputs/exit and retain producer receipt exclusion; receipt-only additions preserve VERIFIED.

Four independent controls omit AGENTS, omit direct lifecycle doc, loosen exact argv matching, or substitute an actual empty suite ignoring selector. Confirm mutation bytes and exactly the intended nested acceptance failure, without unrelated errors or recursion into controls. Each omission must fail freshness while assertion-preserving document edits pass selected execution. Independently establish Ran 0 tests, then count rejection before Python-dependent exit interpretation; one loader _FailedTest is insufficient.

Check: the approved combined adopter/control acceptance command below.

### Step 6: Acceptance, independent review and frozen-candidate verification close the slice

R1–R6; three tracked files plus new ignored implementation/review/evidence artifacts.

Finish edits/self-review/guide sync, trace all requirements, evaluate affected paths and check diff/whitespace. Run the six acceptance groups once through converge on the completed candidate, requiring 6 PASS / 0 FAIL / 0 MANUAL. No historical PASS covers this tenth profile.

Obtain independent two-pass review; preserve the complete canonical returned report unchanged. Repair blockers with narrow checks and re-review substantive changes. Close/report retrospective before Verify using an evidence-backed no-new-lessons outcome or supported observation; do not promote binding rules without approval.

Freeze on the explicitly retained base: the user's no-base-refresh constraint overrides the general refresh recommendation. One owner runs the full framework gate once after review under background supervision. Retain exact source/runtime scope; suppressed child output establishes no full-suite count. Record Review/Verify only when exits hold; stop verified/uncommitted, with no Ship/delivery action.

## Testing strategy

Registration is test-first. New guard logic must be written first or challenged with deliberately broken variants. Reuse generic helpers without modifying predecessor fixtures. Keep source pins, actual one-test proof, runtime observation, freshness, intended assertion failures, reachable additions and omission/matching/count controls as separate evidence.

Focused checks run in the edit loop. Convergence owns completed slice E2Es; do not duplicate unchanged completed E2Es. Before ANY repeated check run lifecycle.py reuse LABEL_OR_CMD; never rerun REUSE. Correct failed run labels under identical labels. One integrated full gate covers predecessor regression on the frozen candidate. Load validation-policy sections before Gate 4 and any minutes-long check; justify expensive execution with acceptance/input scope and absence of a covering valid PASS.

## Validation commands

All commands use explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Proposed TierDoc classes become runnable only after separately approved implementation. The six approved acceptance commands are unchanged:

```text
python3 .ai/scripts/tests/test_assurance_inputs.py TierDocProfileTests
python3 .ai/scripts/tests/test_assurance_inputs.py TierDocDependencyTests
python3 .ai/scripts/tests/test_assurance_inputs.py TierDocExportTests
python3 .ai/scripts/tests/test_assurance_inputs.py TierDocCompatibilityTests
python3 .ai/scripts/tests/test_assurance_inputs.py TierDocFrameworkEndToEndTests TierDocFailureTests
python3 .ai/scripts/tests/test_assurance_inputs.py TierDocAdopterEndToEndTests TierDocControlTests
```

Run final acceptance through converge rather than duplicate standalone E2Es:

```text
python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-5j.md
python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5j.md --plan docs/assurance/plan-5j.md --tests .ai/scripts/tests/test_assurance_inputs.py
python3 .ai/scripts/lifecycle.py run inputs-5j-framework -- python3 .ai/scripts/run_tests.py -j 8
```

Retain converge-5j.log and framework-5j.log. Supervise long checks with repository background/wait mechanisms; no repeated unchanged suites. Run applicable lifecycle scan-diff/audit/status and tracked-status/ignore checks. No tier/stage-rule change is proposed, so real-agent evaluation is outside scope. No selected baseline execution, runtime import, product test or acceptance command runs during planning.

## OKF impact

Planning `okf.py affected` on all three proposed tracked paths returned exit 1/no framework bundle. Synchronization is inapplicable: do not initialize knowledge, capability baseline/log or claim records PASS. Update the existing guide; keep specification/plan and future implementation/review/log artifacts ignored under docs/assurance.

## Risks and mitigations

- Wrong predecessor oracle: resolve runtime loop, BOTH literal reads, distinct interpolation and final runtime sets independently; keep reviewed pins.
- Source/runtime confusion or inflated taxonomy: separate runtime observation, stop on baseline mismatch, preserve selected assertions and stated limits.
- Wrong failure/reachability proof: require count and intended diagnostic, absent-data failure/supplied-data success, with no syntax/import/CLI substitute.
- Mutation contamination: confirm bytes, isolate cases, restore originals and assert freshness recovery.
- Regression: compare all nine complete entries/exports against delivered HEAD and run integrated full suite once.
- Evidence inflation: preserve historical records and exact source/runtime/environment scopes.

## Out of scope

Selected-test changes; broader registration; fixed/nonempty taxonomy; actual gates; document semantics; arbitrary-tier regex validation; algorithm/schema/dependency/gate changes; generalized dependency discovery; automatic adoption; reduced gates; native/model/session qualification; trust grants; historical rescoring; base/worktree/branch changes; commit/push/PR/merge.

## Open decisions

None. Approved D1–D4 resolve behavioral scope. The plan is ready for separate human approval; implementation remains pending that approval. Plan stage will be recorded only after approval.

## Planning validation

- Approved specification analysis and trace passed before Intent was recorded with `--approved-by human:enramosjr`.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5j.md --plan docs/assurance/plan-5j.md` -> exit 0, all six requirements traced.
- `git check-ignore docs/assurance/specification-5j.md docs/assurance/plan-5j.md` -> exit 0, both ignored.
- `git diff --check` and `git status --short --untracked-files=no` -> exit 0, tracked state clean.
- Lifecycle status: L2 feature, Intent complete; Plan/Review/Verify still required. No Plan approval or stage is inferred.

Required read-only planner delegation returned the implementation-ready plan after source inspection. No source edits, runtime observations/imports, product tests, new knowledge bundle or delivery action occurred during planning. No remote check performed.
