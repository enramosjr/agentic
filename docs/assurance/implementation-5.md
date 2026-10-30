# Implementation report: increment 5 — Python input profiles

## Delivery update — authoritative

User-authorized commit/push completed: `4ed2aec3a33f3369ff44abf686a7796e5661be3a` contains exactly the new exporter, new acceptance module and lifecycle-guide change. Pushed to origin/claude/assurance-increment-7; exact remote/local HEAD match confirmed; clean tracked checkout; Ship recorded. All docs/assurance files remain ignored and uncommitted. No PR, merge, native/model evaluation, trust grant or historical rescoring occurred.

No source changed or product suite reran for delivery. Controls reuse returned REUSE on b52be33. Framework reuse returned environment/runtime drift, not a new PASS or REUSE; the prior full-gate PASS retains its recorded source/environment scope. Retrospective remains closed with observation 1. handoff-5b.md selects and scopes the next slice for a fresh-chat spec/plan approval sequence. Historical uncommitted/Verify-pending notes below are superseded.

## Final gate update — authoritative

Source tree b52be33 passed its single frozen-candidate full framework gate: `lifecycle.py run inputs-5-framework -- python3 .ai/scripts/run_tests.py -j 8` exited 0. Detached supervisor/wait_check completed with exit 0; framework-5.log is retained. The producer suppresses successful child output, so no full-suite test count is claimed. No source changed during or after the gate.

Independent review is Approved with no outstanding findings (review-5.md, complete body preserved unchanged). Current convergence is 7 PASS/0 FAIL/0 MANUAL, source controls 4/4 confirmed KILLED with baseline PASS, and diff/scan/audit pass. Retrospective is closed with observation 1. Formal Verify is recorded; final audit passes, and status lists Intent/Plan/Review/Verify complete with no required stage remaining. Ship is not recorded and source remains uncommitted. This leading update supersedes historical pending-gate language below.

## Current checkpoint

Implemented on the existing claude/assurance-increment-7 branch at base 5a0ee96136997772e89e978001441dfd7f1261aa. User approved revised spec/defaults and then the plan; Intent and Plan are recorded. Changes remain uncommitted. Initial review's bounded repair is complete; focused re-review and the full framework gate are pending. No final Verify or delivery claim yet.

Latest gate update: focused independent re-review is Approved with no outstanding findings, complete returned body preserved unchanged as review-5.md. Source b52be33 is frozen for `lifecycle.py run inputs-5-framework -- python3 .ai/scripts/run_tests.py -j 8`. Acceptance: complete framework regressions for the new exporter/test module and guide integration, including installer/conformance checks. No covering full-suite PASS exists for this candidate; the earlier increment's PASS cannot be reused after source additions. This is the single full framework gate planned for the frozen candidate. It is pending, not a claimed PASS.

Source scope is exactly three files: new `.ai/scripts/assurance_inputs.py`, new `.ai/scripts/tests/test_assurance_inputs.py`, and existing `.ai/lifecycle.md`. No core producer, ledger, runner, pilot helper, inference, gate, hook or installer code changed. No new worktree, network/base mutation, commit, push, PR or merge occurred.

## Behavior

The standalone exporter contains one literal declared profile for the exact Python runner-test discovery argv. It validates root, catalog, supported Git inventory and paths without importing/running target modules. Text/JSON expose the same ordered four inputs, rationale, limitations, declaration and lifecycle input argv. Positive supplements append after catalog patterns. Refusals emit no candidate and retain existing scope. The guide documents explicit adoption, full-suite refusal and runtime/input-completeness limits.

Two real fixtures exercise existing evidence surfaces. The framework fixture executes the actual selected runner test, records explicit lifecycle inputs and checks REUSE for unrelated edits versus RERUN for each declared file. The adopter fixture adopts the exported declaration, records the actual pilot obligation, observes VERIFIED, STALE and UNVERIFIED for the required changes, and preserves the producer's receipt exclusion. No framework knowledge bundle is initialized.

## Test-first and focused evidence

