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

Candidate pins cover tracked/nonignored untracked source content, including governance Markdown, deletion, modes and symlink changes; explicit approved spec/plan body hashes including ignored refs; exact convergence and reviewed entries; and an immutable archived reviewed ledger window plus exact append-transition proof. Exclude Git scratch, generated lifecycle receipts and ONLY the reserved report body; separately pin its immutable metadata. Do not exempt indexes or logs. tree_hash alone is insufficient because of its Markdown exemptions.

Prepare the fresh report destination BEFORE arming review, under an owned producer lease. Reject symlinks, tracked/pre-existing sources, approved refs and explicitly named file dependencies. A broad glob such as Python's inferred Inputs ['**'] does not by itself forbid reservation; it overapproximates dependencies. Do not change ledger hashing or silently exclude the report from command inputs.

For an adopter, create a draft type:Review scaffold inside knowledge/ through existing OKF creation/reindex operations, with an honest pending body that cannot qualify as Approved. Prepare the pending log entry and current lifecycle record directory/index administration now. Freeze the report frontmatter and surrounding index/log fingerprints before native start. Framework mode prepares an equivalent ignored working report without creating knowledge/.

Exclude ONLY the exact reserved report body from candidate comparison; separately pin its immutable frontmatter. Do not exempt indexes, logs, capability docs or arbitrary Markdown. Native start/stop remain scratch-only, leaving that scaffold unchanged throughout review. After completion, save-report replaces only the pending body with the captured body, preserves metadata/indexes/log, performs no stamp/reindex/log/publication, and rejects conflicting content. Identical export is idempotent. Restart reserves a fresh destination and retains unsuccessful history. A later delivery-log change is ordinary reviewed-corpus drift, not an implicit exemption.

Because hashing is unchanged, report export may stale older broadly scoped validation/req evidence. Refresh needed validation by appending its real result after review, preserving the exact convergence receipt and captured entries. Ordinary validation can use a new label; stable req:ID may append a newer entry with the same label because evidence identity is the concrete receipt, not the label alone. Existing failure/freshness checks still apply. Do not claim stale historical validation is current or rerun convergence to repair this expected publication effect.

## Boundaries, locking and invariants

Use short guard transactions and explicit owned/borrowed lease contexts. An owner registers worktree identity, unique lease ID/nonce and process identity BEFORE effects, then releases the guard lock and performs its transaction with state locking as needed. Only that owner releases its lease in finally; interruption leaves unresolved ownership. No guard lock is held while awaiting a subprocess. State-held synchronous children are allowed only after auditing that their entire borrowed path acquires neither guard nor state lock; otherwise release state before launch and reload under lock afterward.

Same-process nested operations borrow the active context. Synchronous same-worktree child CLIs inherit an internal descriptor and validate the atomically published owner/process identity WITHOUT acquiring guard or state locks. Invalid/expired/mismatched same-root ownership refuses before effects, never falls back to a new lease. Borrowers cannot release, replace or extend ownership. Normal owner release also requires proven borrower quiescence; surviving or unresolved borrowers leave ownership unresolved. Different fixture worktrees get independent ownership, not the ancestor's authority. Scoped propagation/restoration must not leak a descriptor to unrelated operations. This is ordinary-workflow metadata, not adversarial authentication.

Lock order remains guard THEN state. lifecycle.main establishes ownership before its state_lock branch. save uses that context; synchronous OKF reindex children borrow it without guard acquisition. OKF resolves its actual target root and borrows before mutating handlers. Direct producer functions assert ownership or establish it only before any state lock. completion.finish --apply establishes ownership before its apply transaction; apply_bindings, synchronous stamp/log children and direct cmd_stage(verify) borrow it. Direct stage calls still enforce protection/freshness. Metadata binding is ordinary corpus mutation, so post-review changes invalidate approval.

