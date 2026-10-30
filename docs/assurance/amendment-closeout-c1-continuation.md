# C1 validation continuation: specification and plan amendment

**DRAFT — requires explicit human approval. No correction, continuation or retry is authorized by this document.** This amends the execution/evidence boundary of the approved C1 validation specification and implementation plan; it leaves their original bodies, the stopped campaign and C2 unchanged.

## Problem and outcome

The single approved campaign stopped at N08 because its operator oracle predicted a narrower changed-ID set than the approved mutation produces. [Independent evidence review](review-evidence-closeout-c1-stopped.md) confirms eight intended mutant assertion failures and twenty-three baseline method passes, but does not approve C1 closure. Three original classes remain unexecuted.

Complete the original eleven-class proof with a separately identified continuation and aggregate evidence report. Preserve the first campaign as FAILED rather than relabeling it. The continuation would add only N09–N11: six product workers, bringing the aggregate to the original twenty-two-worker scope.

## Users and scenarios

- The maintainer explicitly approves the N08 oracle correction and the qualified reuse boundary before further implementation or execution.
- A validator uses immutable evidence for N01–N08 and executes only the missing three classes and their approved mutants.
- An independent reviewer checks both evidence segments and the N08 restoration qualification before any C1 closure.

## Frozen prior authority

- Original candidate manifest remains forty-two files, SHA256 `32affe791ca9c75523ec5780a46f7cfe30e8179f2d77e66eaff63d147003ca29`.
- Stopped report `closeout-c1-validation-results/report.json`: SHA256 `a0d0cbf1cf2fc0368b939cef63b323ba9bbfda04e2de7a4299aace27a7fd2fc2`; outcome FAILED; sixteen workers; duration19.68976359300723 seconds.
- Original freeze `closeout-c1-operator-freeze.json`: SHA256 `0bdf33257d4139da8793b8515d3f0a30ff89eec43048f0fa86a97145d72549ed`.
- Independent partial-evidence review: SHA256 `413c07d896e2f93ebf2f0af46d6fadda89574de2019a522ce73fd357d3a25023`.
- Original operator stays unchanged at SHA256 `d86802775f980e2d8daebe34693a5e3f77ee77c471496b7cb8262b831d6da0fb`; its frozen tests, spec, plan, pre-run review, raw artifacts and seals also stay unchanged.

## Requirements

- R1: The continuation MUST verify all prior report/artifact/freeze/review pins and exact current source/branch/HEAD/runtime identity before accepting reused evidence; any drift MUST stop execution without repinning.
- R2: The aggregate MUST name all eleven exact original classes and thirty baseline methods, identifying twenty-three baseline passes from the first segment and seven from the continuation; only N09–N11 MAY execute in the continuation.
- R3: N08 reuse MUST require its exact original mutation bytes, one unchanged target method, one AssertionError at test_assurance.py312, no errors/skips/timeouts and the observed ID set CALC-R1 through CALC-R5. It MUST state that N08 restoration has independently reviewed control-flow provenance rather than inventing a completed row flag. N09–N11 MUST use the exact already-approved mutations and assertion locations unchanged.
- R4: The separately identified continuation operator MUST retain the original four invalid-proof protections, add a synthetic regression for the N08 same-fault exclusion effect, and refuse wrong assertion frames, missing CALC-R4, changed source, incomplete evidence, failed restoration or replay of an incomplete/failed continuation.
- R5: The continuation MUST use isolated disposable copies, no more than six additional product workers, at most180 seconds per worker and a five-minute overall segment limit including verification/publication/cleanup. The aggregate MUST distinguish active execution duration from the approval gap and remain below the original twenty-minute active execution ceiling. It MUST stop without automatic retries or substitutions on any unexpected result.
- R6: A new linked report MUST keep the first campaign's FAILED/0-PASS/6-FAIL outcome explicit while mapping qualified reused proof and new proof separately. C1 MUST remain open until the aggregate passes independent evidence review and applicable lifecycle verification.

## Acceptance

Proposed **new**, not yet implemented command: `python3 docs/assurance/validate-closeout-c1-continuation.py`. One bounded continuation supplies all six checks; repeated identical acceptance invocations verify/reuse complete successful continuation evidence without launching more product workers.

