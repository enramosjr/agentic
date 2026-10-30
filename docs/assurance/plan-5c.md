# Implementation Plan: static harness-wiring input profile

Approved by human:enramosjr in this chat, 2026-10-29 America/Chicago (“approved”, replying to the request for plan approval). Specification: `specification-5c.md`, approved including D1-D4. L2; planner role; Python principal engineer. Implementation under this plan is authorized; commit/push/PR/merge remain excluded.

## Objective

Add one declared input profile for the existing exact HarnessWiring command through the current exporter, proving controlled static wiring execution and repository-file freshness behavior.

## Success criteria

- R1: Only the approved exact argv gains registration as `python-harness-wiring`; both prior profiles retain identity, argv, ordered inputs, rationale and behavior.
- R2: Export preserves the seven approved ordered patterns with source-backed rationale and independent dependency coverage.
- R3: Existing read-only export, text/JSON, supplements, validation and refusal contracts remain intact.
- R4: Adoption remains explicit/advisory; inference, full-suite coverage/refusal, evidence semantics, schemas, gates and receipt exclusions remain unchanged. The guide accurately describes the static claim.
- R5: Actual three-test execution produces matching framework evidence, unchanged/unrelated-change REUSE and relevant-input RERUN; malformed or missing wiring fails actual execution.
- R6: Explicit adopter adoption produces specified VERIFIED/STALE/UNVERIFIED outcomes; five confirmed broken variants fail their intended assertions.

## Current state

`.ai/scripts/assurance_inputs.py:17-46` contains two literal entries. `catalog_checked():75-100` validates the catalog structurally; `suggest():137-161` matches exact argv and validates only the selected profile's filesystem scope. No exporter algorithm change is needed.

`.ai/scripts/tests/test_assurance_inputs.py:34-121` supplies disposable Git repositories, copied production scripts, public export, lifecycle subprocesses and preflight helpers. `ArchitectureFixture:350-389` demonstrates independent byte snapshots and count-before-exit checks. Framework/adopter flows at `506-567` demonstrate ledger identity, freshness and receipt exclusion; controls at `570-620` confirm disposable mutations and intended assertion failures. The new fixture reuses mechanisms, not architecture dependency assumptions.

`HarnessWiring` in `.ai/scripts/tests/test_lifecycle_conformance.py:270-294` has three JSON-parsing/static declaration tests and a direct unittest entry point at `297-298`. Its import closure and ambient runtime effects are documented in the approved spec. The class neither executes hooks nor copies script directories. `.ai/lifecycle.md:210-222` documents current advisory export/adoption and both existing profiles.

Planner repository inspection found no pyproject/setup/tox/nox configuration or `.github` files. Existing stdlib unittest conventions and the delivered framework runner remain the validation interface.

## Proposed approach

Change exactly three existing tracked files:

1. `.ai/scripts/assurance_inputs.py`: append one literal catalog entry with seven rationale entries.
2. `.ai/scripts/tests/test_assurance_inputs.py`: add HarnessWiring-specific fixture support and the eight acceptance classes named by the approved spec.
3. `.ai/lifecycle.md`: document exact command, scope, conservative invalidation, static claim and explicit adoption.

Use a separate new `HarnessWiringFixture` subclass. Preserve existing fixture constants, setup, preflight and assertions. The base fixture already copies production scripts and disk helper; the new fixture copies the selected conformance module and the three actual JSON files, retaining them as supported fixture inventory. JSON is inert test data; install no native integration or Git hook.

Handwrite command, patterns, prior-profile expectations and the source-derived dependency oracle independently of PROFILES. Cover the target, disk helper, eager production imports, lazy setup paths and direct JSON reads. No architecture test helpers, guide input or copied-directory rationale enter this profile by analogy.

## Boundaries and invariants

Every repository command must explicitly use cwd `/home/enramosjr/Projects/agentic-assurance-7`. Retain branch `claude/assurance-increment-7` and base HEAD `95c873d896e1ef53b89dcb75e6f6e1c1984c517e`. The explicit no-base-refresh restriction supersedes the validation policy's default fetch/merge recommendation.