Native start/stop and recovery inspect the guard journal FIRST and refuse immediately on any live/unresolved writer; they never wait on state while a writer may hold it. Only a no-writer transition may obtain state for a read-only snapshot. Explicit recovery proves every granted producer stopped before clearing ownership; timeout or owner exit alone is insufficient. Register synchronous borrowers with process birth identity before granting effects, retain their registrations until completion, and refuse recovery while any borrower remains live or cannot be resolved. Native tool ownership binds the native invocation/session and host lifetime, never the short-lived hook subprocess PID; missing completion remains unresolved until native terminal evidence proves that invocation stopped.

Do NOT hold a lease around an entire driver or native model session. Driver PR sync, session count, queue/status/publication own their actual write transactions and release before native-agent launch/wait. Descendant workflow writers acquire their own leases. An asynchronous validation child acquires ownership before its first protected effect, holds through command/evidence publication and releases itself; its launcher never lends ownership that expires while the child runs. If review start wins first, the child refuses before execution. Scratch-only supervision/heartbeat bookkeeping cannot publish evidence or mutate corpus/source under its exception.

Opted-in active freeze is checked BEFORE legacy LIFECYCLE_GUARD/OKF_AUTONOMOUS bypasses. Opt-out historical tasks keep existing behavior. Unknown shell programs, arbitrary Python writes and deliberate local forgery are outside this ordinary-mistake boundary; completion still rejects changed candidate pins. Separate test repositories/scratch remain usable. No OS sandbox claim.

## Native adapters

Register SessionStart, SubagentStart, SubagentStop and relevant Pre/PostToolUse for both harnesses. Normalize actual session, native child ID/profile, worktree, event and completion text. Require distinct child and native reviewer profile. Parent labels alone never qualify.

Prefer actual last_assistant_message in native stop data. Nullable/missing output refuses. Do not guess unstable transcript formats; future transcript fallback requires demonstrated versioned support. Canonical output contains # Review Report and existing ordered sections/explicit verdict. Keep current body/frontmatter hashing unchanged. Store malformed/nonapproved completion honestly. Identical duplicate callbacks may be idempotent; conflicts, overlap, wrong task/session, missing start or changed pins refuse. Persisted/configured model/effort are not per-turn telemetry.

## Supported protected writer matrix

Guard direct entrypoints before handler effects, plus producer function boundaries used by supported internal workflow calls:

- lifecycle.py: mutating tier/stage/redgreen/run/converge/merge/learn/retire/promote/retrospect/finish-apply and assure-run; genuine dry-run/report variants remain readable.
- okf.py: init/onboard/new/set/stamp/log, reindex except --check, queue archive/record-session, git-setup and merge-driver. Pure list/show/search/context/validate/records/affected/sync-check, queue reads, checkpoint and handoff remain readable.
- install.py: installation into the protected worktree; --check remains readable.
- autonomy_driver.py: actual PR-sync, session-count, queue/status/publication write transactions; release before native-agent launch/wait, never a whole-session lease.
- pr_sync.py: before fetch/trial merge/push; its dry-run is not purely read-only.
- artifacts.py: freeze/variant/command-running producers; verify remains readable.
- autonomy_validation.py: producer registration/submission.
- completion.py: apply paths/direct stage-Verify calls and freshness in reports.

Harness hooks deny recognized file edits/deletions, including Markdown, and recognized wrapped producers from every actor during an interval. Do not rely only on a tool/command spelling when a supported normal CLI path performs the same mutation. Document the exact matrix and unsupported arbitrary-shell boundary.

## Implementation steps

### Step 1: opt-in activation and isolated journal — R1, R2, R7

Files: new review_guard.py, lifecycle parser/commands, new test_review_enforcement.py. Write ActivationTests, basic IntervalTests and recovery-schema tests FIRST. Implement versioned scratch state, native-session registration, task opt-in, strict capability/trust checks and safe fresh report reservation. Test legacy records, missing/unsupported runtime/session, wrong task, malformed journal and absent identity. Native start requires current approved refs and exact successful convergence. Record focused RED/GREEN.

