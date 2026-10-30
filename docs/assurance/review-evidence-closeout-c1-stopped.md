# Review Report

## Verdict

Changes requested — **C1 closure is not approved**. The stopped campaign contains trustworthy partial evidence, but remains FAILED with **0 PASS / 6 FAIL / 0 MANUAL**.

## Scope

Read-only review of the stopped campaign’s report, seal, freeze identity, forty raw artifacts, N01–N08 results, mutation records, frozen operator control flow and convergence log. No campaign, tests, imports, correction or retry occurred.

## Persona Applied

Python principal engineer: exact assertion attribution, negative-pattern semantics, restoration provenance and immutable partial evidence.

## Findings

### Medium — N08’s additional operator oracle excludes a result caused by the approved mutation

**Location:** `validate-closeout-c1.py:252–254`.

The mutation changes `chosen = not negative` to `chosen = True`, disabling every matching exclusion. This includes both `!src/gen/**` and the automatically appended lifecycle-record exclusion. Consequently CALC-R2 can also be selected through a changed lifecycle record.

Raw N08 evidence shows:

- The exact selected method executed once.
- Exactly one AssertionError occurred at the designated unchanged assertion, test_assurance.py:312.
- CALC-R4 was incorrectly included as intended; CALC-R2 was additionally included through the same exclusion bypass.
- No error, skip, timeout, loader failure or zero execution substituted for the assertion.

Thus N08 is **the intended mutation caught at the intended assertion**, not a wrong assertion or demonstrated product defect. The extra operator oracle was overconstrained; the pre-run review missed this interaction. Its rejection correctly stopped execution rather than silently relaxing the oracle.

## Validation Reviewed

Independent read-only checks established:

- All **forty raw artifact hashes** match the report.
- Report SHA256 matches its seal.
- Report identity equals the frozen identity.
- All **forty-two invoking candidate pins** still match.
- Git status retains only the approved uncommitted C2 files.
- Sixteen product processes ran: **twenty-three baseline methods passed and eight mutant methods failed at their designated assertions**, without errors, skips or timeouts.
- N01–N07 have completed restoration records and unchanged candidate snapshots.
- N09–N11 did not run.
- Convergence’s later five invocations rejected the failed report and launched no further product workers.

N08 restoration has **qualified control-flow provenance**: its frozen finally path restores bytes, read-checks the original hash, verifies all copied pins, disposes the copy and checks its absence before propagating the original wrong-selection error. That original error remains the stop cause, rather than an overriding restoration error. Its mutation JSON’s restored:false is a pre-execution snapshot, not evidence of failed restoration. A completed N08 row flag was not published.

Framework knowledge synchronization remains **INAPPLICABLE**, not PASS.

## Residual Risks

Preserve the FAILED campaign, raw artifacts, seal, freeze and frozen operator unchanged.

A finite next approval boundary is an **explicit amended continuation** that:

1. Corrects and independently tests N08’s operator oracle in a separately identified operator version.
2. Explicitly authorizes qualified reuse of immutable N01–N08 evidence, including the N08 restoration qualification above.
3. Runs only N09–N11: **six additional product workers**, bringing the aggregate to the original twenty-two-worker scope.
4. Produces a new linked report and receives independent evidence review before C1 closure.

This recommendation does not authorize that continuation. No failed report should be relabeled PASS, and no retry or source change is implied.