One implementer owns all three files and fixtures; no parallel mutation lanes. Independent review is read-only. Do not modify target conformance tests, actual hook configuration, exporter algorithms, lifecycle/assurance/ledger algorithms, runner, installer, schemas or inference.

Conservative scope intentionally includes unused non-test descendants and supported future scripts. Runtime/executable/environment, temporary storage/mount state, ignored files and external mutable data remain outside the repository-file claim. All docs/assurance artifacts remain ignored, local and uncommitted. Preserve historical receipts and their original source/runtime scopes. No native/model evaluation, sessions, trust grants, historical rescoring, invoking-checkout knowledge initialization, new worktree, branch/base changes or delivery actions.

## Implementation steps

### Step 1: Establish failing exact-profile and export acceptance

**Files/symbols:** existing input-test module; new HarnessWiringFixture, handwritten constants/oracle, HarnessWiringProfileTests, HarnessWiringDependencyTests and HarnessWiringExportTests.

Write tests before catalog changes. Copy the real target and JSON data into the new disposable fixture; retain the base fixture's helper/production setup. Check exact argv/root and rejected variants; both prior profiles including rationale; seven ordered patterns; exclusion/restoration; eager/lazy setup coverage; direct JSON literals; future supported non-test scripts/descendants; unrelated test/document exclusion; and boundary-drift source sentinels.

Exercise public text/JSON and parsed Inputs/lifecycle token parity, positive supplements, required-literal absence, ignored inventory, escaping paths and refusal without a usable candidate. Put nonexecution sentinels in target/helper files without poisoning shared exporter dependencies such as ledger. Malformed fixture JSON must still export successfully because export validates paths, not hook semantics. Snapshot source/evidence to prove export immutability.

**R1-R3 failing-closed check:** record RED using:

```text
python3 .ai/scripts/lifecycle.py redgreen red -- python3 .ai/scripts/tests/test_assurance_inputs.py HarnessWiringProfileTests HarnessWiringDependencyTests HarnessWiringExportTests
```

Inspect the actual failure reason: absent exact profile, not broken fixture setup.

### Step 2: Satisfy the profile contract with one declaration

**File/symbol:** assurance_inputs.py, PROFILES.

Append approved ID, root cwd, exact argv, seven ordered patterns and accurate per-pattern rationale. Explain conservative production import/lazy setup scope, test exclusion/restoration and three direct JSON reads. Preserve both prior entries and all algorithms.

**R1-R3 check:** record GREEN with Step 1's identical command. Retain catalog-validation coverage without requiring all profiles' files in every fixture.

### Step 3: Preserve compatibility and explain static adoption

**Files/symbols:** input-test module and lifecycle guide; new HarnessWiringCompatibilityTests.

Write compatibility checks before guide changes. Check both prior profiles, full-suite refusal/broad inference, evidence command/declaration identity and receipt behavior. Document exact new command/ID, seven patterns, extra invalidation, explicit manual adoption, static declarations only and runtime/read-completeness limits.

**R1, R4 check:** `python3 .ai/scripts/tests/test_assurance_inputs.py HarnessWiringCompatibilityTests`. Guide prose is test-first exempt. Preserve prior-profile tests for integrated verification; new assertions must fail when their documented/compatibility criteria are unmet.

### Step 4: Prove framework execution and static failure boundaries

**File/symbols:** input-test module; new HarnessWiringFrameworkEndToEndTests and HarnessWiringFailureTests.

Drive the public exporter in an isolated framework fixture. Independently execute the exact selected command; parse actual unittest output and require exactly three tests before interpreting exit status. Require success and stable selected input membership/bytes. Then record through lifecycle run with exported input tokens; compare recorded argv, ordered declaration and exit with export.

Assert REUSE unchanged and after separate unrelated test/document edits. Restore each change between cases. Assert RERUN after separate edits to each JSON, target, disk helper, a representative eager production import such as review_guard.py and a new supported non-test script. JSON freshness edits must preserve valid JSON and required wiring. Assert no framework knowledge bundle appears.