- `lifecycle.py run inputs-5-baseline -- python3 -m unittest discover -s .ai/scripts/tests -p test_run_tests.py` exited 0 before source edits.
- Seven-class grouped command recorded RED for absent exporter behavior: 12 test methods exercised; failures/errors stem from the missing exporter. Retained red-5.log.
- `inputs-5-focused` passed the six non-E2E classes on the initial implemented tree. Full grouped command then recorded GREEN, including both real fixture flows. Retained focused-5.log and green-5.log.
- Self-review identified option-like supplemental values: a dash-prefixed glob can be parsed as a lifecycle option. Added the focused regression, recorded RED, rejected that unrepresentable form and recorded GREEN. Exact outputs retained in red-5-argv.log and green-5-argv.log. This is a boundary repair within R4/R5, not an inference/grammar change in existing core code.
- Final `lifecycle.py trace docs/assurance/specification-5.md --plan docs/assurance/plan-5.md --tests .ai/scripts/tests/test_assurance_inputs.py` exited 0; all seven requirements traced.
- `lifecycle.py converge docs/assurance/specification-5.md` exited 0 on tree a195f77: seven PASS, zero FAIL, zero MANUAL. Retained converge-5.log.

The fixture preflight captures the real unittest count and freezes the four input hashes across subsequent lifecycle recording. Child success output is suppressed by the existing producer; no test count is inferred from a ledger entry or lifecycle summary. Runtime/environment portability is explicitly not claimed.

## Source controls

`lifecycle.py run inputs-5-controls -- python3 docs/assurance/mutation-controls-5.py` initially exited 1 because the operator classified only 3/4 controls as killed. All four actually produced assertion failures, but this Python returns exit 5 for zero discovery before the original count assertion. The original report/log remain in mutations-5.json and controls-5.log.

Moved count validation before the command exit check so count enforcement is independently observed on all supported versions. No assertion was removed or weakened. `lifecycle.py reuse inputs-5-controls` reported RERUN, and the repaired operator then exited 0 on tree a195f77. Final mutations-5-final.json records baseline PASS and 4/4 confirmed KILLED controls: missing runner, missing helper, zero discovery and loosened exact argv matching. Operator/source hashes, applied byte changes, targeted outputs and outcomes are retained. All mutations occur in disposable copies; no native/model or trust operation occurred.

## Synchronization and retrospective

`okf.py affected` over all three paths reports no bundle: INAPPLICABLE in framework mode, not PASS. Existing lifecycle guide is synchronized; no knowledge bundle/log or fabricated records PASS was created. Working docs remain ignored under docs/assurance.

Retrospective is closed with evidence-backed observation 1: assert actual test count independently because zero-discovery exit codes vary and producer success summaries suppress child output. Evidence: mutations-5-final.json. No project rule was promoted.

## Remaining gates and restrictions

Obtain independent two-pass review; repair/review any findings and reevaluate affected evidence; freeze final candidate; run the full framework gate once; record final diff/scan/audit and Verify. No current full-suite PASS is claimed. Earlier increments' product/native evidence is unchanged and retains its original source/environment scope. No new native/model evaluation attempt, fixture trust grant, historical rescoring or delivery is authorized.

## Review repair and current receipts

Initial independent review requested one Medium R4 repair: existing ignored literal supplements could yield a declaration despite exclusion from the supported inventory. The full report is retained unchanged in review-5-initial.md. A new public-CLI regression recorded RED for both an ignored literal and a bare directory literal, then GREEN after a four-line inventory-membership check. Existing optional wildcard/future-input semantics are not represented as complete ignored-file discovery. Exact outputs are red-5-review.log and green-5-review.log.

Current source tree is b52be33. `reuse inputs-5-controls` reported RERUN after source edits; controls-5-reviewed.log exits 0, and mutations-5-reviewed.json seals current operator/source hashes with baseline PASS and 4/4 confirmed KILLED controls. Earlier reports are retained. Current converge-5-reviewed.log exits 0: 7 PASS, 0 FAIL, 0 MANUAL. No frozen-candidate full suite has run yet. The closing retrospective remains observation 1; its preserved original supporting report has not been changed.
