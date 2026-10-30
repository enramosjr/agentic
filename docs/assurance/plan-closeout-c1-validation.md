# Implementation Plan: Bounded C1 class-level negative proof

2026-10-29 America/Chicago. **Draft for approval; no coding or validation execution authorized yet.** Tier L2; planner role; Python principal-engineer persona. The persona materially informs subprocess cleanup, isolated mutable state and structured test-result attribution.

## Objective

Implement and independently review a local validation operator, then collect the finite current-candidate evidence specified by the [approved C1 validation spec](specification-closeout-c1-validation.md). The user approved that spec in the message requesting this plan; Intent is recorded as human:enramosjr. The approved spec body is retained unchanged, including its original draft wording. C1 remains open until the later campaign and independent evidence review succeed.

## Success criteria

- R1: Exact current candidate identity, historical eleven-class roster and complete execution-input pins are present and unchanged.
- R2: Eleven unchanged class baselines execute all thirty expected methods with no failure, error, skip, missing test or unexpected success.
- R3: Eleven distinct approved mutations each cause exactly the designated method to fail at the designated unchanged assertion; no substitute failure earns credit.
- R4: Four invalid-proof controls are rejected; incomplete/duplicate maps and restoration failure cannot produce success.
- R5: All candidate mutations remain in disposable copies; restoration and invoking-file equality succeed within 180 seconds per test process and twenty minutes overall.
- R6: Raw evidence supports the qualified report, then an independent reviewer approves the class map before any C1 closure statement.

## Current state

- Invoking checkout: `/home/enramosjr/Projects/agentic-assurance-7`; branch `claude/assurance-increment-7`; HEAD `02dd97586873f24a604224aa5ad186a60c4104e7`. Existing source changes are the verified, uncommitted C2 candidate, documented in [its implementation report](implementation-closeout-c2.md). No branch, base or worktree operation is required.
- `.ai/scripts/tests/test_assurance.py` contains ten original area1 classes and twenty-nine current methods. `.ai/scripts/tests/test_lifecycle_conformance.py::Assurance` adds one original class/method. The fixture-only Case class is excluded. Original authority and evidence qualifications remain in [C1 reconciliation](closeout-c1-reconciliation.md).
- The assurance fixtures copy root `.ai/scripts/*.py` into their own temporary adopter repositories and exercise the real lifecycle CLI. The conformance method reads the guide relative to its copied module. Neither test assertions nor fixture expectations need changes.
- `.ai/scripts/tests/disk_tmp.py` selects disk-backed temporary storage and can otherwise fall back to the user's cache. The operator must supply isolated disk-backed temporary and cache directories before importing any copied tests.
- Existing `run_tests.py::worker` demonstrates structured unittest result collection, but does not record the assertion frames required here. Reuse that pattern in the local operator; do not modify run_tests.py.
- `lifecycle.py::cmd_converge` executes the identical acceptance command separately for each of the six requirements. The operator must run one campaign and subsequently revalidate/reuse its complete frozen evidence rather than launch six campaigns.

## Candidate pins

The approved spec's exact byte SHA256 is `4eccb9ae35f35a551d2aa051982843ad587751aa6e0ecd86090eb982544acdaa`.

[closeout-c1-candidate.sha256](closeout-c1-candidate.sha256) is part of this approval candidate. Its exact byte SHA256 is `32affe791ca9c75523ec5780a46f7cfe30e8179f2d77e66eaff63d147003ca29`. It pins forty-two files: all thirty-four root Python scripts, the guide, framework configuration, two baseline test modules, their disk_tmp helper, and three C2/profile preservation test files. The latter preservation files are not additional test lanes. In particular, the manifest includes the untracked C2 ordering test and all C2 source changes.

Capture occurred through file fingerprinting only; no tests or candidate-module imports ran. Before implementation execution and again before the campaign, reject changed file content, missing/extra root Python scripts, changed HEAD/branch or changed protected-file inventory. Do not regenerate these approval pins to accommodate drift. Record the actual interpreter/Git paths, versions and executable hashes at campaign start; unavailable runtime identity prevents credit. New local operator/test files get their own frozen hashes after implementation and pre-run review, before any product baseline starts.

## Proposed approach

Create a standard-library-only operator at **new** `docs/assurance/validate-closeout-c1.py` and focused synthetic tests at **new** `docs/assurance/test_closeout_c1_operator.py`. Keep the executable campaign, private worker mode and result verification in that operator; no reusable framework extension is needed.

