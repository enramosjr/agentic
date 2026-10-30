# Spec: Bounded C1 class-level negative proof

Version: **0.1.0-draft**, 2026-10-29 America/Chicago. Tier L2, kind docs/validation. **Awaiting human approval; no validation authorized or run by this specification.**

## Problem and outcome

[C1 reconciliation](closeout-c1-reconciliation.md) recovered area1's approved spec, plan, review and lifecycle receipt. The remaining gap is its explicit acceptance condition: every new test class must reject a deliberately broken variant. The original reviewer did not establish that map. This specification proposes new evidence on the current candidate, rather than reconstructing or relabeling a historical run.

The outcome is a finite class-to-control report with verified execution, intended assertion failures and unchanged invoking source. It can close only the remaining C1 proof item. It does not grant initiative release approval or close C5/C6 in full.

## Users and scenarios

- The maintainer approves the exact validation boundary before any operator is implemented or executed.
- A validator demonstrates each original area1 class detects one specified behavioral regression using unchanged test assertions.
- A reviewer rejects a claimed kill caused by empty discovery, an unapplied edit, an unrelated error or failed restoration.
- A baseline failure, surviving mutant or changed invoking candidate leaves C1 open and produces a bounded failure report.

## Requirements

- R1: The validation MUST freeze and identify the current working candidate, including all uncommitted C2 files and its untracked ordering test, by HEAD, branch and a per-file SHA256 manifest of execution inputs; it MUST reconcile exactly the eleven classes in the coverage matrix against original area1 source and distinguish current results from historical evidence.
- R2: The validation MUST run all methods in each matrix class unchanged on the frozen candidate copy before accepting that class's mutant result, recording exact selected test IDs, discovered/executed counts, exit status, failures, errors and skips; a missing test, zero count, skip, error or baseline failure MUST prevent closure.
- R3: For each matrix row, the validation MUST apply exactly its specified behavioral mutation in a separate disposable copy, confirm the intended bytes changed and execute the named unchanged test method; a kill MUST require that method to execute and fail at the specified assertion with no test errors, loader/import/syntax failure, timeout or unrelated failure substituted as evidence.
- R4: The validation operator MUST reject four deliberately invalid proof cases: an empty suite, an unapplied mutation, an unrelated loader/error result and a restoration failure; it MUST also reject an incomplete or duplicate class map and propagate cleanup/restoration failure as a nonzero result.
- R5: All mutations and fixture execution MUST stay in disposable copies, with bounded subprocess deadlines and a twenty-minute overall execution limit; the invoking candidate and protected profile inputs MUST remain byte-identical, and each mutated copy MUST be restored and read-confirmed before disposal, including on failure.
- R6: The final report MUST preserve raw command results and hashes, distinguish baseline PASS, intended mutant rejection and operator rejection controls, and declare C1 closed only when R1–R5 all succeed and independent review approves the evidence; otherwise it MUST name the exact remaining gap without upgrading historical claims.

## Acceptance

The following is a **proposed, not yet implemented or executed** local validation command. The implementation plan must be approved separately. Its single bounded execution supplies all six checks; these bullets do not authorize six reruns.

- R1: `python3 docs/assurance/validate-closeout-c1.py` exits 0 only with an explicit current-candidate input manifest and an exact eleven-row roster tied to the original source; a committed-HEAD-only copy that omits C2 fails this check.
- R2: `python3 docs/assurance/validate-closeout-c1.py` exits 0 only when the eleven unchanged class baselines execute their full frozen test roster and pass without skips or errors. The current static expectation is thirty tests, not a claim that they ran.
- R3: `python3 docs/assurance/validate-closeout-c1.py` exits 0 only with eleven applied, non-equivalent mutations and eleven intended assertion failures attributed to the exact target methods below; any survivor or wrong failure rejects closure.
- R4: `python3 docs/assurance/validate-closeout-c1.py` exits 0 only when all four invalid-proof controls are rejected and the exact-map and cleanup checks fail closed. These controls are operator checks, not extra class coverage.
- R5: `python3 docs/assurance/validate-closeout-c1.py` exits 0 only with before/after equality of invoking input bytes, successful copy restoration/read-confirmation, no escaped writes and no exceeded deadline; timeout or cleanup failure exits nonzero and preserves diagnostics.
- R6: `python3 docs/assurance/validate-closeout-c1.py` exits 0 only when its report contains all preceding raw results and a qualified mechanical outcome. Human-independent reviewer approval of those results is an additional required closure gate; operator success alone cannot record C1 closed.