For each harness JSON in disposable fixtures, independently confirm malformed bytes and removed required wiring, then require actual target execution to fail for the intended JSON/wiring error. Require the expected test count, nonzero exit and intended failure instead of accepting startup/import failure. Execute only the Python test; never invoke declared hook commands.

**R5 check:** `python3 .ai/scripts/tests/test_assurance_inputs.py HarnessWiringFrameworkEndToEndTests HarnessWiringFailureTests`. Write test logic before treating fixture helpers as complete; the broken variants in Step 5 demonstrate sensitivity where the existing product already satisfies the path.

### Step 5: Prove adopter freshness and reject false evidence

**File/symbols:** input-test module; new HarnessWiringAdopterEndToEndTests and HarnessWiringControlTests.

Create an ordinary adopter only inside a disposable fixture, removing its framework marker and using existing initialization/adoption mechanisms. Publish a temporary requirement with public exported Inputs. Independently prove actual three-test execution, run the obligation and assert VERIFIED and stable selected inputs.

Assert retained VERIFIED after unrelated test/document edits; STALE after separate edits to each JSON, target/helper, representative production import and supported new non-test script; UNVERIFIED after unmatched ordered declaration and changed command identity. Restore each mutation between cases. Assert the producer's existing receipt exclusion remains present and effective, including after receipt publication changes excluded bytes.

Implement five controls in independent disposable sources:

1. Omit `.claude/settings.json` from profile inputs and rationale.
2. Omit `.codex/hooks.json` from inputs and rationale.
3. Omit `.cursor/hooks.json` from inputs and rationale.
4. Loosen exact argv matching.
5. Replace the selected target with a zero-test unittest variant.

Confirm actual mutation bytes before running a narrowly selected acceptance method. Each omitted-JSON control must permit the valid actual static command to pass, then fail the intended missed-freshness assertion after a valid wiring-preserving JSON edit. Removing rationale alongside the input prevents catalog validation from preempting the criterion. Loose argv must fail registration rejection; zero tests must fail the independent exactly-three count regardless of Python's empty-run exit behavior. Require intended assertion failures and no unrelated errors. Never recurse into the controls themselves.

**R6 check:** `python3 .ai/scripts/tests/test_assurance_inputs.py HarnessWiringAdopterEndToEndTests HarnessWiringControlTests`.

### Step 6: Close acceptance, review, synchronization and verification

**Files:** three planned tracked files; new ignored docs/assurance/implementation-5c.md, review-5c.md and slice logs.

Finish edits and guide synchronization. Run approved acceptance through convergence and trace requirements into implementation tests. Obtain independent two-pass review: spec compliance, then quality/completeness/knowledge synchronization. Repair and re-review findings before freezing the candidate. All R1-R6 checks, five confirmed controls and six malformed/missing-wiring cases must be represented; no placeholder or native-enforcement claim remains.

Before repeating a check run lifecycle reuse; reuse current covering PASS on unchanged inputs. Repair only the failing lane first; source changes require current convergence before Verify. Close/report the retrospective before Verify, applying existing exact-count and confirmed-mutation observations unless a new evidenced lesson arises.

Freeze the reviewed candidate on the authorized current base, run the full framework gate once, then record diff/scan/audit and Verify with exact outcomes. Report unavailable checks honestly. **R1-R6 checks:** commands below. Stop with verified, uncommitted changes; delivery remains unauthorized.

## Testing strategy

Use public export/lifecycle/assurance interfaces, handwritten independent oracles, exact declaration/command identity and real isolated framework/adopter execution. Count tests independently of lifecycle's suppressed successful child output. Keep valid JSON freshness edits separate from deliberate malformed/missing-wiring cases. Confirm control bytes and intended failures.

The production change is literal registration. New test logic is test-first where practicable and proven nonvacuous by controls; guide prose is exempt. Preserve old fixtures/assertions rather than broadening them for every catalog entry. No claim of complete runtime dependency discovery or native enforcement follows from these tests.

## Validation commands

