# Handoff: assurance increment 2

Latest continuation: [mechanical-enforcement scoping handoff](handoff-2-review-enforcement.md). Its current scope/approval state supersedes historical next-action notes below; all prior evidence remains preserved.

2026-10-28. Workdir MUST be `/home/enramosjr/Projects/agentic-assurance-7`, branch claude/assurance-increment-7; do not use the main checkout or create another worktree. HEAD remains 9efcfb7939cd6818f28caab48d3dadf4b2d69f4a. Candidate stays uncommitted. Do not commit/push/open PR/merge without explicit user authorization.

## Approvals and preserved work

- Increment 7 measurement implementation, counts, guide sentence, conformance change and original evidence at cb75486 are preserved. One integration-test adjustment is described below; do not rerun unaffected standalone measurement gates.
- User approved all increment 2 policy choices and specification-2.md, then separately approved plan-2.md. L2 intent/plan recorded with human:enramosjr; independent Approved review recorded as review-2.md.
- Framework has no knowledge bundle. Working artifacts docs/assurance are ignored and MUST NOT be committed; receipts in Git scratch.

## Implementation and evidence

- assurance.py: internal touched selection from recorded task-start HEAD through working tree, baseline block comparisons and current delta IDs; fail-closed diagnostics. Existing changed report unchanged.
- lifecycle.py: L2/L3 adopter Verify gate and exact-match delta acceptance req evidence, one execution, pre-execution input fingerprints and completion timestamp, locked reload-and-append.
- New test_assurance_gate.py: approved R1-R8 acceptance classes, CLI flows and adversarial boundaries. Existing guide updated.
- Initial redgreen module GREEN had 26 tests; subsequent review regressions add unchanged CRLF and later-completed failure cases, each recorded RED then GREEN.
- Independent initial review found CRLF normalization false touches and command-start timestamp false VERIFIED. Both fixed; final review Approved, no outstanding code findings. CRLF reads now binary then explicit UTF8 decode; req outcomes stamped at completion while retaining pre-run input fingerprints.
- Final source tree d17338e: converge R1-R8 8 PASS, 0 FAIL, 0 MANUAL. Trace spec/plan/tests PASS8. diff whitespace PASS; scan zero Critical, three no-direct-assert heuristics independently reviewed as false positives (helpers assert CLI outcome/state).
- Original mutation baseline PASS, 12/13 killed. Strengthened block-only assertion and new review regressions: targeted5/5 confirmed and killed, including originally surviving block mutant. Preserve mutations-2.json and mutations-2-targeted.json/logs. Combined evidence covers all15 distinct variants; no need repeat unchanged variants.
- Retrospective closed with lesson1 (pre-execution fingerprints; final convergence snapshots cannot stand in for them).
- Final framework gate delegated to mutation_validation agent: `lifecycle.py run assurance-2-framework -- python3 .ai/scripts/run_tests.py -j 8`; result pending when this handoff was drafted. Check its log/result before any rerun. Source frozen; no source edits during gate.

## Full-gate integration repair

Initial framework gate d17338e: 737 tests in61.3 seconds, one failure. Increment7 ReportOnlyTests permanently compared protected sources to HEAD, rejecting intended increment2 changes. Focused RED pinned it; repaired test asserts existing observed() before/after protected invoking-source bytes and path presence, not a permanent freeze against HEAD. Focused GREEN; confirmed measurement source-write mutant rejected by the same assertion (mutation-measure-integration-2.json). Measurement implementation/expected counts unchanged. Independent narrow re-review Approved and updated review-2.md recorded.

New frozen source a491524: refreshed convergence8PASS/0FAIL/0MANUAL. Corrected framework suite delegated and running; preserve first failure log framework-2.log, use framework-2-final.log for final result. Consult reuse before any rerun. This required test-file compatibility repair extends the planned file list without changing approved behavior.

## Required external verification blocker

AGENTS.md8.4 requires real-agent lifecycle evaluation for changed stage rules. It has NOT run and MUST NOT be represented as PASS or waived by independent review. Do not record Verify/Ship until this is resolved.

Claude installed2.1.312 with Pro/claude.ai subscription authentication. Existing `.ai/evals/checks/live_observer.py` pins Claude2.1.296 and rejects version drift before model launch; do not silently edit that unrelated operator policy.

Automatic approval review rejected this proposed command BEFORE process creation:

```text
python3 .ai/scripts/lifecycle.py run assurance-2-real-agent -- python3 .ai/scripts/lifecycle_eval.py run --scenario control-delta --scenario feature-l2 --evidence-class real-agent --agent-id claude --cli-version 2.1.312 --hook-activation project-and-observer --permission-configuration acceptEdits --observation-adapter live --timeout 300 --max-agent-seconds 600 --max-wall-seconds 660 --json docs/assurance/real-agent-2.json -- python3 /home/enramosjr/Projects/agentic-assurance-7/.ai/evals/checks/live_observer.py launch claude /home/enramosjr/.local/bin/claude
```

