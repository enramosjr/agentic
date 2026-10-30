# Implementation Plan: static installer-documentation input profile

Approved by human:enramosjr in this chat on 2026-10-29 America/Chicago: “Approved. Proceed with implementing 5e according to the plan, including the required tests, independent review and verification.” Based on approved specification-5e.md, R1-R6 and recommended D1-D4. L2; planner role; Python principal engineer. A read-only planner investigated and returned the plan for parent persistence. Implementation is authorized; delivery actions remain excluded. No product tests ran during planning.

## Objective

Add `python-installer-doc-contract` for exactly `python3 .ai/scripts/tests/test_lifecycle_conformance.py Distribution.test_readme_and_playbook_document_the_installer`. Use the existing literal exporter and explicit adoption to verify bounded repository-file freshness for documentation-token and VERSION-regex checks while preserving all four delivered profiles.

## Success criteria

- R1: Only approved argv gains the new ID; four prior profiles retain identity, ordered scope, rationales and behavior.
- R2: Seven approved ordered patterns have accurate rationale and independent source coverage; confirmed reachable dependency additions require review.
- R3: Public exports, supplements, validation, refusal, immutability and nonexecution preserve their contracts.
- R4: Documentation accurately describes advisory/manual adoption and static/runtime limits; inference, suites, matching, schemas and gates remain unchanged.
- R5: Framework fixtures independently prove one actual passing test, byte stability, every required REUSE/RERUN outcome and seven intended static failures.
- R6: An ordinary adopter proves required VERIFIED/STALE/UNVERIFIED states, identity and receipt behavior; five confirmed broken variants fail their intended assertions.

## Current state

`assurance_inputs.py:17-88` defines four literal profiles. `suggest` matches exact argv and validates repository paths without executing tests or validating document contents.

`test_lifecycle_conformance.py:60-65` reads `.ai/README.md`, `.ai/docs/install-and-upgrade.md` and `.ai/VERSION` through `text(path)`. It checks the installer-path token within Quick start, five playbook terms and the literal Python regex `r"^\d+\.\d+\.\d+\n$"`. The sibling method has broader inventory/copy behavior and remains unselected.

The selected module eagerly imports disk_tmp and lifecycle. disk_tmp calls scratch.require_disk; lifecycle imports scratch/review_guard, whose eager imports include ledger, sets up lazy modules and constructs protected decorators. The selected method accesses no lifecycle attributes or protected producers. Ambient temporary-storage/mount effects remain outside the repository-file claim.

`test_assurance_inputs.py:34-121` provides disposable Git fixtures, bounded subprocesses and public exporter/lifecycle helpers. `ReviewerReportFixture:1017-1087` offers analogous count/snapshot/restoration mechanics but hard-codes REPORT declarations; its preservation helper explicitly compares only the three profiles preceding reviewer-report.

`report_setup_digest:993-1014` retains initialization, classes, signatures/decorators and called text/require_disk/lazy/protected bodies. This matches the inspected shared setup path and may be reused unchanged; old hashes and selected-method assumptions do not independently verify the new profile. `.ai/lifecycle.md:210-230` contains the profile guide. Planner's bounded configuration inventory found no pyproject/setup/tox/nox or GitHub workflow configuration; existing scripts specify stdlib Python 3.9+ and unittest.

## Proposed approach

Change exactly three existing tracked files:

1. `.ai/scripts/assurance_inputs.py`: append one literal profile and seven rationales.
2. `.ai/scripts/tests/test_assurance_inputs.py`: add independent declarations, InstallerDocFixture and the eight acceptance classes named in the spec, before unittest.main.
3. `.ai/lifecycle.md`: append profile documentation within the existing subsection.

Derive InstallerDocFixture directly from Fixture. Reuse pure mechanisms without modifying prior fixtures/tests. Copy target/helper, three direct text inputs and compatibility-only inputs needed to export all four prior profiles. Fixture preparation copies are infrastructure, not selected-method behavior. No exporter algorithm, target-test, installer, matching, schema, persistence or gate change is needed. New local reports remain ignored under docs/assurance.

