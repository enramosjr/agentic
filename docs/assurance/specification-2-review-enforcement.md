# Spec: mechanically bound review — approved supplement

Approved by human:enramosjr, 2026-10-28. L2, Python principal engineer. User selected opt-in activation, Claude and Codex together, and all-writer protected-mutation freeze during review. Codex installed-runtime schema/discovery scoping completed without model calls; native capture execution remains unverified. Implementation requires an approved plan. No new external allocation is authorized by this spec approval.

## Problem and outcome

On source6ad08d1, feature-l2 passed strict native review evaluation but control-delta failed: a reviewer ran mutating converge, the parent rewrote its canonical report, and convergence ran again after Review/Verify. Instruction-only repair did not prevent those ordinary mistakes. The new mechanism must prevent protected mutations during review, bind saved reports to actual native reviewer output, and reject stale review/verification claims without weakening evaluation.

This supplements the existing approved assurance spec2 R1-R8. Preserve that implementation, original spec/plan hashes, measurement behavior and all prior passing/failed evidence. Existing failed real-agent results remain FAIL. Framework source has no knowledge bundle; working documents stay ignored under docs/assurance.

## Users and scenarios

Maintainers and agents request mechanically bound independent review in a capable native harness. The reviewer inspects a frozen task candidate; parent and reviewer cannot run protected workflow producers during that interval. The native completion captures the actual report; the parent persists the same body and records Review. Later reviewed-candidate changes require renewed review. Interrupted sessions remain unqualified and can be explicitly abandoned/restarted.

## Requirements

- R1: Mechanically bound review MUST be explicit opt-in for a task; tasks that do not opt in MUST retain existing review behavior without a mechanical-provenance claim. Opted-in tasks MUST require a supported native adapter and task-bound observed reviewer identity/start/completion. Parent-supplied role labels, report text or hashes alone MUST NOT establish independent provenance. Unsupported or conflicting capture MUST refuse mechanical qualification with an actionable diagnostic; historical records MUST NOT be rewritten or silently upgraded.
- R2: Claude and Codex native adapters MUST both support reviewer start/completion capture in this increment. Native reviewer start MUST capture task/reviewer identity and reviewed source, approved-spec, plan and exact convergence pins under the existing lock/record/scratch machinery. Missing identity, concurrent overlapping review or another task's receipt MUST NOT establish a qualified interval. Its own capture bookkeeping MUST NOT count as a reviewer mutation or stale its own pins. A runtime lacking a required capability MUST refuse the mode; one working adapter MUST NOT be presented as completion of both.
- R3: During an active mechanically tracked review interval, protected mutations from ALL actors in that worktree MUST refuse before commands execute or evidence is published, including lifecycle converge/run/assure-run/stage/merge operations and recognized source, Markdown and deletion edits. Read-only commands MUST remain available. The guard MUST cover supported direct workflow CLI entrypoints as well as supported harness hooks; merely refusing a known tool spelling while allowing its normal direct CLI path is insufficient. Native capture/completion bookkeeping and explicit recovery MUST remain usable.
- R4: Native completion MUST capture the actual complete canonical reviewer report and its verdict, body hash, identity and reviewed pins. Missing completion, malformed report, changed candidate or incomplete identity MUST remain unqualified. Existing YAML-frontmatter/body-hash semantics MUST remain unchanged; no formatting, summary or reconstructed verdict may substitute for reviewer-authored output. Capture/publishing order MUST not falsely classify trusted capture bookkeeping as a reviewer write.
- R5: Recording mechanically bound Review MUST require its saved artifact body to match that native captured body hash, an approved canonical verdict and unchanged reviewed pins. Prefixes, summaries, rewritten verdicts, missing capture and another session/task's report MUST refuse. The parent MUST NOT turn a malformed handback into independent approval. Canonical corrections MUST originate from the reviewer under a valid capture interval.
- R6: Source, approved-artifact or exact convergence changes after review MUST invalidate Review/Verify for advancement and surface a precise freshness diagnostic. Verify, Ship and commit/PR guards MUST not rely solely on recorded stage presence. Append-only validation results required after review MAY be recorded without invalidating review when they change none of the captured evidence or candidate pins; existing current-failure checks remain required. This exception MUST NOT permit replacing the reviewed convergence receipt or changing previously reviewed evidence.
- R7: Interrupted reviews, missing events, malformed receipts and changes during an interval MUST not yield approval. Explicit abandon/restart MUST preserve unsuccessful history and require a new independent completion. Concurrent starts/completions MUST use locking so no task consumes another reviewer's receipt. Existing valid source/spec/plan/convergence and assurance prerequisites MUST remain required.
- R8: Integration docs and tests MUST describe activation, supported adapters, protected mutation scope, capture, exact preservation, invalidation, recovery and limits. The mechanism MUST remain ordinary-mistake protection in a user-writable workspace, not claim an arbitrary-shell sandbox or unforgeable identity. Existing real-agent failures, scoring, native observer acceptance and strict report binding MUST remain unchanged; local deterministic checks MUST NOT be described as a passing real-agent campaign.

## Acceptance

The following NEW proposed classes in `.ai/scripts/tests/test_review_enforcement.py` must drive actual workflow CLI entrypoints and supported native hook payloads in temporary repositories, asserting command outcomes, side-effect absence and recorded state. Adapter contract tests use captured/synthetic payloads and are not real-agent adherence claims.

