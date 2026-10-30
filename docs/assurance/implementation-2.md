# Increment 2 implementation evidence

L2, Python principal engineer; approved specification-2.md and plan-2.md. Intent and plan recorded. No commit, push, PR or Git merge authorized or performed. Increment 7's four changes and evidence remain preserved.

## Implementation

- Internal assurance gate selects task-start input changes, current changed blocks and delta-operated IDs; checked Git operations and capability/evidence diagnostics fail closed.
- Existing L2/L3 adopter Verify checks the gate before publishing success. No obligation runs implicitly; existing prerequisite checks remain.
- Exact-match delta acceptance produces scoped req evidence from pre-execution snapshots alongside ordinary converge evidence, in the existing locked reload-and-append transaction.
- Existing guide documents behavior and limits. Framework mode has no knowledge bundle; affected/records absence is inapplicable, not PASS. Working artifacts remain ignored.

## Test-first evidence

- GateStatusTests RED: before integration, Verify incorrectly recorded success for touched UNVERIFIED requirements (including L3). GREEN recorded after the gate.
- DeltaEvidenceTests RED: matching convergence produced no req entries. GREEN after pre-execution capture/publication.
- DocumentationTests RED: guide lacked task-start/gate behavior. Full test module GREEN includes documentation.
- `lifecycle.py redgreen green -- python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_gate.py`: GREEN, 26 tests on completed slice.
- Initial full RED also exposed fixture prerequisites (log entry, stable review refs and integer timeout); these were corrected before treating gate/evidence failures as product evidence. No source fixes were based on those fixture errors.

## Validation remaining

Confirmed mutation proofs; independent review; final framework suite; real-agent lifecycle evaluation; retrospective and Verify.

`lifecycle.py converge docs/assurance/specification-2.md`: 8 PASS, 0 FAIL, 0 MANUAL on the completed source candidate. Trace with approved spec, plan and new test module: 8 requirements traced.

Real-agent environment: `claude --version` reports 2.1.312; local auth reports subscription authentication. The unchanged live observer pins Claude 2.1.296 and refuses version drift before model launch. A supported observed real-agent execution is not yet established; do not claim PASS or modify unrelated observer policy silently.

Automatic approval review rejected the proposed `lifecycle.py run assurance-2-real-agent -- python3 .ai/scripts/lifecycle_eval.py run ... -- python3 .ai/evals/checks/live_observer.py launch claude /home/enramosjr/.local/bin/claude` before process creation. Its stated reason: authenticated external evaluation could transmit repository contents and consume subscription resources; destination/payload authorization remained unresolved. No real-agent evaluation was executed, no PASS claimed, and no indirect retry is authorized. Complete unaffected local validation; final delivery must identify this blocker and request explicit authorization for the external evaluation if still needed.

## Review corrections

- Initial independent review found High completion-ordering false VERIFIED and Medium CRLF false touch; report saved as review-2-initial.md.
- CRLF test RED selected unchanged CALC-R1; GREEN after gate Git reads preserve binary blobs/path bytes and decode UTF-8 without universal newline translation. Public changed report remains text-mode compatible.
- Overlap test RED reported VERIFIED despite later-completed failure; GREEN after requirement outcomes receive completion timestamps while keeping pre-execution fingerprints.
- Original mutation baseline PASS, 12/13 killed. The block-only test had inadvertently broadened its scope, letting an input-path hit mask removal of block comparison. Preserve its exclusion in the fixture; targeted block/Git/newline/order/fingerprint variants rerun on corrected candidate.
- Retrospective closed with lesson 1: per-command input fingerprints must precede execution; final convergence snapshots cannot be aliased into requirement evidence.

Final corrected source candidate d17338e: refreshed convergence R1-R8 8 PASS, 0 FAIL, 0 MANUAL. Targeted mutation command `lifecycle.py run assurance-2-mutations-targeted -- python3 docs/assurance/mutate-2.py block-omitted git-swallowed normalized-baseline start-timestamp post-run-inputs` exits 0; all five edited variants confirmed and killed. Combined with preserved original killed variants, all 15 distinct planned/current variants have rejection evidence (the originally surviving block mutant is now killed). `git diff --check` PASS; scan-diff has zero unwaived Critical and three no-direct-assert heuristics in tests whose helpers assert Verify state and process outcome.

## Integrated gate compatibility repair