### Step 2: supported writer freeze without races — R2, R3, R7

Files: guard, lifecycle dispatcher/hooks, OKF and listed producer entrypoints, native registrations. Write ReadOnlyTests and concurrency IntervalTests FIRST. Implement owned/borrowed leases and the concrete lock schedule above. Barrier tests cover state-locked save with synchronous child OKF reindex; finish-apply with stamp/log children and direct Verify; invalid inherited ownership; independent fixture roots; start/stop/recovery against executing/publishing owners; borrower release refusal; async validation/start races; and driver lease release before native-agent wait. Assert refusal or completion without deadlock or accidental owner release, plus no blocked command effects. Retain unresolved ownership after interruption. Record RED/GREEN.

### Step 3: both native captures and exact report preservation — R2, R4, R5

Files: review_native.py, Claude/Codex hook configs, lifecycle review commands/stage. Write CaptureTests and PreservationTests FIRST for BOTH payload families. Implement pre-start report scaffold/metadata/index/pending-log preparation, scratch-only capture and canonical validation; save-report changes only the reserved body. Review requires matching task/interval/native identities, approved canonical verdict, exact saved body and current pins. Test intact/YAML success and prefix/summary/verdict rewrite/fabricated hash/missing stop/conflicting duplicate/wrong session refusal. Adopter E2E proves pending scaffold passes OKF records but cannot approve, native events do not mutate workspace, exact export plus OKF records/Review/validation/Verify succeeds, and unrelated frontmatter/corpus/index/log changes reject freshness. Corrections require valid reviewer capture. Record RED/GREEN.

### Step 4: advancement freshness and legitimate validation — R5, R6

Files: lifecycle stage/gate/status/hook paths, completion reports, guard comparisons and an internal evidence-publication append wrapper. Write FreshnessTests FIRST. Check qualification at Review, Verify, Ship, status/completion and commit/PR hooks; diagnose source/spec/plan/convergence/evidence drift. Permit only exactly proven append-only post-review validation while retaining captured entry identity, rather than forbidding stable-label reuse. Existing current-failure and requirement-freshness checks remain required. A convergence rerun ALWAYS stales its reviewed receipt, even on success.

Archive the complete reviewed ledger window (at most ledger.MAX_ENTRIES entries) in the immutable review receipt at native start. Supported evidence publications use one internal wrapper around UNCHANGED ledger.append. Under the existing state lock, reload/validate the last proven window; atomically record a pending transition with sequence, previous-window digest, exact appended entry/batch, expected digest and exact evicted oldest prefix; publish expected state; then mark completed. Expected is precisely (previous_window + appended_entries)[-ledger.MAX_ENTRIES:], replaying actual append order. Its Git-scratch sidecar is serialized by state lock, not the guard-registry file; no guard reacquisition under state. The producer already owns/borrows its lease.

Before advancement, replay completed transitions from the immutable archive and require exact final-window equality. Reject arbitrary deletion/rewriting/reordering, middle eviction, unrecorded appends, skipped/reordered transitions or invalid payload/digest chains. Canonical oldest eviction is allowed because reviewed entries remain archived unchanged. Interrupted publication permits only exact previous state (preserve aborted transition) or exact expected state (explicitly finish publication); a third state refuses without repair. Resolve interrupted ownership first. Never infer legitimacy merely from a convenient suffix or synthesize append payloads.

Default-Python adopter E2E: prepare scaffold, run unittest through lifecycle.run without explicit inputs and assert inferred ['**', lifecycle-record exclusion], converge/capture/export/Review, prove old broad validation STALE, append a new-label validation and explicitly rerun a broad req:ID using the same stable label, preserve captured entries/archive/convergence, then OKF records and Verify pass without another review/export. Repeat with initially100 ledger entries, proving canonical oldest evictions and immutable archive. Negative controls cover report exclusion from command inputs, stale result treated current, changed convergence, failed refresh, tampered archive/eviction/chain, unrecorded append and interrupted third state. Test both legitimate interruption states and concurrent publishers serialized through state lock. No ledger/report hashing or scorer/observer semantics change.

