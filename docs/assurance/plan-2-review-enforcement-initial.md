# Implementation Plan: mechanically bound review

Proposed for human approval. Implements approved specification-2-review-enforcement.md R1-R8. Preserve original6ad08d1 source, assurance artifacts and all prior results. L2; Python principal engineer. No new worktree, delivery operation or external model allocation.

## Objective

Provide explicitly opted-in native independent-review enforcement for Claude AND Codex: freeze protected writers, capture the actual report, require exact preservation and reject stale approval. Preserve legacy review behavior outside the mode and existing strict scoring.

## Success criteria

- R1-R2: activation and interval qualification use supported native callbacks, task identity and exact reviewed pins.
- R3: supported protected writers refuse before effects during active review, including direct workflow CLI invocation.
- R4-R5: completion captures the canonical reviewer-authored report; saved Review matches that exact body and reviewed candidate.
- R6-R7: advancement checks freshness; legitimate append-only validation works; interrupted attempts recover explicitly without fabricated approval.
- R8: both integrations, docs, deterministic tests and honest native-verification limits are complete.

## Current state

- lifecycle.py provides state_lock, atomic save, task identity and locked evidence reload/append. Its main classifies mutations, while hook_problem is stage-based and exempts Markdown. cmd_hook bypasses ordinary shell commands and legacy bypass variables before review-aware inspection.
- Review accepts a saved verdict without native capture. Convergence freshness does not bind recorded Review to its exact receipt. lifecycle.save publishes adopter records inside the workspace, which the unchanged observer would detect as a review-interval mutation.
- okf.py direct producers and other workflow writers have no shared review guard. lifecycle already imports okf, so adding the reverse import would create a cycle.
- Claude/Codex hook registrations lack native reviewer start/completion capture. Installed Codex0.162.1 accepts/discovers those events but reports them untrusted; execution/capture remain unproven. See codex-capability-scope-2.md.
- Existing native evaluation/scoring/body-hash logic remains unchanged. Earlier real failures are historical evidence, never rescored.

## Proposed approach and components

- NEW .ai/scripts/review_guard.py: low-level stdlib/scratch module, importing neither lifecycle nor OKF. Owns per-worktree journal/lock, producer leases, receipt validation and freshness comparison.
- NEW .ai/scripts/review_native.py: bounded Claude/Codex callback normalization, canonical completion validation and native callback CLI. Lifecycle supplies task/candidate snapshots without an import cycle.
- lifecycle.py: activation/status/recovery/report-copy orchestration, stage and advancement checks. Other supported producer entrypoints depend only on the low-level guard.

New proposed CLI:

```text
lifecycle.py review enable --adapter claude|codex --session NATIVE_PARENT_SESSION --report NEW_REPORT.md
lifecycle.py review status
lifecycle.py review save-report
lifecycle.py review abandon --reason TEXT
lifecycle.py review restart --report NEW_REPORT.md
```

The session option selects an already observed native session; it is not proof by itself. No parent-facing approve/complete/supply-hash command exists. Native registrations call `python3 .ai/scripts/review_native.py hook --adapter claude` or codex. Missing, unsupported, untrusted or incomplete native capability evidence refuses qualification; no trust bypass is introduced.

## Journal and candidate

Operational capture lives only under Git scratch, keyed by canonical worktree identity AND task: `okf-scratch/review/<worktree-id>/<task-id>/`. A versioned journal records adapter/parent/task, reserved report destination, active interval, unsuccessful history and qualified completion. Each interval binds child identity, native event/order identifiers, times, candidate pins, outcome and raw captured report path/hash/verdict.

Start/stop never call lifecycle.save or publish workspace records. The normal parent Review publication later records qualified receipt identity/pins. This keeps expected capture bookkeeping outside the observer's workspace mutation fingerprint.

Candidate pins cover tracked/nonignored untracked source content, including governance Markdown, deletion, modes and symlink changes; explicit approved spec/plan body hashes including ignored refs; exact convergence and reviewed entries; and the reviewed evidence prefix. Exclude Git scratch, generated lifecycle receipts and ONLY the reserved report path. tree_hash alone is insufficient because of its Markdown exemptions.

Reserve a fresh untracked .md report destination inside the worktree, without symlink components. It cannot be a tracked source, approved ref or reviewed command input. Only exact capture-copy may create it after completion; an existing different file refuses. Restart requires a fresh destination.

## Boundaries, locking and invariants

Use short per-worktree guard transactions and producer leases:

1. Register a protected writer lease BEFORE effects.
2. Native start requires no interval and no live or unresolved writer lease.
3. Run the command without holding a file lock; its lease prevents review start.
4. Publish/release through checked transactions.
5. Native completion rechecks pins and closes under the same guard lock.