The first full framework gate on d17338e ran 737 tests in 61.3 seconds; one failed: increment 7 ReportOnlyTests compared protected files directly with HEAD, rejecting increment 2's intended source changes. This is an integration-test assumption, not a measurement behavior regression. A focused RED pinned that exact assertion. The narrow repair changes only ReportOnlyTests to assert existing observed() before/after snapshots of protected invoking-source bytes and explicitly require their presence. The same focused command GREEN. Increment 7's implementation, counts, original static change receipt and other tests remain preserved; its permanent runtime assertion now composes with subsequent increments. This necessary test-file adjustment was discovered by the full gate, outside the original planned file list; it does not change product policy or the measurement contract.

Refreshed convergence, confirmed source-write mutation proof, narrow independent re-review and affected full gate rerun are required before reporting local validation complete. Do not repeat unaffected measurement mutation scenarios.

On corrected source a491524, refreshed R1-R8 converge again 8 PASS/0 FAIL/0 MANUAL. Narrow compatibility proof `lifecycle.py run assurance-2-measure-integration -- python3 docs/assurance/mutate-measure-2.py` PASS: copied ReportOnlyTests baseline exit0; confirmed mutation makes measurement append to invoking assurance.py; same test exits1 with the protected-file AssertionError. The harness first refused an ambiguous target before mutation (two matching require_disk lines), then used the unique measure signature and passed; no false kill was counted. Evidence mutation-measure-integration-2.json and measure-integration-2-repaired.log.

## Final local gate and delivery state

- Independent narrow integration re-review Approved; updated review-2.md recorded. No outstanding code findings.
- `lifecycle.py run assurance-2-framework -- python3 .ai/scripts/run_tests.py -j 8` PASS, exit0 on a491524, framework-2-final.log. Successful child output is suppressed by lifecycle run, so no fresh test-count claim; initial 737-test failure log retained.
- `lifecycle.py run assurance-2-diff -- git diff --check` PASS, exit0 on a491524. Reuse correctly returned RERUN after the test-file change.
- Final audit OK; affected reports no bundle (framework inapplicable, not PASS). No knowledge bundle initialized.
- Intent, plan and Approved review recorded; retrospective closed with lesson1. Verify NOT recorded: required real-agent evaluation blocked by automatic approval review. Ship NOT recorded. No commit, push, PR or Git merge.
- HEAD remains9efcfb7939cd6818f28caab48d3dadf4b2d69f4a; source candidate a491524. Gate implementation, measurement behavior/counts and all other increment7 changes retained. One measurement test was adapted for later-increment compatibility as described above.

Next action requires explicit user authorization to qualify the installed Claude CLI/observation compatibility and run the two bounded fixture evaluations via the existing subscription, transmitting copied framework kit and temporary fixture content to Anthropic and consuming subscription quota. Do not retry the rejected command indirectly or claim Verify before actual required evidence passes.

## External evaluation authorization

The user subsequently answered "yes" to: "May I qualify Claude 2.1.312 and run the two bounded fixture evaluations through your Pro subscription? This sends copied framework/fixture content to Anthropic and consumes quota." The earlier missing authorization is resolved. No paid API billing, extra campaign, source changes or delivery operations were authorized. Qualification/execution is delegated to the existing local validation agent. It must preserve tracked source candidate a491524 and adapt any CLI-specific operator only in an ignored isolated copy, retaining native observation and frozen-configuration checks. Real outcomes remain pending.

Model-free qualification completed: installed Claude2.1.312 supports required flags; native init debug confirms installed lifecycle SessionStart ran status0 with router context. Because untrusted project permissions are dropped, the isolated operator supplies identical installed governance hooks explicitly alongside observer hooks. Native-style edit/shell guard probes return structured deny; copied native parser rejects missing reviewer identity. Operator changes remain ignored, full diff/hash in operator-2/operator.diff and qualification.json; version_only_change=false, frozen configuration pin20f5f297...ca97. No tracked source changed. Subscription-only launch wrapper removes API/provider overrides and requires loggedIn claude.ai/firstParty/pro before model launch. Two bounded cells authorized, no model fallback/retry; actual native model/effort/reviewer evidence is still required from those cells.

## Actual bounded real-agent result

The two authorized cells executed once each. `lifecycle.py run assurance-2-real-agent -- python3 docs/assurance/run-real-agent-2.py` exited1 on unchanged a491524: feature-l2 FAIL, control-delta FAIL; 0 PASS/2 FAIL/0 ERROR. Native observed model claude-sonnet-5-5, medium effort, CLI2.1.312, frozen configuration20f5f2977901bebde6b4babb7aacabc21e7b596b70e2023cbf1db991055dca97. Charged64.57142000400927 agent seconds within600; original300/cell and660wall limits retained. No retries/fallback or additional model calls.

