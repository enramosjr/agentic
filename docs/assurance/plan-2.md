# Implementation Plan: assurance gate and delta convergence evidence

2026-10-28. L2; Python principal engineer. Spec approved: `docs/assurance/specification-2.md`. Plan pending human approval; no source edits yet.

## Objective

Prevent L2/L3 adopter Verify from accepting touched requirements with failing mechanical assurance. Let exact-match delta acceptance executions produce reusable requirement evidence without duplicate execution.

## Success criteria

- R1–R3: Verify blocks touched STALE/FAILED/UNVERIFIED/INVALID requirements, names remediation, and fails closed on selection/evaluation errors.
- R4–R5: MANUAL/UNDECLARED remain nonblocking; risk annotations never waive failures; L0/L1 and framework/no-requirement behavior stay compatible.
- R6–R7: Exact-match delta add/modify checks execute once and produce scoped req evidence; unsuccessful/excluded executions never fabricate fresh passing evidence.
- R8: Lifecycle documentation describes the gate; existing assurance reporting contracts remain unchanged.

## Current state

- `.ai/scripts/lifecycle.py:617` records starting HEAD in `state["head"]`; no new state field is needed.
- `cmd_stage`, around lines 722–750, checks audit, merge, convergence, ledger and adopter synchronization before Verify publication; no assurance gate exists.
- `.ai/scripts/assurance.py:135` parses requirements; `Obligation.block_sha256` supports block comparison. `changed`, around lines 361–385, selects input intersections but misses block edits. `evaluate`, around lines 318–344, already handles statuses and exact argv/scope matching.
- `cmd_converge`, lifecycle lines 1184–1242, executes acceptance then publishes whole-tree `converge:<ID>` entries. `execute_check`, around lines 986–1022, demonstrates pre-execution scoped capture and locked reload-and-append.
- `.ai/scripts/brownfield.py:288` onward models rendered replacements, preserved scenarios and completed receipt handling.
- Existing `test_assurance.py.Case` and `test_brownfield_deltas.py.DeltaCase` demonstrate temporary Git CLI fixtures. Reuse fixture patterns without inheriting their entire test suites.
- Framework mode has no knowledge bundle. `okf.py affected` reports absence; that is inapplicable, not PASS.

## Proposed approach

Add gate-specific internal helpers in assurance.py, orchestrated by the existing L2/L3 Verify path. Assurance remains read-only and imports no lifecycle code.

Resolve the recorded task-start commit and gather changes through the working tree using checked, NUL-delimited Git output with rename collapsing disabled, plus nonignored untracked paths. Both old deleted and new destination paths participate. Select current input intersections, conservative whole-tree/invalid obligations, changed current blocks and current approved-delta IDs. Read baseline capability content with Git and compare parsed blocks by stable ID; do not change public `assure --changed` behavior. Missing baseline, failed Git reads or evaluation diagnostics refuse rather than produce a partial/empty success.

Evaluate selected obligations after existing prerequisites and before Verify publication. No implicit command execution. Changed prose may reuse fresh evidence with identical Verify/Inputs, per approved policy.

For converge, derive eligible obligations from approved delta rendered add/modify blocks. Match acceptance argv exactly. Capture each eligible command's HEAD, tree, runtime, scope digest and files BEFORE execution. Publish req and existing converge evidence from the same execution outcome in the existing final locked reload-and-append transaction. Never relabel a post-run whole-tree converge entry: that could falsely verify a command which changed its inputs.

## Boundaries and invariants

No new stage, hook, dependency, store or output schema. Preserve existing prerequisite checks, statuses, exits, risk annotations and changed report. Refusal records no successful Verify and runs no obligations. Exact obligation evidence globs include existing lifecycle-record exclusions. Pre-execution evidence and honest failure/timeout/launch outcomes preserve freshness. Locked publication preserves concurrent entries.

Preserve all four increment 7 source/test changes and its recorded evidence. No new worktree, commit, push, PR or Git merge. Temporary fixture repositories may exercise lifecycle delta merge as required by acceptance.

## Implementation steps

### Step 1: Gate statuses and compatibility

Files: NEW `.ai/scripts/tests/test_assurance_gate.py`; existing assurance.py and lifecycle.py. Requirements R1, R4, R5.

Write GateStatusTests, GatePolicyTests and CompatibilityTests first; record RED before production edits. Reach existing Verify prerequisites through real CLI fixtures. Assert all four blocking statuses, named remediation, unchanged Verify state, and an unchanged command counter on refusal. Assert explicit rerun then successful Verify; nonblocking statuses; no active/expired risk or attestation bypass; L1/framework/no-requirements behavior; and existing prerequisite refusals. Implement integration, then record focused GREEN.

### Step 2: Complete touched selection and fail closed

Files: assurance.py, lifecycle.py, new gate tests. Requirements R2, R3.

Write TouchedScopeTests and GateFailureTests first. Cover task-start baseline after later commits; staged/unstaged/untracked/deleted/renamed paths; ordered exclusions; unrelated scopes; whole-tree obligations; requirement-only edits; delta IDs; completed removal exclusion; and prose-only fresh reuse. Implement checked baseline/path collection and baseline block comparison, reusing validated delta modeling. Assert missing/bad baseline, Git failure and malformed capability/evidence cannot collapse into empty success, execute commands, or publish Verify. Record RED/GREEN for new logic.