- R1: `python3 docs/assurance/validate-closeout-c1-continuation.py` refuses any mismatch in prior pins, forty raw artifact hashes, report seal, candidate or runtime identity.
- R2: `python3 docs/assurance/validate-closeout-c1-continuation.py` succeeds only with the complete eleven-class/thirty-baseline-method map and exactly six new product-worker results for N09–N11.
- R3: `python3 docs/assurance/validate-closeout-c1-continuation.py` succeeds only with all eleven intended mutant failures and explicit N08 provenance qualification; no old campaign result is rewritten.
- R4: `python3 docs/assurance/validate-closeout-c1-continuation.py` succeeds only when synthetic rejection checks and the N08 oracle regression pass, and incomplete/changed/failed evidence never receives reuse credit.
- R5: `python3 docs/assurance/validate-closeout-c1-continuation.py` succeeds only with six-or-fewer new product invocations, timely successful restoration/publication, identical invoking inputs and aggregate twenty-two-worker accounting; timeout or drift exits nonzero.
- R6: `python3 docs/assurance/validate-closeout-c1-continuation.py` produces a qualified aggregate mechanical result. Independent evidence-review approval remains a separate mandatory closure gate.

## Proposed implementation sequence

1. **R1, R2, R3:** Create new local files validate-closeout-c1-continuation.py and test_closeout_c1_continuation.py; import only the old operator's standard-library helper definitions, never call its campaign/main or change its globals/files. Read and audit immutable raw evidence. Correct N08's oracle in the new version to the exact observed five-ID set, while retaining the original designated assertion and failure-quality checks. Write its regression first; prove it rejects an incorrect N08 result.
2. **R4, R5:** Reuse the already-reviewed isolated worker, mutation and result mechanisms through the new coordinator, with new closeout-c1-continuation-results/ and closeout-c1-continuation-freeze.json artifacts, fresh operator/reviewer pins, six-worker ceiling and five-minute budget. Test restoration/deadline failure propagation, incomplete-map/drift rejection and successful evidence reuse with synthetic fixtures before product execution. Original four controls remain required; no original product class is rerun for them.
3. **R1–R6:** Obtain independent pre-run review of the new code, its synthetic results and the amended reuse/qualification logic. Freeze that new operator identity without overwriting the original freeze or failed report. Record a new approval-bound lifecycle specification/plan reference that explicitly retains the earlier failed convergence as historical current-candidate evidence.
4. **R2, R3, R5:** Run N09 ReportFormatTests (two baseline methods) and its selected schema mutant; N10 ExitCodeTests (four methods) and its selected strict-exit mutant; N11 Assurance (one method) and its command-table mutant. These are exactly six new product-worker invocations. Record explicit per-row restoration success, including failure paths; stop on the first unexpected result.
5. **R6:** Independently review the aggregate of immutable prior evidence plus new evidence. Only after approval complete the retrospective/Verify and update C1's status. Preserve the original failed report/convergence and the qualified N08 explanation even if the aggregate later succeeds.

## Constraints

- Approval of this amendment would authorize only the correction and bounded continuation above, with independent pre-run and post-run review; it is not approval of future results.
- Keep invoking cwd `/home/enramosjr/Projects/agentic-assurance-7`, branch/HEAD and candidate pins unchanged. No tracked source/test/config/guide edits, commits, staging, push/PR/merge, branch/worktree or base refresh.
- C2 remains uncommitted, 5o unapproved, all profile work paused, catalog fourteen. No full-framework/profile/native/model/session/trust work or dependencies.
- Framework mode: ignored local operator/test/report artifacts and lifecycle scratch only; do not create knowledge/ or fabricate bundle validation.
- The approval gap between stopped execution and a separately authorized continuation is explicitly excluded from active execution duration, not hidden in a claim of one uninterrupted successful campaign.

## Non-goals

Rerunning N01–N08, rewriting any failed outcome, changing a product/test assertion, substituting a mutant, broadening original class coverage, authenticating historical approvals, historical rescoring or initiative release approval.

## Assumptions

- Qualified N08 reuse, including control-flow restoration provenance, is acceptable only if explicitly approved here; this is the independent reviewer's recommendation, not existing authorization.
- The same frozen source/runtime remains available; a mismatch stops this continuation rather than opening a new compatibility or repair scope.

## Open questions

None affecting behavior. Human approval of this combined scope/implementation amendment remains pending.