- R1: `python3 -m unittest discover -s .ai/scripts/tests -p test_review_enforcement.py -k ActivationTests` asserts the selected rollout, unsupported/missing native identity refusal, no parent-assertion substitution and historical compatibility.
- R2: `python3 -m unittest discover -s .ai/scripts/tests -p test_review_enforcement.py -k IntervalTests` asserts exact task/reviewer/candidate pins, overlap refusal, isolation and no self-invalidation from capture bookkeeping.
- R3: `python3 -m unittest discover -s .ai/scripts/tests -p test_review_enforcement.py -k ReadOnlyTests` asserts protected direct/recognized wrapped producers execute no command and publish no evidence, source/Markdown/delete hooks deny, and readers/capture/recovery remain usable under the selected freeze policy.
- R4: `python3 -m unittest discover -s .ai/scripts/tests -p test_review_enforcement.py -k CaptureTests` asserts actual native completion body/verdict/pins, missing/malformed/conflicting capture refusal and canonical reviewer correction; bookkeeping cannot look like source mutation.
- R5: `python3 -m unittest discover -s .ai/scripts/tests -p test_review_enforcement.py -k PreservationTests` asserts intact/YAML bodies qualify while prefixed/rewritten/fabricated/mismatched/missing reports refuse without recording Review.
- R6: `python3 -m unittest discover -s .ai/scripts/tests -p test_review_enforcement.py -k FreshnessTests` asserts reviewed source/spec/plan/convergence changes invalidate advancement and status diagnostics, including post-Verify changes; valid append-only post-review validation does not create a review loop or bypass existing failure checks.
- R7: `python3 -m unittest discover -s .ai/scripts/tests -p test_review_enforcement.py -k RecoveryTests` asserts interruption, malformed receipt and concurrent/mismatched completion never produce approval; explicit recovery retains unsuccessful history and requires a new capture.
- R8: `python3 -m unittest discover -s .ai/scripts/tests -p test_review_enforcement.py -k CompatibilityTests` asserts adapter declarations/docs and legacy behavior follow the approved policy, historical failures stay unchanged and existing strict mismatch controls remain active. The final framework gate must also cover existing assurance and lifecycle suites.

## Constraints

Standard library/Python floor and existing locking/record/scratch conventions. Reuse the existing stage/ref and canonical hash semantics. No scoring relaxation, silent parent attestation, report repair or retrospective rescoring. Do not modify source6ad08d1 until approved spec/plan stages permit it. Preserve all current changes; no new worktree, commit, push, PR or Git merge. Real native verification remains required for lifecycle/hook changes but needs its own explicit external allocation; none is granted here.

Adapter qualification MUST distinguish accepted event schemas/discovery from enabled, trusted execution and actual native report capture. Registration alone MUST NOT be reported as working capture. Persisted/configured thread model or effort metadata MUST NOT be described as per-turn execution telemetry. Capability/trust diagnostics must preserve these evidence boundaries rather than silently relaxing mode qualification.

## Non-goals

Hostile-process security, OS-wide filesystem sandboxing, authentication against deliberate local record forgery, arbitrary-shell static analysis, unrelated assurance increments, and universal harness support without demonstrated native capabilities.

## Assumptions

Native callback/transcript provenance is trusted within the declared adapter boundary; the local workspace and hooks remain user-writable. A protected review freezes the candidate, not every temporary test artifact on the machine. Parent post-review validation is necessary under the existing lifecycle, so append-only validation must not automatically force endless re-review. Adapter bookkeeping must preserve that distinction and remain auditable.

## Open questions

None. The user selected opt-in activation, Claude and Codex native integrations together, protected-mutation freeze for all writers during active review, and approved this spec. Installed-runtime capability checks establish feasibility; actual native execution must still be verified before completion. Unavailable capabilities must be reported, never substituted with parent assertions.

## Source evidence

- `.ai/scripts/lifecycle.py:1579-1602` stage-based edit guard; Markdown exemption. `:1730-1732` ordinary-shell early return. `:1875-1883` nested-run mutation classification/locking. `:1155-1180` convergence freshness does not bind Review to the exact reviewed receipt.
- `.claude/settings.json`, `.codex/hooks.json`: deployed pre-tool/session hooks lack reviewer start/completion capture.
- `.ai/evals/checks/live_observer.py:128-151`: existing native identity/role/report observation example; evaluation integration is not deployed enforcement.
- `docs/assurance/real-agent-2-report-contract-report.md`, binding/order diagnostics: actual candidate mutation and report rewrite; feature case proves strict binding can pass. These records remain immutable.
- Official OpenAI Hooks documentation: https://learn.chatgpt.com/docs/hooks — native subagent start/stop identify the agent and profile; stop can carry the latest assistant message or transcript path. Completion text is nullable and transcript format is not a stable interface, so adapters must qualify capabilities and refuse missing evidence.
- Official OpenAI App Server documentation: https://learn.chatgpt.com/docs/app-server — hook discovery and stored-thread reads are available without starting a turn. Documentation/schema discovery is not actual native-event execution proof.
- `docs/assurance/codex-capability-scope-2.md` and its summary/requests/responses/generated schema: installed0.162.1 accepted explicit start/stop registrations and listed them enabled, with trustStatus untrusted, no config errors or trust bypass. Only initialize, hooks/list and config/read requests ran; no thread/model start, provider inference or quota was requested. Actual event firing/capture and trust activation remain unproven. Schema labels thread model/effort as persisted/configured metadata, not per-turn telemetry.