## Boundaries and invariants

Every repository command uses explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Retain branch `claude/assurance-increment-7` and delivered HEAD `bd34de90f4eb84c5be19d306418404e61a6985e5`. No fetch/base refresh, switch, reset or new worktree. These explicit restrictions supersede default validation-policy base-refresh advice.

One implementer owns all three tracked files and fixture code; no parallel mutation lanes. Independent review is ordinary read-only review. Preserve all four old entries, inference/full suites, ordered declaration/exact command identity, schemas, gates and producer receipt exclusion. The invoking framework never acquires knowledge. Only the isolated ordinary-adopter fixture initializes its own bundle.

Restore fixture bytes in cleanup/finally. VERSION freshness edits use another matching value such as `0.1.1\n`; generic whitespace appending is unsuitable. Format failure is separate. No native/model/session/trust action, historical rescoring/evidence modification or autonomy driver. Preserve historical source/runtime scopes. Finish verified and uncommitted; no commit/push/PR/merge is authorized.

## Implementation steps

### Step 1: Exact registration and public export fail closed before catalog addition

**R1, R3; files:** input-test module, then exporter PROFILES.

Write independent INSTALLER_DOC_COMMAND, test/helper/direct-input lists, ordered patterns and production boundary expectations. Add InstallerDocFixture, InstallerDocProfileTests and InstallerDocExportTests first. Cover exact ID/argv/root and refusal of class/module, sibling method, discovery, extra option, alias and alternate interpreter. Compare all four prior profile dictionaries to literal catalog data from delivered HEAD and compare their public identity/inputs/rationales; inherited preservation alone omits reviewer-report.

Exercise text/JSON parity, Inputs parsing, lifecycle-token parity, positive supplement order and every required-literal/path/inventory refusal. Poison target/helper bodies only for nonexecution proof, preserving exporter dependencies. Existing nonconforming README/playbook/VERSION must export successfully. Snapshot files/evidence around export.

Record RED for `python3 .ai/scripts/tests/test_assurance_inputs.py InstallerDocProfileTests InstallerDocExportTests`, requiring absent-profile failures rather than fixture/import errors. Append only the approved literal entry and seven rationales; record GREEN with the identical command. Leave old entries/functions unchanged.

### Step 2: Reviewed dependency scope rejects reachable additions

**R2; file:** input-test module; InstallerDocDependencyTests.

Assert seven-pattern order/rationales. Use real ledger.input_paths to include independently identified direct inputs/setup files, a future supported script and non-Python production descendant; exclude unrelated tests/documents and compatibility-only documents. Reuse report_setup_digest unchanged because the actual called/setup path was inspected. Store independently justified expected setup pins for selected module, disk_tmp, scratch, lifecycle, review_guard and ledger. Add a fixed selected Distribution-method hash and source-derived direct-read assertions. Never derive expectations from the catalog at test runtime.

Confirm 13 reachable variants justified by this closure: six module-initialization reads (selected module, disk_tmp, scratch, lifecycle, review_guard, ledger); one read each in selected method, text, require_disk, lazy, outer protected and nested decorate; and a selected-module import of a new excluded test helper reading excluded data.

Insert body additions after docstrings and before early returns; insert module additions at reachable initialization positions before unittest exits. Confirm changed bytes and excluded ledger membership. Execute the exact command with each addition to establish reachable static conformance, then require the nested dependency acceptance to fail specifically on method/setup-boundary review without unrelated errors. Do not label wrapped producer-body additions reachable: this path constructs wrappers without calling them. The conservative protected fingerprint still retains that body. Review-only pins and confirmed execution controls remain distinct.

Check: `python3 .ai/scripts/tests/test_assurance_inputs.py InstallerDocDependencyTests`. Confirmed broken variants establish sensitivity of later-written boundary checks. Pins are review guards, not general read discovery.

### Step 3: Documentation preserves explicit advisory adoption