### Step 3: Produce delta requirement evidence from one execution

Files: lifecycle.py and new gate tests. Requirements R6, R7.

Write DeltaEvidenceTests and EvidenceBoundaryTests first. Drive approved add/modify convergence and merge; assert one execution, exact req labels/argv/globs/runtime/fingerprints, rendered replacement semantics, and VERIFIED for unchanged scoped/whole-tree executions. Exclude removal/manual/undeclared/invalid/different-command/legacy whole-feature cases. Assert failure, missing executable, timeout, and self-mutated scoped/whole-tree inputs never yield passing fresh req evidence. Preserve locked publication under concurrent entries. Implement per-command pre-execution capture and final req publication without changing existing convergence results or converge labels. Record RED/GREEN.

### Step 4: Document and prove the connected slice

Files: `.ai/lifecycle.md`, new gate tests; existing lifecycle conformance tests only when their assertions need an approved behavior update. Requirements R8 and connected R1–R7.

Write DocumentationTests, then describe gate scope, baseline, statuses, rerun cost/path, exact delta mapping and residual limits. Run the whole new test module once on the completed slice. Decisive CLI flows: changed input → Verify refusal → explicit rerun → successful Verify; and approved delta → one convergence execution → merge → VERIFIED assurance → successful Verify. Assert record contents and end state.

### Step 5: Review and frozen validation

Requirements R1–R8. Save ignored implementation evidence; obtain independent two-pass reviewer approval, including completeness and framework documentation sync. Fix findings before freezing.

Confirmed mutation proofs must reject: omitted gate; allowed blocking status; HEAD replacing task-start HEAD; omitted block/delta selection; swallowed Git/parsing errors; risk waiver; inexact argv; wrong scope/post-execution fingerprints; duplicate execution; failed-as-passing evidence; discarded concurrent entries. Confirm the edited bytes before trusting each mutation result.

Close retrospective before Verify. Run current convergence, full framework suite once, required real-agent evaluation, diff/scan checks and record review/Verify. Consult reuse before repeating checks. Do not rerun increment 7's unchanged standalone measurement/mutation gates merely for planning or session boundaries.

## Testing strategy

The eight acceptance classes named in the spec live in the new test module. Use real lifecycle CLI operations in temporary Git repositories and assert exit, output and records. Pure helper tests supplement the connected CLI tests. Record intended failures before implementation or prove tests against confirmed broken variants. Space historical-record fixture task IDs to avoid the known second-precision ordering limit; do not repair that limit here.

## Validation commands

Focused class commands are the eight commands in approved spec Acceptance. Slice E2E:

`python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_gate.py`

Traceability:

`python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-2.md --plan docs/assurance/plan-2.md --tests .ai/scripts/tests/test_assurance_gate.py`

Final candidate commands (run evidence-bearing checks through lifecycle run; convergence records its own evidence):

- `python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-2.md`
- `python3 .ai/scripts/lifecycle.py run assurance-2-framework -- python3 .ai/scripts/run_tests.py -j 8`
- `python3 .ai/scripts/lifecycle.py run assurance-2-diff -- git diff --check`
- `python3 .ai/scripts/lifecycle.py scan-diff`

AGENTS.md §8.4 also requires real-agent lifecycle evaluation because this changes a stage rule. Before Verify, establish an available, authorized zero-spend real-agent invocation and run applicable control-delta/feature-l2 scenarios via lifecycle_eval.py run with `--evidence-class real-agent`. Existing documentation mentions `claude -p --permission-mode acceptEdits`; its available/authenticated/zero-spend execution is NOT established. Resolve the actual command and metadata from supported tooling; do not invent settings or run a paid campaign. Record the exact executed command/outcome. Scripted suite results do not replace this check. If unavailable, report Verify blocked rather than invent PASS. This environment prerequisite does not block implementation.

Before repeating a check, use `lifecycle.py reuse LABEL_OR_CMD`. Follow loaded validation-policy sections for focused checks, final gate and long-check delegation; do not poll long suites from the parent chat.

## OKF impact

No bundle in framework mode; do not initialize one. Update existing lifecycle guide; keep working specs/plans/reviews/evidence ignored under docs/assurance and receipts in Git scratch. Affected/records absence is inapplicable, not PASS.

## Risks and mitigations

- Whole-tree false STALE: approved conservative cost; document explicit rerun and scoped declarations.
- Under-declared dependencies: remain an honest limit, no inference.
- Post-run snapshots: prevent with per-command pre-execution capture and self-mutating-input tests.
- Markdown tree exemptions: compare requirement blocks without changing tree freshness semantics.
- Concurrent publication: locked reload-and-append and regression coverage.
- Second-precision records: space fixture tasks, preserve documented limit.
- Real-agent availability: resolve before Verify; report any blocker honestly.

## Out of scope

Increments 3/5, changed-report redesign, dependency inference, pruning, risk waivers, ordering repair, paid evaluation campaigns and delivery operations.

## Open decisions

None concerning implementation behavior. The plan is ready for human approval. Required verification prerequisite: establish the available, authorized zero-spend real-agent invocation before Verify.