The invoking process reads candidate inputs and creates one isolated disk-backed run directory. Copy only the pinned execution inputs into disposable baseline/mutant roots, with fresh fixture Git metadata and no live Git scratch/state. Do not copy or follow the invoking `.git` link. Provide test-module and scripts paths from the copy. Isolate HOME, XDG_CACHE_HOME, TMPDIR, TMP and TEMP; disable bytecode writes; clear inherited GIT_* overrides, _AGENTIC_REVIEW_PRODUCER, _AGENTIC_LIFECYCLE_RUN_ROOTS, OKF_AUTONOMOUS and lifecycle bypass overrides. Parent lifecycle administration remains in the authorized invoking checkout; fixture execution never uses its active task or producer lease.

Derive the thirty exact method IDs from static ASTs of the pinned unchanged tests, restricted to the fixed eleven-class roster. Freeze those IDs in the evidence manifest before importing tests. One private worker per baseline class loads only that class; one worker per mutant loads exactly its selected method. Record the loaded leaf IDs before execution and all started/finished IDs during execution, rejecting loader placeholders and roster/count mismatches.

Use a custom unittest result to retain failures, errors, skips, unexpected successes, raw traceback text, exception type and traceback frame filename/function/line. For each mutant require exactly one executed test, exactly one failure from AssertionError, zero errors/skips/unexpected successes, and the original assertion frame listed below. Verify that the pinned test bytes are unchanged and that the failure's value/message matches the stated behavior; a different assertion in the same method is insufficient. Capture only explicitly whitelisted assertion locals when necessary, such as N01's rid/status or N08's listed IDs; do not serialize arbitrary frame locals or inherited environment. Record both raw worker exit and structured result; the expected mutant-failure exit is distinguished from operator failure.

Start each test worker in its own process group, with a monotonic deadline equal to the smaller of 180 seconds and the remaining global budget. On timeout/failure, terminate and reap its children before restoring the copy. The twenty-minute budget includes the campaign's operator controls and cleanup; stop starting work with insufficient cleanup time. Failure to finish cleanup within the budget is a failed campaign, never a successful overrun.

Every mutated copy starts from the same verified candidate bytes. Check the exact one-occurrence edit within its named function/section; save original bytes, compute before/expected-after/applied hashes and a minimal diff; verify only the authorized file changed. Restore bytes in a finally path, read-confirm the original hash, then dispose. A failed restore or cleanup must override a provisional successful kill. Keep diagnostic artifacts outside the disposable copy so cleanup cannot erase them.

Write append-only per-process stdout/stderr/result artifacts and a final JSON/Markdown report under **new** `docs/assurance/closeout-c1-validation-results/`. A completed mechanical outcome must say that independent evidence review is still pending. The operator never writes a C1-closed status itself.

After a successful first execution, later invocations of the unchanged acceptance command verify the same spec/plan/operator/test/input/runtime identity, the complete raw artifact hashes, exact row set, counts, intended failures and successful restoration. They emit explicit REUSE with the original campaign identity, not a new execution claim. Failed, partial, missing, tampered or stale evidence yields nonzero; it never starts another campaign automatically. Refuse concurrent campaigns and preserve failure artifacts. This is local evidence-integrity checking, not authentication of untrusted authors.

## Exact mutation edits and failure locations

All snippets below are literal single-occurrence replacements within the named scope of the pinned input, never edits to invoking files. The source pins plus these replacements define the expected mutated bytes; calculate and record the corresponding whole-file after-hash before running the worker. If a scope/snippet does not match exactly once, stop without substitution. Test line numbers are one-based in the pinned unchanged test modules; structured traceback attribution verifies them.

| ID | Copied file and scope | Exact old text | Exact replacement text | Required target assertion |
| --- | --- | --- | --- | --- |
| N01 | assurance.py::_parse | `if kind in found:` | `if kind in found and kind != 'Verify':` | test_assurance.py:119, CALC-R3 expected INVALID |
| N02 | assurance.py::evaluate | `return result(obligation, 'UNDECLARED', 'no Verify: line')` | `return result(obligation, 'UNVERIFIED', 'no Verify: line')` | test_assurance.py:133, code expected 0 |
| N03 | lifecycle.py::assure_run | `f"req:{obligation.id}"` | `f"req:BROKEN-{obligation.id}"` | test_assurance.py:150, stdout must contain req:CALC-R1 |
| N04 | assurance.py::evaluate, fresh passing result statement | `'VERIFIED', f'passed on {scope}; covers only this command on these inputs'` | `'UNVERIFIED', f'passed on {scope}; covers only this command on these inputs'` | test_assurance.py:187, fresh status expected VERIFIED |
| N05 | ledger.py::_entry_verdict | `if entry.get('runtime_sha256') and runtime_digest(entry['argv']) != entry['runtime_sha256']:` | `if False and entry.get('runtime_sha256') and runtime_digest(entry['argv']) != entry['runtime_sha256']:` | test_assurance.py:240, executable edit status expected STALE |
| N06 | assurance.py::evidence.add | `if problems:` | `if False and problems:` | test_assurance.py:258, invalid-record status expected UNVERIFIED |
| N07 | ledger.py::_entry_verdict, no-input branch | `return False, f"{name} declared no --inputs and the working tree changed since it ran (declare --inputs to reuse across edits)"` | `return True, f"{name} declared no --inputs and the working tree changed since it ran (declare --inputs to reuse across edits)"` | test_assurance.py:285, committed edit status expected STALE |
| N08 | assurance.py::selected | `chosen = not negative` | `chosen = True` | test_assurance.py:312, first exact listed-ID set excludes CALC-R4 |
| N09 | assurance.py module constant | `SCHEMA_VERSION = 1` | `SCHEMA_VERSION = 2` | test_assurance.py:336, schema_version expected 1 |
| N10 | assurance.py::exit_code | `failing = FAILING + (('UNDECLARED',) if strict else ())` | `failing = FAILING` | test_assurance.py:391, strict report exit expected 1 |
| N11 | .ai/lifecycle.md, Recording table | `\| Assurance \|` (literal pipes, without backslashes) | `\| Assurance-broken \|` (literal pipes, without backslashes) | test_lifecycle_conformance.py:267, Recording table row assertRegex |