**R1, R4; files:** input-test module and lifecycle guide.

Add InstallerDocCompatibilityTests before guide prose. Check all four prior profiles, unchanged inference/full-suite refusal and existing matching/schema/gate/receipt mechanisms. Document exact command/ID, seven ordered patterns, three direct text reads including VERSION, conservative invalidation, manual adoption, path-only nonexecuting export and runtime/read-completeness limits. State tokens/actual regex accurately; exclude installer/upgrade success, real drift/conflicts, hooks/trust, semantic-version compatibility and native/model/session claims.

Check: `python3 .ai/scripts/tests/test_assurance_inputs.py InstallerDocCompatibilityTests`. Prose is test-first exempt; a missing-documentation RED/GREEN is useful evidence. Finish guide edits before final convergence.

### Step 4: Framework execution and seven static failures are observable

**R3, R5; file:** input-test module; InstallerDocFrameworkEndToEndTests and InstallerDocFailureTests.

Capture direct execution: require one unambiguous unittest count, exactly one test, then expected exit/output. Success requires OK; failure requires the selected method's intended assertion, not import/setup failure. Assert selected membership and bytes stay unchanged. Drive public export and real lifecycle run/reuse; compare recorded argv, ordered inputs and exit to export.

Require REUSE unchanged and after separate unrelated test/document changes. Require nonzero RERUN after each direct input, target, helper, representative production import and new supported non-test script edit. Restore each edit and require REUSE. For every direct-input freshness edit prove one passing selected test. Assert no framework knowledge directory.

Seven independent static failures remove the Quick start installer-path token, remove each of five playbook terms globally in separate fixtures, or replace VERSION with nonmatching text. Confirm bytes, successful path-only export and exactly one actual failure on the intended criterion.

Check: `python3 .ai/scripts/tests/test_assurance_inputs.py InstallerDocFrameworkEndToEndTests InstallerDocFailureTests`.

### Step 5: Adopter states and five controls reject false evidence

**R1, R4, R6; file:** input-test module; InstallerDocAdopterEndToEndTests and InstallerDocControlTests.

In a separate ordinary adopter explicitly adopt public export. Assert initial UNVERIFIED, independent one-test preflight, real assure --run, unchanged selected bytes and VERIFIED. Unrelated edits preserve VERIFIED. Each direct input, target/helper, representative production import and new supported script yields STALE; restoration restores VERIFIED. Reordered Inputs or changed argv yields UNVERIFIED. Assert appropriate nonzero exits for these STALE/UNVERIFIED cases. Confirm actual producer receipt exclusion and receipt-only additions preserving VERIFIED.

Five disposable controls omit each direct input plus its rationale, loosen matching, or substitute an actual empty suite ignoring the selector. Omission export must actually lack the input; narrow framework freshness acceptance must fail on missed invalidation while conformance-preserving edits still pass the selected command. Loose matching must fail variant refusal. Empty-suite output must independently confirm Ran 0 tests; acceptance must fail on count before Python exit interpretation. A missing method producing one loader _FailedTest is insufficient. Confirm mutation bytes, exactly one nested acceptance execution, intended failure and no errors; never recurse into controls.

Check: `python3 .ai/scripts/tests/test_assurance_inputs.py InstallerDocAdopterEndToEndTests InstallerDocControlTests`.

### Step 6: Review and verify the frozen candidate

**R1, R2, R3, R4, R5, R6; files:** three tracked files plus ignored new-slice evidence.

Handle affected paths, finish code/tests/guide, trace requirements and run whitespace/static checks. Run the six approved commands through convergence once on the completed candidate; require 6 PASS / 0 FAIL / 0 MANUAL. Before long execution record criteria/input scope and why no covering fifth-profile PASS exists. Before repeats run lifecycle reuse; never repeat REUSE or unchanged failing checks. Repair narrowly and refresh invalidated evidence only.

