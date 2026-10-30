# Implementation Plan: static reviewer-report contract input profile

Approved by human:enramosjr in this chat, 2026-10-29 America/Chicago: “approved”, responding to the separate plan approval request. Based on approved specification-5d.md, R1-R6 and D1-D4. L2; planner role; Python principal engineer. A read-only planner investigated and returned this plan for parent persistence. Implementation is authorized; delivery actions remain excluded.

## Objective

Add `python-reviewer-report-contract` for exactly `python3 .ai/scripts/tests/test_lifecycle_conformance.py RolesAndSkills.test_reviewer_completion_report_contract`, using the existing literal exporter and explicit adoption. Establish controlled repository-file freshness for static instruction consistency while preserving all three delivered profiles.

## Success criteria

- R1: Only approved argv gains the ID; all three prior entries and exports retain identity, ordered scope, rationales and behavior.
- R2: Exactly nine approved ordered patterns have accurate rationale and independent source-derived coverage.
- R3: Public export, supplements, refusal, validation, immutability and nonexecution remain intact.
- R4: Documentation accurately states manual/advisory adoption and static/runtime limits; inference, suites, matching, schemas and gates remain unchanged.
- R5: Framework fixtures prove actual one-test execution, byte stability, every specified REUSE/RERUN outcome and five deliberate document-contract failures.
- R6: An ordinary adopter proves VERIFIED/STALE/UNVERIFIED states and receipt behavior; seven confirmed variants fail their intended assertions.

## Current state

`assurance_inputs.py:17-62` contains runner, architecture compatibility and harness wiring profiles. `suggest` matches exact argv; the exporter validates paths, without running tests or parsing document semantics.

`test_lifecycle_conformance.py:69-91` reads the five approved documents, extracts documented command text with regex/shlex and checks section/report/preservation text. It executes no extracted commands and performs no structural TOML parsing. Its eager imports, lazy setup and ambient storage effects are documented in the approved spec.

`test_assurance_inputs.py:34-121` provides bounded disposable Git fixtures and public export/lifecycle helpers. `HarnessWiringFixture:633-680` demonstrates snapshots, count-before-exit and edit/restore. Existing wiring profile preservation at 700-718 compares only runner and architecture, so new checks must explicitly add wiring. Framework/adopter flows at 820-922 and confirmed controls at 925-970 supply analogous mechanisms, not the new dependency assumptions.

`.ai/lifecycle.md:210-226` is the profile guide subsection and also a direct selected input. Finish guide edits before final byte-stable preflight. Planner bounded inventory found no Python project configuration or GitHub workflow; repository scripts use stdlib Python 3.9+ and unittest, with run_tests.py providing the full runner.

## Proposed approach

Change exactly three existing tracked files:

1. `.ai/scripts/assurance_inputs.py`: append one literal profile with nine rationales.
2. `.ai/scripts/tests/test_assurance_inputs.py`: add handwritten declarations, a new fixture and the eight acceptance classes named in the spec.
3. `.ai/lifecycle.md`: append profile documentation within the existing subsection.

Derive `ReviewerReportFixture` from existing `Fixture`. Reuse wiring mechanics without its JSON-specific assumptions. Copy the selected module/helper and five actual documents. Include prior-profile fixture inputs only to support compatibility; their presence does not make them inputs of this profile. Preserve existing tests rather than refactoring them.

No exporter algorithm, inference, matching, schema, persistence, gate or target-test change is needed. Ignored local reports remain under docs/assurance.

## Boundaries and invariants

Every repository command uses explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Retain branch `claude/assurance-increment-7` and base HEAD `652a77b811cb8ac0584940a990d6f266bb4acefd`. No base refresh, branch change, reset or worktree. Explicit restrictions supersede the validation policy's default fetch/merge advice.

One implementer owns all three tracked files and fixtures; no parallel mutation lanes. Independent review is ordinary read-only review. Do not edit selected conformance tests, role registrations, canonical reviewer role, review skill, hooks or underlying exporter/lifecycle/assurance/ledger algorithms.

Preserve exact command/ordered declaration identity and producer receipt exclusions. Framework fixtures remain framework; only disposable ordinary adopters initialize their own knowledge bundles. The invoking framework never creates knowledge.

Freshness edits append conformance-preserving whitespace outside asserted blocks and restore bytes in finally. Intentional document failures are separate. Runtime/executable/environment, storage/mount state, ignored files and external mutable data stay outside repository-file claims. No native/model/session/trust actions, historical rescoring or mechanically bound native capture. Preserve historical source/runtime scopes. Finish verified and uncommitted; no commit/push/PR/merge.

## Implementation steps

### Step 1: Exact registration and reviewed scope fail closed before catalog addition

**R1-R3; files:** input-test module, then exporter PROFILES.