Independent operator preparation/provenance review Approved (operator-review-2.md); exact source-byte/mode audit covers138 files. The evaluator ran an exact clean disposable KIT snapshot, not a commit in the user checkout. `lifecycle.py run assurance-2-real-results -- python3 .ai/scripts/lifecycle_eval.py results-check docs/assurance/real-agent-2.json --require-real` PASS validates qualified recorded observations, NOT passing fixture behavior.

Native logs pin both failures to Write permissions for spec/plan documentation flagged sensitive. Feature-l2 could not fill the spec stub; control-delta recorded approved intent but could not write its plan. Neither reached implementation, reviewer, convergence or the new assurance gate. The logs explicitly report no approval surface under permission-prompts=none; agents stopped rather than bypass denials. Paths beneath .git/okf-scratch suggest ancestor-sensitive classification, but that cause remains an inference distinct from the directly observed refusals. Exact bounded excerpts/transcript paths: real-agent-2-diagnosis.json; full summary: real-agent-2-report.md; results: real-agent-2.json.

Verify remains NOT recorded and required behavioral evidence remains incomplete. Original two-cell authorization is exhausted. Local, no-model preparation may create a new outside-.git fixture layout using Git separate metadata without weakening guards; any additional model retry requires fresh user authorization. Keep original failed records immutable and do not downgrade them to PASS.

## Authorized outside-.git retry

The user answered "yes" to the explicit request for two additional fixture tests through Pro under the same time limits, after disclosure that the original allocation was used and additional quota would be consumed. Prepared layout operator-2-retry uses separate Git metadata outside literal .git ancestors; bytes/modes and clean provenance verified with unchanged source a491524. Same observer/permissions/guards and sanitized subscription-only auth; no paid API, model fallback or extra retry authorized.

Actual retry is delegated as `lifecycle.py run assurance-2-real-agent -- python3 docs/assurance/run-real-agent-2-retry.py --authorized`. The same semantic ledger obligation is genuinely re-executed with repaired setup; original failed entry/results/logs remain preserved. New terminal outcomes go to real-agent-2-retry.json, never overwrite real-agent-2.json. Exactly two new cells, 300 seconds each, 600 agent seconds and 660 wall seconds. Verify remains pending actual behavioral outcomes.

## Actual retry result and remaining boundary

The authorized retry completed on unchanged a491524, same assurance-2-real-agent obligation exit1. Both cells now implemented their fixture behavior, passed convergence, delegated one reviewer and recorded Verify in their own fixture repositories. Native sensitive-path refusals did not recur. Strict evaluator outcome is still 0/2 PASS: each failed `Approved review artifact is not bound to the observed reviewer result`. Charged154.572agent seconds within600. No further models/retries authorized or run.

Read-only native-log diagnosis pins the exact causes without changing artifacts/scoring:

- feature-l2: actual observed reviewer hash equals the raw handback. Parent prepended a title and provenance introduction to that report body; the saved artifact hash differs. Only a prefix differs, but the verbatim binding check correctly refuses it.
- control-delta: reviewer returned prose `Verdict: Approved`, not canonical `## Verdict`; the unchanged observer therefore has no canonical report hash/verdict. Parent rewrote/summarized it into canonical sections rather than retaining the observed result. The saved artifact also differs from the raw handback.

Exact hashes/handbacks/Write payloads/diffs: real-agent-2-retry-binding-diff.json and binding-feature-l2.diff / binding-control-delta.diff. No post-run artifact repair, rescoring or observation relaxation. `lifecycle.py run assurance-2-real-results-retry -- python3 .ai/scripts/lifecycle_eval.py results-check docs/assurance/real-agent-2-retry.json --require-real` PASS certifies qualified result integrity, not behavioral PASS.

Increment2 remains locally implemented/reviewed with passing acceptance/full-suite evidence, but Verify/Ship remain unrecorded because real-agent evaluation is FAIL. Canonical reviewer output and verbatim parent artifact preservation require resolution before another campaign; no third allocation is implied by either exhausted two-cell authorization. Source checkout remains uncommitted, original results and all later diagnostics preserved.

## Existing report-contract repair requested by user

User said "continue" after the focused repair was identified. Analyst inspection confirms the canonical template and exact observed/saved hash binding already exist; this is instruction enforcement, not new gate/report/scoring semantics. Original approved spec and plan stay hash-unchanged; plan-2-review-report-addendum.md records bounded implementation detail for Steps4-5/R8 compatibility. No new external allocation is inferred.

Reviewer registrations now always load Completion report; the role requires complete canonical final Markdown without preface/fence. Parent lifecycle/skill instructions preserve the entire returned body unchanged, use only existing YAML-frontmatter metadata outside it, and request reviewer correction rather than fabricate missing verdicts. Existing hash/scorer/observer unchanged.