Stated rejection: authenticated external evaluation may transmit repository contents and consume subscription resources; approved plan left authorized zero-spend invocation unresolved, so destination and payload were not specifically authorized. No retry or indirect workaround is authorized. Complete local checks first, then request explicit authorization for qualifying the installed CLI and a bounded observed evaluation. Payload would be temporary evaluation fixture repositories and the copied framework kit; destination Claude/Anthropic via existing subscription, potentially consuming quota. No API billing or paid campaign is authorized. CLI/observer version compatibility also needs qualification before a model request.

## Next action

Final framework gate on a491524 PASSED: lifecycle.py run assurance-2-framework -- python3 .ai/scripts/run_tests.py -j8 exit0 (framework-2-final.log); final diff gate exit0. Do not repeat these unchanged checks. Full initial failure log retained; successful child output was suppressed, so do not invent a fresh test count. Current convergence8PASS/0FAIL/0MANUAL, Approved review recorded, retrospective closed. Verify/Ship NOT recorded because required real-agent evaluation remains blocked.

Await explicit user authorization to qualify installed Claude2.1.312/observer compatibility and run the two bounded external fixture evaluations using the subscription. If authorization is granted, establish compatible observation without weakening qualification or allowing paid API billing; run exact approved bounded commands and record real outcomes. Do not ask again for approved spec/plan decisions. No commit/push/PR/Git merge authorized. Until real evidence passes, describe local implementation/review/validation as complete but the task's Verify as blocked.

## Authorization update

The user answered "yes" to the explicit qualification/two-fixture Pro-subscription evaluation question. Destination Anthropic, copied framework/temporary fixture payload and subscription quota consumption are authorized; paid API billing/extra campaign/delivery remain unauthorized. Existing validation agent is qualifying a layout-preserving ignored operator copy with only the Claude version pin updated to2.1.312, including model-free native hook initialization and configuration freezing before launch. Preserve source a491524 and all earlier evidence.

Fresh-turn parent `lifecycle.py reuse assurance-2-framework` reports execution environment/runtime changed even though sources remain a491524; ledger context_digest hashes the full non-session environment. Do not misreport that command as REUSE/PASS. Prior full-suite PASS remains evidence for its recorded source/environment; do not rerun unchanged source suites merely for this chat turn. Audit is OK. No ledger behavior change is in scope.

## Authorized real run completed; next decision

The two authorized cells ran once each via sanitized Pro auth and qualified ignored observer. Original a491524 unchanged. Real observed Sonnet5.5/medium/CLI2.1.312 and qualified clean-copy provenance; results0PASS/2FAIL/0ERROR, charged64.57agent seconds. results-check --require-real PASS certifies record integrity/qualification only, NOT behavior. Both failed on native Write permission denial for fixture spec/plan docs, before implementation/review/assurance gate. Exact native logs/denial messages and inference about .git ancestors are in real-agent-2-diagnosis.json; summary real-agent-2-report.md. Do not retry under exhausted original two-cell allocation or claim Verify.

Model-free operator/provenance independent review Approved (operator-review-2.md); all138copy files bytes/modes audited. Full failed run and source checkout remain preserved. No original-source commit/push/PR/merge.

Prepared LOCAL alternative: ignored operator-2-retry/frozen-source with sibling git-metadata, initialized with Git --separate-git-dir. Unchanged scratch.directory resolves sibling metadata/okf-scratch, disk-backed, and example fixture/knowledge paths have no literal .git ancestor. Same source bytes/modes and clean policy/evaluator/corpus provenance verified. No observer/guard/permission weakening and no model calls. Native Write remedy is explicitly unverified. `lifecycle.py run assurance-2-retry-layout -- python3 docs/assurance/prepare-retry-layout-2.py` PASS; preparation.json, planned-evaluation-command.json and real-agent-2-retry-preparation.md contain exact evidence. Future guarded entrypoint run-real-agent-2-retry.py --authorized has NOT run and needs fresh explicit consent for another two bounded cells (same300/cell,600agent,660wall,subscription-only,no fallback/retry). Keep all old result files immutable.

Current next action: await that new two-cell authorization. Source Verify/Ship remain unrecorded because required real behavioral evaluation failed. Do not repeat spec/plan approvals or local suites. Any successful authorized retry should record actual evidence without erasing original failure and must clear the current failed real-agent ledger obligation honestly before Verify.

## Retry authorization and completed outcome

User subsequently answered yes to the two additional tests. Exact prepared outside-.git retry executed once (same semantic ledger label assurance-2-real-agent), original results immutable. Source a491524 unchanged. Both fixtures implemented behavior, passed convergence, delegated a reviewer and recorded Verify, resolving the earlier native Write blocker for this run. Nevertheless strict evaluator0/2PASS, both FAIL only `Approved review artifact is not bound to the observed reviewer result`; charged154.572agent seconds within600. Qualified results-check --require-real PASS is integrity-only, not behavioral PASS. No further allocation/retry authorized.