For recognized native edit/shell producers, PreToolUse registers a lease and matching PostToolUse releases it. Missing post-event leaves an unresolved lease requiring explicit recovery. Lock order: guard lock THEN lifecycle state lock; never acquire guard under state. Same-process nested operations reuse a lease; legitimate child workflow producers register their own. No file lock is held while waiting on a subprocess.

Opted-in active freeze is checked BEFORE legacy LIFECYCLE_GUARD/OKF_AUTONOMOUS bypasses. Opt-out historical tasks keep existing behavior. Unknown shell programs, arbitrary Python writes and deliberate local forgery are outside this ordinary-mistake boundary; completion still rejects changed candidate pins. Separate test repositories/scratch remain usable. No OS sandbox claim.

## Native adapters

Register SessionStart, SubagentStart, SubagentStop and relevant Pre/PostToolUse for both harnesses. Normalize actual session, native child ID/profile, worktree, event and completion text. Require distinct child and native reviewer profile. Parent labels alone never qualify.

Prefer actual last_assistant_message in native stop data. Nullable/missing output refuses. Do not guess unstable transcript formats; future transcript fallback requires demonstrated versioned support. Canonical output contains # Review Report and existing ordered sections/explicit verdict. Keep current body/frontmatter hashing unchanged. Store malformed/nonapproved completion honestly. Identical duplicate callbacks may be idempotent; conflicts, overlap, wrong task/session, missing start or changed pins refuse. Persisted/configured model/effort are not per-turn telemetry.

## Supported protected writer matrix

Guard direct entrypoints before handler effects, plus producer function boundaries used by supported internal workflow calls:

- lifecycle.py: mutating tier/stage/redgreen/run/converge/merge/learn/retire/promote/retrospect/finish-apply and assure-run; genuine dry-run/report variants remain readable.
- okf.py: init/onboard/new/set/stamp/log, reindex except --check, queue archive/record-session, git-setup and merge-driver. Pure list/show/search/context/validate/records/affected/sync-check, queue reads, checkpoint and handoff remain readable.
- install.py: installation into the protected worktree; --check remains readable.
- autonomy_driver.py: before producer-session start.
- pr_sync.py: before fetch/trial merge/push; its dry-run is not purely read-only.
- artifacts.py: freeze/variant/command-running producers; verify remains readable.
- autonomy_validation.py: producer registration/submission.
- completion.py: apply paths/direct stage-Verify calls and freshness in reports.

Harness hooks deny recognized file edits/deletions, including Markdown, and recognized wrapped producers from every actor during an interval. Do not rely only on a tool/command spelling when a supported normal CLI path performs the same mutation. Document the exact matrix and unsupported arbitrary-shell boundary.

## Implementation steps

### Step 1: opt-in activation and isolated journal — R1, R2, R7

Files: new review_guard.py, lifecycle parser/commands, new test_review_enforcement.py. Write ActivationTests, basic IntervalTests and recovery-schema tests FIRST. Implement versioned scratch state, native-session registration, task opt-in, strict capability/trust checks and safe fresh report reservation. Test legacy records, missing/unsupported runtime/session, wrong task, malformed journal and absent identity. Native start requires current approved refs and exact successful convergence. Record focused RED/GREEN.

### Step 2: supported writer freeze without races — R2, R3, R7

Files: guard, lifecycle dispatcher/hooks, OKF and listed producer entrypoints, native registrations. Write ReadOnlyTests and concurrency IntervalTests FIRST. Implement leases, pre/post tracking and lock order. Exercise direct CLI and recognized wrappers for parent/reviewer/unrelated actors; assert no command execution, no evidence/source mutation and available readers. Test both race orders: writer before start, start before writer. Retain unresolved leases after interruption. Record RED/GREEN.

### Step 3: both native captures and exact report preservation — R2, R4, R5

Files: review_native.py, Claude/Codex hook configs, lifecycle review commands/stage. Write CaptureTests and PreservationTests FIRST using bounded captured/synthetic payload families for BOTH adapters. Implement scratch-only native capture and canonical validation; save-report copies exact bytes/body without reconstruction. At stage review require matching task/interval/native identities, approved canonical verdict, saved body hash and unchanged pins. Test intact/YAML success; prefix/summary/verdict rewrite/fabricated hash/missing stop/conflicting duplicate/wrong session refusal. Corrections require a valid reviewer capture interval. Record RED/GREEN.

### Step 4: advancement freshness and legitimate validation — R5, R6

Files: lifecycle stage/gate/status/hook paths, completion reports, guard comparisons. Write FreshnessTests FIRST. Check qualification at Review, Verify, Ship, status/completion and commit/PR hooks; identify source/spec/plan/convergence/evidence drift. Allow append-only post-review validation only if reviewed ledger prefix is unchanged, reviewed labels/convergence are not replaced, and existing current-failure checks still pass. Bounded-ledger truncation that loses reviewed prefix refuses. A convergence rerun ALWAYS stales the reviewed receipt, even on success.