Focused reviewer_completion_report_contract RED recorded missing mandatory load and role instructions; GREEN after repair. New OutcomeTests.test_reviewer_report_body_binding passes the unchanged scorer for intact and metadata-only bodies, and rejects prefixes, rewritten summaries and manufactured verdicts specifically for observed-result binding even after artifact hashes are legitimately refreshed and lifecycle audit passes. Local copied-source mutation controls, current convergence, independent review and final framework gate follow; old real-agent failures stay FAIL.

Candidate6ad08d1: R1-R8 refreshed convergence8PASS/0FAIL/0MANUAL. `lifecycle.py run assurance-2-report-contract-mutations -- python3 docs/assurance/mutate-report-contract-2.py` PASS; two copied focused baselines pass and all six confirmed variants fail intended assertions (mandatory-load omission per registration, role final-report omission, parent preservation omission per instruction surface, disabled strict binding in throwaway scorer). No syntax/import/zero-test failures counted. Evidence report-contract-mutations-2.json/log. `git diff --check` PASS; scan-diff zero Critical, same three helper-based no-direct-assert heuristics, TOML outside H2-H3 scan scope. Framework affected reports no bundle, inapplicable not PASS. Independent review pending; full framework suite deferred until it closes. No new external model allocation.

Independent repair review Approved on6ad08d1; its complete canonical final Markdown was saved unchanged as review-2-report-contract.md (no parent prefix/rewrite), body equality verified through repo.py read against the returned report text, and stage review recorded. Updated framework suite is delegated on this frozen candidate; earlier a491 evidence remains historical. The existing retrospective closure with lesson1 is retained. Required real-agent adherence evidence remains unmet; no extra model allocation inferred from the local repair request.

Final local repair gate on6ad08d1 PASS: `lifecycle.py run assurance-2-framework -- python3 .ai/scripts/run_tests.py -j 8` exit0 (framework-2-report-contract.log). Successful child output suppressed, no fresh count claimed. `lifecycle.py reuse assurance-2-diff` RERUN because tree changed, then `lifecycle.py run assurance-2-diff -- git diff --check` exit0 on6ad08d1. Original logs preserved. Local repair complete; existing real-agent failures unchanged and Verify NOT recorded. A no-model fresh-source follow-up preparation may be staged for review, but another external two-cell allocation requires explicit user consent.

## Repaired-contract external allocation authorized

User subsequently answered "yes" to the prepared two-fixture Pro evaluation under the same limits, after disclosure that earlier allocations were exhausted and Verify still required live evidence. Exact prepared invocation `lifecycle.py run assurance-2-real-agent -- python3 docs/assurance/run-real-agent-2-report-contract.py --authorized` is now delegated/running. It enforces source6ad08d1 and agent/config pins, sanitized Pro auth, exactly2cells300/cell600agent660wall, no fallback/automaticretry. Old results remain immutable; new real-agent-2-report-contract.json is separate. No source commit/push/PR/merge or extra campaign authorized. Actual behavioral outcomes pending; keep Verify unrecorded until qualified full PASS.

## Repaired-contract live outcome

Authorized two-cell execution completed on unchanged6ad08d1, same assurance-2-real-agent label exit1: feature-l2 PASS, control-delta FAIL, ERROR0. Charged245.440seconds within600. No further model calls, patches or campaign preparation. `results-check --require-real` integrity/qualification PASS recorded as assurance-2-real-results-report-contract; it is not an overall behavioral PASS.

Feature-l2 passed ALL strict checks: actual/raw/saved report hashes match, correct identity/read-only/order and frozen candidate pins. Control reviewer now returned a full canonical report, but itself ran mutating converge during its read-only interval (15:51:12Z), changing convergence receipt pin while source/spec/plan pins stayed identical. Parent rewrote that reviewer body into a short report with a different hash and reran converge again after Verify (15:51:39Z). Observer/scorer correctly rejected candidate mutation and observed/saved report mismatch. No scorer defect, record repair or rescoring was inferred.

Evidence: real-agent-2-report-contract-report.md, result JSON/log, diagnosis JSON, binding-diff/order JSON and exact body diffs. Source/local tests/review remain unchanged and passing, but strict real obligation still FAIL; Verify/Ship NOT recorded. Instructions alone did not prevent control-session mutation/report rewriting. Further remediation would need an explicit scoped decision about mechanical read-only/report-preservation enforcement; do not automatically stack more wording changes or purchase another pair of calls. All three authorized two-cell allocations are exhausted. No source delivery authorized.
