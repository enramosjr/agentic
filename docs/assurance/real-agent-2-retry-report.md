# Repaired-layout real-agent evaluation: strict binding failures retained

2026-10-28. User explicitly authorized two additional bounded fixture cells through the existing Pro subscription after the initial two-cell allocation failed. No further allocation, model probes, fallback or retries were used. Source candidate a491524 remains unchanged, with no source commit, push, PR or merge.

## Exact execution and limits

`python3 .ai/scripts/lifecycle.py reuse assurance-2-real-agent` → RERUN (last exited 1).

`python3 .ai/scripts/lifecycle.py run assurance-2-real-agent -- python3 docs/assurance/run-real-agent-2-retry.py --authorized` → exit 1, source tree a491524. The same semantic ledger label records the genuine repaired evaluation attempt while preserving the original failure history and original real-agent-2.json/log.

The prepared wrapper verified source bytes/modes, removed API/provider overrides, required effective loggedIn/claude.ai/firstParty/Pro authentication, and executed the exact argv in operator-2-retry/planned-evaluation-command.json. The frozen-source copy uses separate Git metadata outside any literal .git ancestor; unchanged native observer, guards, permissions and config pin were retained.

Allocation: feature-l2 and control-delta, one cell each, timeout 300 seconds each, max-agent-seconds 600, max-wall-seconds 660. Actual charged agent time: 154.572012423072 seconds. No paid API billing was selected.

## Results

- feature-l2: FAIL, sole reason `Approved review artifact is not bound to the observed reviewer result`.
- control-delta: FAIL, same sole reason.
- Totals: 0 PASS, 2 FAIL, 0 ERROR, 0 NOT_RUN. Both cells completed evaluation; neither timed out.

Both fixtures now wrote their documents, implemented the requested behavior, passed convergence, delegated one independent same-model/medium-effort read-only reviewer, and recorded fixture Verify. Behavioral and lifecycle checks preceding strict review binding found no other failures. Native observations identify Claude 2.1.312, claude-sonnet-5-5, medium effort, distinct read-only reviewers, no reviewer writes, matching before/after/reviewed candidate pins and correct convergence → review → Verify order. These successes do not erase the strict binding failures.

`python3 .ai/scripts/lifecycle.py run assurance-2-real-results-retry -- python3 .ai/scripts/lifecycle_eval.py results-check docs/assurance/real-agent-2-retry.json --require-real` → exit 0 on a491524. This is a qualified-result integrity PASS, not a behavioral PASS.

## Pinned binding diagnosis

Diagnosis uses only retained native parent transcripts, actual reviewer handbacks and final successful Write/Edit payloads. The evaluator removed temporary fixture trees normally; saved artifact bodies were reconstructed from those successful native payloads. No fixture artifact was repaired after execution and no FAIL was rescored.

feature-l2:

- Observed reviewer report SHA256 and independently unframed handback SHA256 both equal `ddb32a1dbb4613fdae62c3b268c54d9b96fd4e6346eecbeaadae080bfa660a8b`.
- Saved artifact body SHA256 is `9d5de425303c43180158087ddb774e41b3420ec5a3cd5f1d2259f57ab52f553f`.
- The evaluated parent added only a `# Review: cli.py --json flag` heading and a provenance introduction claiming verbatim preservation before the otherwise unchanged reviewer text. Whole-body hashing correctly rejects the extra prefix. See binding-feature-l2.diff.

control-delta:

- Actual reviewer handback SHA256 is `f128ad2832fbf84b932387521e2efec4ba3dce2fbed2f8efe3ffe8a9770f5bc6`.
- The reviewer returned prose `Verdict: Approved`, without the canonical `## Verdict` section. The unchanged observer therefore did not populate a report SHA/verdict (both null); it did not invent canonical approval.
- The evaluated parent summarized/reorganized the report into canonical Findings, Spec compliance, Validation Reviewed and Verdict sections. Saved artifact SHA256 is `4a2c6335b424eaa91f6422357db82142b3fb43a6155f9d798d054ada1fa200c9`, differing from the reviewer output. See binding-control-delta.diff.

These are agent report-preservation/format adherence failures under the existing strict contract, not evidence that the new assurance gate blocked the workflows. The prior sensitive-path blocker did not recur in this repaired layout.

## Evidence and remaining limit

- real-agent-2-retry.json and real-agent-2-retry.log(.exit): actual results and execution.
- real-agent-2-retry-diagnosis.json: bounded assistant final messages, tool errors and exact retained native transcript paths.
- real-agent-2-retry-review-binding.json: actual handbacks, reviewer observations and successful artifact payload proposals.
- real-agent-2-retry-binding-diff.json and binding-*.diff: exact hash comparisons and compact body diffs.
- operator-2-retry/preparation.json: byte/mode manifest, clean provenance and corrected layout; effective-auth.json: sanitized Pro auth.

The authorized extra two-cell allocation is exhausted. No further campaign is prepared here. The failed real-agent obligation remains unmet, and this evidence must not be used to claim parent Verify completed or the increment ready to ship.