Close/report retrospective. Obtain independent two-pass review against approved spec/plan and canonical report contract; preserve returned Markdown unchanged. Resolve blockers and re-review repairs. After review freeze on the existing authorized base and run the full framework suite once, supervised by background/wait-check or subagent. Record exact source/runtime scope and outcome without inferring counts from suppressed output. Record Review/Verify only after exit conditions hold. Stop verified/uncommitted.

## Testing strategy

Use public interfaces, real fixture inventory, bounded subprocesses, byte snapshots/restoration and count-before-exit. RED/GREEN establishes absent-profile sensitivity. Confirmed mutations establish sensitivity of later-written boundary/freshness/matching/count checks. Parameterize variant families rather than add lanes. Static failures prove only text/regex assertions. Retain disk-backed scratch/environment isolation and separate fixture tasks when timestamp precision could select old receipts.

Python persona materially informed import-time effects, called-body coverage, subprocess bounds, Python 3.9 compatibility and precise regex/count claims. No separate product baseline run is necessary before implementing; no product command runs before plan approval.

## Validation commands

Future implementation checks only. Record focused checks with lifecycle run/redgreen. The six spec acceptance commands and eight future class names remain unchanged; convergence supplies their evidence without duplicate E2Es.

```text
python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5e.md --plan docs/assurance/plan-5e.md --tests .ai/scripts/tests/test_assurance_inputs.py
python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-5e.md
python3 .ai/scripts/lifecycle.py run inputs-5e-diff -- git diff --check
python3 .ai/scripts/lifecycle.py run inputs-5e-scan -- python3 .ai/scripts/lifecycle.py scan-diff
python3 .ai/scripts/lifecycle.py run inputs-5e-framework -- python3 .ai/scripts/run_tests.py -j 8
python3 .ai/scripts/lifecycle.py audit
```

Full regression runs once after review/freeze. Before repeats use `python3 .ai/scripts/lifecycle.py reuse LABEL_OR_CMD`. Reload applicable validation-policy sections before Gate 4/long checks. Inspect wait_check.py help before background launch; delegate long waiting, avoid short model polling and respect host tool-call limits. No real-agent lifecycle evaluation is needed because tier/stage rules remain unchanged.

## OKF impact

Planning affected on the three tracked paths exited 1: no bundle exists. Framework OKF synchronization is INAPPLICABLE, not records PASS. Never initialize knowledge or invent capability/log evidence. Synchronize the existing guide and retain ignored local spec/plan/implementation/convergence/review artifacts, preserving 5d records.

## Risks and mitigations

- VERSION whitespace failure masks freshness: use another matching version and separate format failure.
- Positive sentinels miss new reads: independent reviewed setup/method pins and confirmed reachable additions.
- Dead code mislabeled reachable: trace/execute each variant and exclude protected producer bodies from runtime claims.
- Preservation misses reviewer-report: compare/export all four prior entries explicitly.
- Catalog-derived oracle hides omissions: independent source expectations and three omission controls.
- Loader failure masks zero execution: actual empty suite and count-before-exit rejection.
- Historical/runtime evidence inflation: exact original scopes and newly established fifth-profile evidence.

## Out of scope

Target-test/installer/document contracts; full Distribution registration; exporter/lifecycle/ledger algorithms; minimum-scope discovery; reduced gates; automated adoption; native/model/session/trust actions; historical changes; base refresh/new worktrees; invoking-framework knowledge; commit/push/PR/merge.

## Open decisions

None. Approved D1-D4 settle behavior. The user separately approved this plan; record Plan and proceed with implementation.

## Planning validation

Approved spec analyze/trace exited 0; six requirements traced. Intent recorded with --approved-by human:enramosjr from the user's explicit approval. Lifecycle audit exited 0 for active record 20261029T162830Z-claude_assurance-increment-7.json. `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5e.md --plan docs/assurance/plan-5e.md` exited 0, all six requirements traced into this plan. Both spec/plan paths are ignored. Local repository context remains clean on the delivered HEAD/branch; no remote verification. Planning checks validate structure only, not implementation. Plan approval/registration remains pending.