All commands below are future implementation checks, not planning receipts. Use the explicit checkout cwd on every invocation. Reload relevant validation-policy sections before Gate 4/long checks; record criterion, input scope and lack of valid covering evidence before an expensive run.

- Focused loop: Step 1's exact RED/GREEN command and Step 3's compatibility command under lifecycle run as appropriate.
- Trace: `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5c.md --plan docs/assurance/plan-5c.md --tests .ai/scripts/tests/test_assurance_inputs.py`.
- Complete slice acceptance/E2E: `python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-5c.md`. This runs all six approved acceptance commands, including real framework/adopter paths and controls. Cite current passing receipts instead of immediately rerunning identical E2Es.
- Full gate once after review/freeze: `python3 .ai/scripts/lifecycle.py run inputs-5c-framework -- python3 .ai/scripts/run_tests.py -j 8`.
- Diff: `python3 .ai/scripts/lifecycle.py run inputs-5c-diff -- git diff --check`.
- Scan: `python3 .ai/scripts/lifecycle.py run inputs-5c-scan -- python3 .ai/scripts/lifecycle.py scan-diff`.
- Audit: `python3 .ai/scripts/lifecycle.py audit`.
- Before any repeated check: `python3 .ai/scripts/lifecycle.py reuse LABEL_OR_CMD`.

Use existing wait_check background supervision, checking its CLI help before constructing launch commands, with new framework-5c.log/converge-5c.log artifacts. Delegate long waiting in the launch host namespace; do not use short model polling or reduce wait_check's default wait budget. No model waiting call exceeds the host communication limit. Successful child output may be suppressed; do not invent full-suite counts.

No real-agent lifecycle evaluation is applicable: this slice changes neither tier/stage rules nor native enforcement. The complete script suite covers profile/document checks and existing scripted evaluation. No old suite is rerun merely because this is a new chat, and no historical receipt verifies this profile.

## OKF impact

Planning-time `python3 .ai/scripts/okf.py affected .ai/scripts/assurance_inputs.py .ai/scripts/tests/test_assurance_inputs.py .ai/lifecycle.md` returned exit 1 because this framework has no bundle. Record framework-mode INAPPLICABLE, not PASS; do not initialize knowledge or fabricate records evidence. Repeat impact assessment during verification, synchronize existing lifecycle guide, retain new-slice ignored reports and preserve prior evidence. Report framework-tool/environment limitations honestly.

## Risks and mitigations

- Catalog growth disturbing prior fixtures: preserve fixture setup; filesystem validation applies only to the selected profile.
- Self-validating scope: independent source-derived oracles and three omitted-JSON controls.
- Empty execution appearing successful: exact-three count before exit interpretation.
- JSON syntax masking freshness: wiring-preserving JSON edits; separate actual-failure cases.
- Accidental native execution: fixture JSON stays data and no native integration is installed.
- Conservative extra invalidation: document breadth without claiming minimal inputs or full runtime coverage.
- Evidence/runtime/PID-namespace drift: preserve scopes and supervise in the launch namespace; missing visibility is never PASS.

## Out of scope

Further registrations, full module/aliases, runtime discovery, narrower gates, automatic adoption, schema/inference changes, hook edits/activation, native/model/session/trust work, historical rescoring, invoking-checkout knowledge initialization, worktrees, branch/base changes, commit, push, PR and merge.

## Open decisions

None. The user approved this plan; record Plan and proceed with implementation.

## Planning validation

- Approved spec: analyze exited 0; trace exited 0 for six requirements. Intent recorded with `--approved-by human:enramosjr` from the user's explicit approval in this chat.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5c.md --plan docs/assurance/plan-5c.md` -> exit 0, all six requirements traced into the plan. Future tests are absent by design and no implementation trace is claimed.
- `python3 .ai/scripts/lifecycle.py audit` -> exit 0 for active record `20261029T142705Z-claude_assurance-increment-7.json`.
- No product/test command executed during planning. No source edit or historical evidence modification. Specification and plan are ignored local artifacts; Plan approval and registration remain pending.