Pinned cause from native logs: feature parent added title/provenance prefix to otherwise exact report; saved body hash differs from observed/raw reviewer. Control reviewer returned prose `Verdict: Approved` without canonical `## Verdict`; observer correctly has no canonical report, while parent rewrote it into sections. Preserve real-agent-2-retry.json, retry log, real-agent-2-retry-diagnosis.json, real-agent-2-retry-binding-diff.json and binding diffs. Do not repair artifacts or rescore them to PASS.

Current next decision: address canonical reviewer formatting and verbatim parent report preservation before another evaluation. The original increment2 spec/plan remain approved and all local acceptance/review/framework checks pass, but global Verify/Ship NOT recorded and failed current real-agent ledger obligation remains honest. No source commit/push/PR/Git merge. Do not launch more model cells or silently broaden increment2 to change reviewer/evaluator contracts; clarify the focused remediation scope first.

## Report-contract instruction repair completed locally

User requested "continue". Analyst confirmed existing canonical template and strict bodyhash contracts already require this behavior; no new policy/spec semantics were introduced. Keep original approved spec2/plan2 hashes unchanged. Implementation detail in plan-2-review-report-addendum.md. Mandatory reviewer Completion report loads in Claude/Codex; canonical complete final Markdown/no preface/fence; parent entire body unchanged/YAML metadata outside only/reviewer correction instead of parent verdict repair. Production scorer/observer/hash code unchanged.

Current frozen candidate6ad08d1: new instruction conformance RED then GREEN, direct strict-binding regression PASS (intact/YAML pass, parent prefix/rewrite/verdict fabrication fail exactbinding despite auditclean), six confirmed mutation controls allkilled with copied baselinesPASS; refreshed R1-R8converge8PASS/0FAIL/0MANUAL. Independent review Approved saved ENTIRE returned body unchanged to review-2-report-contract.md, equalityverified, review stage recorded. Fullsuite framework-2-report-contract.log exit0 and finaldiff exit0. Existing retrospective closure lesson1 retained. Source checkout uncommitted.

No additional model calls occurred during repair. Failed prior real results stay FAIL. Verify/Ship remain unrecorded until passing required real adherence evidence. Local/no-model preparation of a fresh outside-.git layout and guarded operator-2-report-contract follow-up command is underway to make a potential new two-cell request concrete. Await explicit new allocation before launching it; old allocation exhausted. No need repeat spec/plan approvals or local gates while candidate unchanged. No commit/push/PR/merge authorized.

Follow-up local preparation is now PASS on6ad08d1, report real-agent-2-report-contract-preparation.md and operator-2-report-contract/preparation.json/planned-evaluation-command.json. Exact fresh KIT bytes/modes, clean provenance, .git-free disk-backed paths; unchanged qualified observer/config/guards/permissions. Guarded future command: `python3 .ai/scripts/lifecycle.py run assurance-2-real-agent -- python3 docs/assurance/run-real-agent-2-report-contract.py --authorized`. It has NOT run, creates only separate real-agent-2-report-contract.json, refuses drift/existingresults/changed agent pins, requires sanitized Pro auth and exactly2cells300/cell600agent660wall. No model/campaign result created by preparation. Explicit new user authorization remains required before that command.

## Latest authorized allocation completed

User approved the prepared pair; exact command above executed once and is terminal (do NOT rerun guarded entrypoint). Source6ad08d1 unchanged. Real outcome1PASS(feature-l2)/1FAIL(control-delta)/0ERROR; charged245.440seconds within600. Qualified-results integrity PASS only. Feature passed strict report bodyhash, reviewer identity/read-only/candidate/order and lifecycle/behavior checks.

Control failed correctly: canonical reviewer reran mutating converge during read-only review, changing convergence pin (source/spec/plan unchanged); parent then rewrote the reviewer-authored report to a short body with a different hash and reran converge after Verify. Pin chronology and exact body/hash differences recorded in real-agent-2-report-contract-{order,binding-diff}.json and full real-agent-2-report-contract-report.md. No observer/scorer relaxation, post-run artifact repair or false PASS. Instructions now work in feature case but did not prevent control-session noncompliance.

CURRENT STATE: local instruction repair+acceptance+mutation/fullsuite+independent review PASS; required real obligation remains FAIL on current6ad08d1, so main Verify/Ship NOT recorded. All three two-cell allocations exhausted. No new model calls/campaign or further source patches prepared. Next decision is whether to scope mechanical read-only and verbatim-report enforcement; do not keep stacking instruction patches/retries without that decision. Preserve all original failures/results/logs and uncommitted source; no commit/push/PR/merge authorization. Original spec2/plan2 remain approved but broader enforcement would need lifecycle scope/spec treatment.