Handwrite command, patterns, five documents, test/helper and eager-import/lazy-setup oracle independently of PROFILES. Add ReviewerReportFixture and ReviewerReportProfileTests, ReviewerReportDependencyTests and ReviewerReportExportTests first.

Cover exact ID/argv/root; reject broader class/module/method, discovery, option, alias and interpreter variants. Compare all three prior entries with committed-HEAD literal catalog data and their public exports. Assert nine-pattern order and accurate rationale; actual ledger selection covers independent reads/setup, excludes unrelated tests/documents and includes future scripts/non-test descendants. Boundary-drift checks inspect the selected method rather than inheriting full-class reads.

Exercise public text/JSON/Inputs/lifecycle-token parity, positive supplements, source/evidence snapshots and target/helper nonexecution sentinels without poisoning exporter dependencies. Refuse every missing literal, ignored/unsafe boundary or unsupported command without candidate fields. Existing nonconforming documents must still export successfully.

Record RED for `python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportProfileTests ReviewerReportDependencyTests ReviewerReportExportTests` through lifecycle redgreen. Confirm absent-profile failures rather than broken setup. Append only the approved literal profile and rationales, then record GREEN with the identical command. Existing entries/functions stay unchanged.

### Step 2: Documentation preserves the advisory contract

**R1, R4; files:** input-test module and lifecycle guide.

Write ReviewerReportCompatibilityTests before guide prose. Check all prior profiles, full-suite refusal/broad inference, command/declaration matching and receipt behavior through existing mechanisms. Document exact command/ID, five direct reads, ordered exclusion/restoration, conservative eager-import/lazy-setup scope and extra invalidation, explicit manual adoption, path-only nonexecuting export and static/runtime limitations. Exclude actual review/report production, model/native independence, hooks and authentication claims. Preserve Stage 3 instructions and existing profiles/gates.

Check: `python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportCompatibilityTests`. Guide prose is test-first exempt; focused missing-documentation RED/GREEN is useful evidence. Final preflight uses the edited guide.

### Step 3: Framework execution and freshness are independently observable

**R2, R3, R5; file:** input-test module; ReviewerReportFrameworkEndToEndTests and ReviewerReportFailureTests.

Capture actual direct unittest output; require exactly one executed test before interpreting exit, then success and unchanged selected membership/bytes. Subtests do not increase the test count. Drive public export and real lifecycle run/reuse; compare ledger argv, ordered inputs and exit with export.

Require REUSE unchanged and after separate unrelated test/document edits. Require nonzero RERUN after each direct document, target, helper, representative eager production import and new supported production script edit. Restore each mutation and require REUSE again. For every direct-document freshness edit, independently prove the selected command still runs exactly one passing test. Assert no framework knowledge bundle.

Five separate intentional failures remove Completion report loading from each registration, alter one canonical reviewer heading, remove one required lifecycle preservation phrase and remove one required review-skill phrase. Confirm bytes; path-only export still succeeds; actual selected execution runs one test and fails nonzero with the intended assertion, not setup/import failure. Preserve byte stability and restore originals.

Check: `python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportFrameworkEndToEndTests ReviewerReportFailureTests`. Later-written test logic must show sensitivity against confirmed broken variants in Step 4, rather than relying on a passing postimplementation test alone.

### Step 4: Adopter states and seven controls reject false evidence

**R1, R4, R6; file:** input-test module; ReviewerReportAdopterEndToEndTests and ReviewerReportControlTests.

In a separate ordinary-adopter fixture only, initialize its bundle and explicitly publish the public exported declaration. Assert initial UNVERIFIED; independent one-test proof; actual assurance execution; VERIFIED and stable selected bytes. Separate unrelated edits preserve VERIFIED; each selected input/addition yields STALE; restoration restores VERIFIED. Unmatched reordered Inputs or command identity yields UNVERIFIED. Check actual receipt exclusion and receipt-only changes. Preserve assure exit semantics: zero for VERIFIED, nonzero for tested STALE/UNVERIFIED.

Implement seven isolated controls: omit each of five documents plus matching rationale; loosen exact argv matching; substitute actual zero-test execution. Confirm mutation bytes before the pertinent acceptance method. Omission export must actually lack the document, then the narrow framework freshness test must fail for missed invalidation while the conformance-preserving edit leaves the selected command passing. Loose matching must fail variant rejection. Nested tests run once, fail on intended criteria and contain no unrelated errors; never recurse into controls.

For zero tests, do not copy the old empty-module mutation: an exact missing method can yield one loader _FailedTest. Use a disposable no-TestCase replacement intentionally ignoring the selector, such as unittest.main(argv=[sys.argv[0]]). Confirm captured Ran 0 tests, then require the independent count assertion to reject it before interpreting version-dependent exit status. This changes only fixture source.

Check: `python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportAdopterEndToEndTests ReviewerReportControlTests`.

### Step 5: Review and verify the frozen candidate once

**R1-R6; files:** the three approved tracked files plus ignored new-slice reports/logs.