## Coverage matrix

Original authority: `git show f74ae7f:docs/assurance/specification.md`, especially its final Acceptance paragraph; original source at the same commit. Current test assertions are in `.ai/scripts/tests/test_assurance.py` and `.ai/scripts/tests/test_lifecycle_conformance.py`. `Case` is a fixture base with no tests and is excluded. RuntimeTests is a separate class under original R4 and is included. The Assurance class is original R10 and is included even though its current method also checks later documentation terms.

Mutations below change behavior in copied production code or copied guide text, never the test assertions or fixture expectations. Exact replacement bytes and hashes must be frozen in the implementation plan before execution. Anchors refer to current functions, not historical implementations.

| Control | Class; original requirement; baseline methods | Selected method | Broken behavior in disposable copy | Required failing assertion |
| --- | --- | --- | --- | --- |
| N01 | ObligationSyntaxTests; R1; 1 | test_valid_and_malformed_obligations | In assurance._parse, accept duplicate Verify lines instead of returning INVALID. | CALC-R3 must be INVALID; mutant reports a non-INVALID status. |
| N02 | CompatibilityTests; R2; 3 | test_obligation_free_and_prose_capabilities_stay_green | In assurance.evaluate, report an obligation without Verify as UNVERIFIED instead of UNDECLARED. | Expected obligation-free report exit 0 becomes nonzero. |
| N03 | AssureRunTests; R3; 4 | test_run_records_req_entry_with_declared_inputs | In lifecycle.assure_run, record req:BROKEN-<ID> instead of req:<ID>, preserving actual command execution. | Exact req:CALC-R1 must appear in run stdout; the changed label lacks that substring. |
| N04 | StatusTests; R4; 7 | test_fresh_evidence_is_verified | In assurance.evaluate's fresh passing mechanical branch, return UNVERIFIED instead of VERIFIED while retaining ordering/freshness checks. | Expected VERIFIED on fresh evidence becomes UNVERIFIED. |
| N05 | RuntimeTests; R4; 1 | test_changed_executable_is_stale | In ledger._entry_verdict, bypass the runtime_sha256 mismatch rejection while retaining scoped input checks. | Expected STALE after executable edit becomes VERIFIED. |
| N06 | IntegrityTests; R5; 2 | test_invalid_and_output_bearing_records_contribute_nothing | In assurance.evidence.add, bypass the rejection for a ledger.audit problem, allowing the output-bearing forged entry to contribute evidence. | Expected UNVERIFIED becomes VERIFIED; malformed JSON handling remains intact. |
| N07 | UnscopedTests; R6; 3 | test_any_commit_makes_it_stale | In ledger._entry_verdict's no-input branch, accept a changed tree instead of requiring tree equality. | Expected STALE after unrelated commit becomes VERIFIED. |
| N08 | ChangedTests; R7; 2 | test_matched_unmatched_and_unscoped | In assurance.selected, ignore matching negative globs so src/gen/** is erroneously selected. | Expected listed IDs exclude CALC-R4 for src/gen/out.py; mutant includes it. |
| N09 | ReportFormatTests; R8; 2 | test_text_and_json_fields_without_output | Change assurance.SCHEMA_VERSION from 1 to 2. | Expected schema_version 1 differs from actual 2. |
| N10 | ExitCodeTests; R9; 4 | test_strict_counts_undeclared | In assurance.exit_code, omit UNDECLARED from the strict failing statuses. | Expected --strict exit 1 becomes 0. |
| N11 | Assurance; R10; 1 | test_assurance_documented | In the copied guide's Recording table only, change the Assurance row label so the original required command row no longer matches. | The unchanged final assertRegex fails with Recording table row; Assurance status section parsing and term checks still pass. |

The baseline total is 29 assurance tests plus 1 conformance test. Eleven class-baseline processes and eleven selected-method mutant processes form the fixed maximum of 22 top-level test invocations. Existing fixtures may start their normal child CLI processes; those remain within the bounded parent process groups. Four operator rejection controls use small isolated proof fixtures rather than rerunning product suites. Restored-copy hashes provide restoration evidence; no extra baseline reruns are implied.

## Constraints

- Execute only after spec approval, separate implementation-plan approval and lifecycle prerequisite recording. Approval of this draft is not execution authorization.
- Use `/home/enramosjr/Projects/agentic-assurance-7` as the invoking directory; preserve branch `claude/assurance-increment-7` and HEAD `02dd97586873f24a604224aa5ad186a60c4104e7` unless the user explicitly changes the candidate. Capture full current hashes after approval and refuse any drift from the approved plan's pins.
- Preserve the verified, uncommitted C2 candidate described in [its implementation report](implementation-closeout-c2.md). Its seven controls and full-gate result remain scoped evidence, not eleven-class C1 proof. Do not weaken C2's approved ordering semantics to imitate area1's historical tie behavior.
- The invoking `.ai/lifecycle.md`, assurance_inputs.py, test_assurance_inputs.py, test_lifecycle_conformance.py and all profile registrations remain unchanged. N11 alters only the original R10 command-table row in a disposable guide copy; no profile wording, catalog or conformance assertion changes are allowed.
- Standard library, current supported Python/runtime, no network, native/model/session/trust actions or additional dependencies. Disable bytecode writes and isolate fixture Git scratch. Do not copy the live lifecycle state as executable test state or write test records to its shared scratch.
- Set a maximum 180-second deadline per top-level test invocation, with child-process-group cleanup and the stricter twenty-minute overall limit. On any unexpected result stop execution, restore and report; no automatic mutant substitutions, product fixes or retries. A changed control needs renewed approval of the affected boundary.
- Framework mode: local ignored draft/operator/report artifacts under docs/assurance; do not create knowledge/. Existing historical receipts, reports and hashes remain immutable. A successful run is current evidence with its own provenance, not recovered historical proof.
- No full-framework rerun merely to recreate existing unchanged C2 evidence. The later approved plan must apply validation-policy reuse rules and identify any genuinely necessary operator-specific checks.

## Non-goals

- Exhaustive mutation testing, proving every assertion, changing original area1 requirements, or authenticating a schema-valid hand-written ledger record.
- Repairing an unexpected product or test failure, changing assurance behavior, or expanding this eleven-class roster to later increments.
- Approving 5o, executing any profile work, rescoring prior profile/session evidence, or performing paid/model/native evaluations.
- C2 commits, staging, shipping, pushes, PRs, merges, release approval, new branches/worktrees or base refreshes.

## Assumptions

- Replaces "historical replay or new evidence?": new current-candidate proof is the approved C1 reconciliation's available exit route; the old reviewer omission remains a historical fact.
- Replaces "how much negative proof?": one distinct behavioral mutation per original new class, including RuntimeTests and Assurance, is sufficient for this specific acceptance condition; it is not exhaustive behavior assurance.
- Replaces "does a conformance mutant count as profile work?": altering the original command-table row only in a disposable copy tests original R10; all invoking guide/profile/test bytes stay unchanged.
- Replaces "what happens on a surprise?": stop within the fixed limits and report the remaining gap; the scope never silently turns into repair work.

## Finite completion checklist

1. Human approves this validation spec.
2. Draft and obtain approval of an implementation plan with exact source/test pins and mutation bytes.
3. Implement the local operator and its four rejection controls; obtain independent review before the bounded evidence run.
4. Execute the single bounded campaign: eleven class baselines, eleven specified mutant methods, four operator controls, restoration and invoking-tree checks.
5. Independently review the raw class map and failure attribution, publish the qualified report and update C1's remaining-item status only to the extent proved.
6. Keep all changes uncommitted; carry remaining initiative closeout items forward without approving 5o or resuming profiles.

## Open questions

None affecting behavior. The proposed boundary above is ready for human approval. Intent remains unrecorded until approval; no plan, implementation or execution is authorized by the draft itself.