N01–N11 use the exact classes and selected method names in the approved spec matrix. Baseline class method counts, in that order, are 1, 3, 4, 7, 1, 2, 3, 2, 2, 4, 1. N11 preserves the Assurance status section and every profile term; it tests only the original R10 table-row assertion. N04 preserves C2 ordering and changes only the original status result. No weaker test or alternate mutant is an automatic fallback.

## Boundaries and invariants

- No tracked source/test/guide/config changes, fixture assertion changes, dependency additions or public contract changes. All implementation artifacts are local ignored files under docs/assurance.
- Preserve C2's five modified tracked files and untracked ordering test, plus its existing reports/receipts. No staging, commit, push, PR, merge, branch/worktree creation, fetch or base refresh.
- Keep 5o unapproved, the fourteen-profile catalog unchanged and all profile work paused. Hashing preservation inputs does not authorize profile execution.
- Do not copy live lifecycle evidence into fixtures, mutate historical receipts, create knowledge/, rescore historical evidence or claim a historical replay.
- Observe the approved maximum: eleven baseline-class processes plus eleven mutant-method processes; four small operator rejection controls are synthetic. No automatic retries or second campaign after failure or drift.
- Verify invoking candidate hashes before and after every row and at finalization; isolate all fixture write roots and refuse path escapes/symlinks during copy/output creation. Preserve Git status and protected inventory alongside hashes. Do not claim monitoring of unrelated filesystem activity or cryptographic authenticity.

## Implementation steps

### Step 1: Frozen input and roster contract — R1, R2, R5

Files: new operator and synthetic test file; existing manifest/spec are read-only inputs. Write synthetic fixture tests first for mismatched pins, missing/duplicate class IDs, missing method and unexpected root script. Implement strict manifest parsing, static AST roster extraction, path containment and copy verification. These checks operate on tiny synthetic fixture trees, not product test imports. A deliberate broken variant of the checker must fail these assertions; retain its RED then correct GREEN evidence. Verify that the fixed spec matrix resolves to exactly eleven classes/thirty methods without executing those tests.

### Step 2: Evidence rejection and restoration contract — R3, R4, R5

Files: new operator/test file only. Write the four required rejection controls first: (1) an actual empty unittest suite; (2) an unchanged/no-op mutation; (3) unrelated assertion and loader/error outcomes that lack the designated frame; (4) failed restoration/readback after a provisional kill. Use synthetic proof fixtures, not additional assurance invocations. Add exact-map, artifact-integrity and cleanup-result assertions in the same focused suite. Demonstrate that disabling each rejection causes its test to fail, then restore the operator and pass. No import error or absent implementation alone counts as meaningful RED evidence.

### Step 3: Bounded isolated worker and campaign — R1, R2, R3, R5

Files: new operator/test file only. Implement private structured worker mode, exact selection, process-group timeouts, isolated environment, fixed mutation table and restoration in finally. Exercise child timeout/cleanup and result attribution on tiny synthetic fixtures first. Then connect the eleven baseline/mutant pairs without running them. Freeze operator/test hashes and write a campaign-ready manifest. Independent pre-run review must check the approved source/test pins, all eleven edits/oracles, isolation and deadlines. Any unresolved issue blocks the evidence campaign.

### Step 4: Single campaign and immutable reuse — R1, R2, R3, R4, R5, R6

Files: new operator and results directory. Implement strict first-run versus evidence-reuse behavior; test its successful/failed/partial/drift/tamper paths with synthetic artifacts first. Following pre-run review, run the approved acceptance command through convergence once, using a 1260-second outer timeout so the operator's stricter twenty-minute deadline controls execution and cleanup. First invocation performs the four operator rejection controls and at most twenty-two product workers; subsequent identical acceptance invocations only verify/reuse that same complete successful evidence. On any unexpected result stop, preserve diagnostics and keep C1 open. Do not fix product code or silently change a mutant.