Compare reviewed source content rather than raw HEAD alone so unchanged shipping commits stay valid. Before commit ensure staged protected content matches reviewed candidate, preventing a stale index from delivering different bytes. Record RED/GREEN.

### Step 5: explicit interrupted recovery — R7

Files: review commands/journal transitions. Complete RecoveryTests FIRST. abandon preserves unsuccessful outcome/reason and releases without approval; restart retains history, checks prerequisites and reserves a new path. Opt-in cannot silently downgrade to legacy. Reject late abandoned callbacks. Clearing an unresolved writer lease requires proof that every granted producer stopped; otherwise refuse. Barrier tests kill an owner while its registered borrower remains live and prove recovery refuses until both lifetimes resolve; native tests prove hook-process exit cannot unlock an outstanding invocation. Record RED/GREEN.

### Step 6: docs, connected E2E and compatibility — R8

Files: .ai/lifecycle.md, reviewer role/registrations, review skill, relevant hook/setup docs and conformance tests. Write CompatibilityTests FIRST. Document activation/trust distinction/capture/freeze matrix/report copy/freshness/append-only validation/recovery/limits. Preserve original assurance behavior, strict outcome checks, observer/hash code and every old real result.

Narrow E2E for EACH adapter family: enable → native start → blocked direct producer/Markdown edit with no effects → native completion → exact report save → Review → append-only passing validation → Verify → reject candidate drift → abandon/restart and reject stale completion. Synthetic callbacks prove the workflow contract, not actual native event delivery.

## Testing strategy and mutation proofs

Eight classes map to spec R1-R8: ActivationTests, IntervalTests, ReadOnlyTests, CaptureTests, PreservationTests, FreshnessTests, RecoveryTests, CompatibilityTests. Unit tests cover deterministic parsing/comparison; real temporary-repository CLI/hook tests assert final state/effects. RED before logic, GREEN after. Confirm applied bytes before every broken-variant result.

Mutation families: missing activation/native capability/identity; missing overlap/lease check; direct lifecycle/OKF bypass; Markdown or legacy-bypass exemption; capture published into workspace; parent hash accepted as native; prefix/malformed verdict accepted; omitted source/spec/plan/convergence pin; rewritten evidence or allowed convergence rerun; valid append-only refresh falsely staling review; abandoned/wrong-task completion accepted; either adapter missing. Also confirm child guard reacquisition under state, borrower owner-release, missing publication ownership, whole-session driver lease, scaffold metadata rewrite, blanket corpus exclusions, incorrect bounded eviction/transition chain and report exclusion from command inputs are rejected.

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

Guard/start race: owned/borrowed leases, explicit synchronous-child schedule and transaction-scoped driver writes. Self-invalidation: scratch-only capture plus pre-start scaffold/index/log preparation and body-only export. Broad writer surface: explicit entrypoint/function matrix and per-entrypoint negative controls. Nullable/untrusted native data: fail-closed diagnostics and actual qualification. Validation loops/truncation: immutable archive and exact unchanged ledger.append transition proof, with explicit interrupted-publication recovery. Local bypass/forgery: ordinary-mistake boundary, no OS sandbox claim.

## Out of scope

Scorer/observer/hash relaxation, retrospective rescoring, hostile-process security, arbitrary-shell analysis, unsupported harness success, other assurance increments and source delivery.

## Open decisions

None concerning intended behavior. This plan is proposed for human approval. Trusted activation and separately authorized real execution for both adapters remain verification prerequisites; missing fields/delivery are failures to report, not permission to substitute parent assertions.