Compare reviewed source content rather than raw HEAD alone so unchanged shipping commits stay valid. Before commit ensure staged protected content matches reviewed candidate, preventing a stale index from delivering different bytes. Record RED/GREEN.

### Step 5: explicit interrupted recovery — R7

Files: review commands/journal transitions. Complete RecoveryTests FIRST. abandon preserves unsuccessful outcome/reason and releases without approval; restart retains history, checks prerequisites and reserves a new path. Opt-in cannot silently downgrade to legacy. Reject late abandoned callbacks. Clearing an unresolved writer lease requires proof that producer stopped; otherwise refuse. Record RED/GREEN.

### Step 6: docs, connected E2E and compatibility — R8

Files: .ai/lifecycle.md, reviewer role/registrations, review skill, relevant hook/setup docs and conformance tests. Write CompatibilityTests FIRST. Document activation/trust distinction/capture/freeze matrix/report copy/freshness/append-only validation/recovery/limits. Preserve original assurance behavior, strict outcome checks, observer/hash code and every old real result.

Narrow E2E for EACH adapter family: enable → native start → blocked direct producer/Markdown edit with no effects → native completion → exact report save → Review → append-only passing validation → Verify → reject candidate drift → abandon/restart and reject stale completion. Synthetic callbacks prove the workflow contract, not actual native event delivery.

## Testing strategy and mutation proofs

Eight classes map to spec R1-R8: ActivationTests, IntervalTests, ReadOnlyTests, CaptureTests, PreservationTests, FreshnessTests, RecoveryTests, CompatibilityTests. Unit tests cover deterministic parsing/comparison; real temporary-repository CLI/hook tests assert final state/effects. RED before logic, GREEN after. Confirm applied bytes before every broken-variant result.

Mutation families: missing activation/native capability/identity; missing overlap/lease check; direct lifecycle/OKF bypass; Markdown or legacy-bypass exemption; capture published into workspace; parent hash accepted as native; prefix/malformed verdict accepted; omitted source/spec/plan/convergence pin; rewritten reviewed ledger or allowed convergence rerun; valid validation falsely staling review; abandoned/wrong-task completion accepted; either adapter missing.

## Validation commands

Focused commands are the eight exact spec acceptance commands, selecting one class with -k. Narrow completed-slice E2E:

`python3 -m unittest discover -s .ai/scripts/tests -p test_review_enforcement.py`

Trace/converge:

- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-2-review-enforcement.md --plan docs/assurance/plan-2-review-enforcement.md --tests .ai/scripts/tests/test_review_enforcement.py`
- `python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-2-review-enforcement.md`

After independent review/fixes and frozen candidate, full gate ONCE:

- `python3 .ai/scripts/lifecycle.py run review-enforcement-framework -- python3 .ai/scripts/run_tests.py -j 8`
- `python3 .ai/scripts/lifecycle.py run review-enforcement-diff -- git diff --check`
- `python3 .ai/scripts/lifecycle.py scan-diff`

Record focused/E2E/mutation checks through lifecycle evidence commands; reuse before repeats. Do not rerun unchanged old campaigns or rescore their failures. Delegate long gates or use background wait_check under validation policy.

## Review and native-verification prerequisites

Independent read-only review must examine coverage, lock order, identity, self-generated bookkeeping and validation compatibility; save returned body unchanged. Close findings before final gate.

Actual trusted activation, start/stop/report delivery and unchanged strict observer outcomes for BOTH Claude and Codex are required before completion. Schema/discovery acceptance, untrusted registrations, synthetic callbacks or persisted model configuration do not suffice. No new external allocation exists; implementation/deterministic checks may proceed after plan approval, but actual native verification and final completion wait for separately authorized execution. Missing/untrusted native capabilities refuse rather than silently qualify.

## OKF impact

Framework has no knowledge bundle; do not initialize one. Update existing source integration docs, keep specs/plans/reviews/evidence ignored under docs/assurance and receipts in Git scratch. affected/records no-bundle results are inapplicable, not PASS. Preserve old PASS/FAIL evidence and close retrospective before Verify.

## Risks and mitigations

Guard/start race: producer leases and fixed lock order. Self-invalidation: callback bookkeeping scratch-only and exact safe report reservation. Broad writer surface: explicit entrypoint matrix/function boundaries and per-entrypoint negative controls. Nullable/untrusted native data: fail-closed diagnostics and real qualification. Validation loops/ledger truncation: reviewed-prefix invariance with explicit append exception and refusal when prefix is lost. Local bypass/forgery: honest ordinary-mistake boundary, no OS sandbox claim.

## Out of scope

Scorer/observer/hash relaxation, retrospective rescoring, hostile-process security, arbitrary-shell analysis, unsupported harness success, other assurance increments and source delivery.

## Open decisions

None concerning intended behavior. This plan is proposed for human approval. Trusted activation and separately authorized real execution for both adapters remain verification prerequisites; missing fields/delivery are failures to report, not permission to substitute parent assertions.