Finish guide/tests and assess affected paths; trace requirements to final tests, check whitespace/static scan and run the approved six-command convergence once on the candidate. Require 6 PASS / 0 FAIL / 0 MANUAL. Before expensive execution, record acceptance criterion/input scope and why no valid covering new-profile PASS exists. Diagnose failures narrowly before fixes. Before repeating a check, invoke lifecycle reuse; never rerun a REUSE or unchanged failure. Refresh only evidence invalidated by repairs.

Close/report retrospective with evidenced lessons or an explicit no-new-lessons reason. Obtain independent ordinary two-pass review of approved spec/plan, diff, convergence and evidence; preserve its full canonical Markdown unchanged. Resolve blocking findings and re-review relevant fixes. No native session/capture/trust operation.

Freeze on authorized current base without fetching/merging. Run the full framework suite once on that reviewed candidate, supervised in background/wait-check rather than output polling. Record exact source/runtime scope and outcome without inventing counts from suppressed output. Record Review and Verify only after their exits hold. Report three-file scope, convergence, five failures, seven controls, review/full-gate outcomes and retrospective; stop verified/uncommitted.

## Testing strategy

Use public interfaces, bounded subprocesses/cleanup, handwritten source-derived oracles, real fixture Git inventory and independent count-before-exit. RED/GREEN establishes absent-profile detection. Confirmed variants establish sensitivity of later-written freshness, matching and count checks. Static failure cases establish only the target's instruction assertions, never actual review quality.

Python persona materially informed import-time effects, repository/runtime boundary separation, Python 3.9 compatibility and public-interface evidence. Retain disk-backed fixtures; isolate lifecycle state and separate fixture task creation if timestamp precision requires it.

## Validation commands

Future implementation checks only; no product execution before plan approval. Six approved acceptance commands remain unchanged:

```text
python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportProfileTests
python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportDependencyTests
python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportExportTests
python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportCompatibilityTests
python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportFrameworkEndToEndTests ReviewerReportFailureTests
python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportAdopterEndToEndTests ReviewerReportControlTests
```

Record focused checks through lifecycle run/redgreen. Candidate checks:

```text
python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5d.md --plan docs/assurance/plan-5d.md --tests .ai/scripts/tests/test_assurance_inputs.py
python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-5d.md
python3 .ai/scripts/lifecycle.py run inputs-5d-diff -- git diff --check
python3 .ai/scripts/lifecycle.py run inputs-5d-scan -- python3 .ai/scripts/lifecycle.py scan-diff
python3 .ai/scripts/lifecycle.py run inputs-5d-framework -- python3 .ai/scripts/run_tests.py -j 8
python3 .ai/scripts/lifecycle.py audit
```

Before repeats use `python3 .ai/scripts/lifecycle.py reuse LABEL_OR_CMD`; current convergence supplies acceptance evidence without duplicate E2Es. Full gate runs once after review/freeze. Reload applicable validation-policy sections before Gate 4/long checks. Check wait_check CLI help before background launch; keep default wait budget and delegate long waiting when needed, without short model polling or violating host call limits. No real-agent lifecycle evaluation is required because tier/stage rules remain unchanged.

## OKF impact

Planning affected on the three tracked paths returned exit 1, no bundle. Framework synchronization is INAPPLICABLE, not records PASS. Never initialize knowledge or invent baseline/log evidence. Synchronize existing lifecycle guide and preserve ignored local spec/plan/implementation/convergence/review artifacts and all closed 5c records.

## Risks and mitigations

- A loader failure masquerades as one test: confirm an actual zero-test control and reject on count.
- Static failure masks freshness: preserve conformance during freshness edits and isolate five deliberate failures.
- Catalog-derived oracle hides omissions: independent source expectations and all five omitted-document variants.
- Prior-profile comparison misses wiring: explicitly compare/export all three entries.
- Guide edits stale selected bytes: finish documentation before final preflight/convergence.
- Runtime drift inflates evidence: retain exact source/runtime scopes and static claim limits.

## Out of scope

Target/role/skill/hook changes, full-class/module registration, TOML structural parsing, read discovery, scope minimization, narrower gates, automatic adoption, native/model/session/trust actions, historical rescoring, base refresh/worktrees, invoking-framework knowledge and commit/push/PR/merge.

## Open decisions

None. Approved D1-D4 settle behavior. The user approved this plan; record Plan and begin implementation.

## Planning validation

Approved spec analyze and trace each exited 0; six requirements traced. Intent recorded with --approved-by human:enramosjr from the user's approval. lifecycle audit exited 0 for active record 20261029T155725Z-claude_assurance-increment-7.json. `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5d.md --plan docs/assurance/plan-5d.md` exited 0, six requirements traced into the plan; this establishes no implementation/test result. git check-ignore exited 0 for specification-5d.md and plan-5d.md. No product tests or tracked source edits occurred during planning. Plan approval/registration remain pending.