### Step 5: Independent evidence review and qualified closeout — R6, R1, R4, R5

Files: new implementation/review report; existing closeout-c1-reconciliation.md updated only after evidence review. An independent reviewer checks all raw results, actual method counts, exact mutation diffs, failure frames, hashes, restoration and reuse attribution; review both spec compliance and quality. An Approved verdict with no outstanding required finding is necessary before changing C1's remaining-item status. Preserve the historical omission as a historical fact. Report other initiative closeout items separately without declaring C5/C6 complete.

Close the retrospective before Verify, recording either a concrete observed lesson or no-new-lessons with a reason. Use framework scratch lifecycle receipts and the existing docs locations; the final report states exact commands/outcomes and the uncommitted disposition. Do not record Verify or completion on partial evidence.

## Testing strategy

The operator's pure logic receives focused test-first verification with synthetic inputs. The four operator rejection controls are separate from the eleven original class proofs. They do not replace the campaign or add product-suite invocations. The campaign itself is the narrow E2E: unchanged original tests drive copied real lifecycle/assurance code and detect the specified regressions. Count baselines, expected mutant failures and invalid-proof rejection separately.

Use a deliberately broken checker variant to demonstrate non-vacuous focused assertions, then restore it. Respect lifecycle red/green requirements for newly implemented logic; use identical focused command labels and record both outcomes. These implementation checks are future work after plan approval. No test has run during planning.

No full-framework or profile suite is required for ignored local operator/docs changes with immutable framework inputs. Reuse C2's already recorded full gate only within its stated original scope; it does not prove C1's missing controls. If a later proposed fix would change tracked framework code or widen dependencies, stop and seek approval of the changed scope and its applicable gate before proceeding.

## Validation commands

All commands use the designated invoking directory. Commands naming new files are **proposed**, not currently runnable evidence. Record each actual future check through the lifecycle ledger; consult `lifecycle.py reuse` before repeating it.

1. Existing static planning checks: `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-closeout-c1-validation.md` and `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-closeout-c1-validation.md --plan docs/assurance/plan-closeout-c1-validation.md`. They run no acceptance tests.
2. New focused operator suite, after approval: `python3 -m unittest discover -s docs/assurance -p test_closeout_c1_operator.py`. Keep all product imports/campaign launches behind explicit operator entry points, so test discovery cannot run them. Use this command for meaningful RED/GREEN and synthetic success/failure/timeout paths.
3. Approved acceptance surface: `python3 docs/assurance/validate-closeout-c1.py`. Launch the single campaign through `python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-closeout-c1-validation.md --timeout 1260`; do not run the operator separately first. Converge records all six requirement results; explicit evidence reuse prevents repeated product execution. Supervise the long check with the existing background/wait_check mechanism, not polling or a duplicate launch.
4. Future administrative sign-off: requirement trace, independent review, retrospective, diff/pin checks and framework lifecycle audit/Verify. `okf.py affected` is INAPPLICABLE here because this is a framework checkout with no knowledge bundle; never initialize one or report this diagnostic as PASS. No `okf.py records` bundle claim is made.

## OKF impact

Framework mode is confirmed by repo.py context. `okf.py affected` for the proposed operator/test/reconciliation paths exits 1 because no bundle exists; that is recorded as INAPPLICABLE, not a passed validation. Persistent scope/evidence stays in docs/assurance and lifecycle Git scratch. After successful independent review, amend the current C1 reconciliation status with a pointer to new current-candidate proof; do not rewrite original area1/4/6 receipt facts or immutable historical documents. Append the outcome to the new implementation report rather than inventing knowledge/log.md.

## Risks and mitigations

- A mutant could fail for another reason: require the exact pinned assertion frame and semantic mismatch, not nonzero exit or substring alone.
- Current baselines could expose a real failure: stop and report it, preserving the proof gap and all source bytes; repair is outside this plan.
- Temporary-storage fallback or inherited Git context could touch live state: set isolated disk-backed HOME/cache/temp and clear live Git/lifecycle context before test imports.
- Six acceptance bullets could exceed the run limit: first-run locking and complete evidence revalidation permit one campaign only; failed or changed evidence cannot auto-relaunch.
- A timeout or restore problem could be hidden by a successful assertion failure: cleanup failure overrides provisional success and is covered by its dedicated rejection control.

## Out of scope

Profile execution/expansion, 5o approval, changes to C2 or framework behavior, native/model/session/trust work, historical rescoring, exhaustive mutation coverage, automatic product repair, unrelated suite reruns and delivery actions.

## Open decisions

None affecting implementation. This plan is ready for human approval. Plan stage remains unrecorded until that approval; C1 remains open and no code or validation campaign has been run.
