# Agent Lifecycle (AIDLC)

One lifecycle for every task, from a one-line prompt to a fully autonomous milestone. The stages and artifacts never change; the tier (`AGENTS.md` §2.5) sets how much ceremony each stage gets. Load by section: `python3 .ai/scripts/okf.py show .ai/lifecycle.md --section HEADING`.

## Router

1. Pick the tier (§2.5), state it with the persona, and declare it before editing source: `python3 .ai/scripts/lifecycle.py tier L2 --reason "new public behavior" --kind feature`. Hooks deny source edits until you do.
2. Run the stages the tier requires, in order, and record each with `python3 .ai/scripts/lifecycle.py stage NAME ...` (see Recording and enforcement). Each stage has an exit check; do not start the next stage until it holds.
3. Escalate the moment investigation shows a contract, schema, persistence, security, or dependency effect, or an unresolved behavior question. Never downgrade a tier the user set.

| Stage | Role | Artifact | Exit check |
|-------|------|----------|------------|
| 0 Intent | `analyst` | L1 intent note; L2+ spec | No open question changes behavior; every requirement has a failing-closed acceptance check |
| 1 Plan | `planner` | Light or full plan; L3 queue entries | Every spec requirement maps to a step and a check; no open decision hidden in a step |
| 2 Implement | `implementer` | Diff, tests, report | Test-first per `AGENTS.md` §8.6; focused checks pass; no §8.1 item on the critical path |
| 3 Review | `reviewer` | Findings or approval | Pass 1 (spec compliance) clean, then Pass 2 (quality); no Critical or High |
| 4 Verify and sync | implementer | Gate 3 and 4 evidence | `okf.py affected` handled, log entry, §8.4 gate for the tier, `okf.py records` exit 0 |
| 5 Ship | implementer, or orchestrator in L3 | Branch, PR, or checkpoint | Candidate frozen on current base; delivery options below |

## Tiers in practice

| Tier | Intent | Plan | Review | Verify |
|------|--------|------|--------|--------|
| L0 trivial | None | None | Read your own diff | Focused check if one exists; `okf.py affected` |
| L1 small | Three-line note in chat: goal, success check, assumptions | Light plan inline | Self-review of the diff; reviewer optional | Focused checks plus the slice's narrowest E2E when behavior changed |
| L2 feature | Spec by `analyst`, approved by the user | Full plan by `planner` | Independent `reviewer`, both passes | Slice E2E, then the full gate once on the frozen candidate |
| L3 milestone or autonomous | Objective and frozen `Acceptance` on each queue entry (the spec, §9.2) | Batch plan (§9.5); `planner` only for a named blocking decision | Reviewer gates DONE (§9.5) | Managed integrated gate (§8.4, §9) |

Single prompts and autonomous runs differ only in who answers the questions: the user at L1 and L2, a Tier A or Tier B decision (§9.7) at L3.

## Stage 0: Intent

Run the `analyst` role. At L1 write the three-line note and continue. At L2 and above:

1. Restate the request as problem, users, and outcome. Separate requirements from solution preferences.
2. Ask only questions that change behavior, in one batch of at most five, each with a recommended default. Without a human, record each default as an assumption and continue.
3. Write the spec (structure in `.ai/agents/analyst.md`). Persist it at `knowledge/specifications/<slug>.md` with `okf.py new` and `status: draft`. A draft spec is intent, not shipped behavior (`AGENTS.md` §5.2).
4. Consistency check before handoff: run `python3 .ai/scripts/lifecycle.py analyze SPEC` and fix every Critical or High finding (`stage intent` refuses them; a Medium manual check needs a reviewer note later). Then apply the analyst's absence-finding lens: missing scenarios, error paths, contradictions, and terminology drift. Each acceptance bullet leads with a backticked command runnable from the repository root.
5. Get approval. Interactive L2: the user approves the spec. L3: the spec becomes the queue entries' `Acceptance` and is frozen at claim time (§9.2).

## Stage 1: Plan

Run the `planner` role. Success criteria cite spec requirement IDs. Ship the light plan at L1 and the full plan at L2. At L3 the queue entry and batch plan are the plan.

## Stage 2: Implement

Run the `implementer` role on an isolated branch or worktree at L2 and above. Follow `AGENTS.md` §8.6: bug fixes start from a failing reproduction; new logic is written test-first. Commit in slices that each pass their focused checks.

## Stage 3: Review

At L2 and above the order is OKF sync, then `python3 .ai/scripts/lifecycle.py converge SPEC` (each requirement's acceptance command, run from the approved spec; fix any FAIL), then review, then verify, with no commit in between: the run is bound to HEAD, so a commit, even of records only, makes it stale. Run the `reviewer` role. Pass 1 asks whether the change meets the spec and plan, with nothing missing and nothing extra; at L2 and above it cites the converge result, notes each MANUAL requirement in the report's `## Validation Reviewed` section, and applies the absence-finding lens. Run Pass 2 (correctness, safety, maintainability, tests, completeness audit, knowledge sync) when Pass 1 is clean. Fix Critical and High findings and re-review only the fix.

## Stage 4: Verify and sync

Do not wrap lifecycle mutations (including converge, run, stage and merge apply)
in `lifecycle.py run`. Invoke them directly. An inherited repository-owner stack
refuses same-repository descendant mutations before their bodies execute, avoiding
lost acceptance/ledger evidence. Read-only inspection, merge --dry-run and
independent fixture repositories remain supported; ancestor ownership is retained.

Run `AGENTS.md` Gate 3 then Gate 4 at the tier's breadth. Run each check with `python3 .ai/scripts/lifecycle.py run LABEL [--inputs GLOB...] -- CMD` (argv, no shell, scratch environment; the ledger keeps exit status, tree and head, never output) and ask `lifecycle.py reuse LABEL_OR_CMD` before repeating one: REUSE means the recorded pass still covers HEAD, RERUN means run it again. At L2 and above `stage verify` requires a current passing ledger entry, fails when the newest entry for the current tree failed, and writes its own note from the ledger (`--note` becomes an optional `agent note:`); L1 keeps `--note`. At L1 and above `stage review` and `stage verify` run `lifecycle.py scan-diff`, which fails on an unwaived stub, `pass` with a deferred-work comment, or "future work" in added lines (waive one with `lifecycle:allow RULE -- reason`), and report weak-test findings without failing. Where a bundle exists, `stage verify` also runs `okf.py sync-check --base <task head>`: every changed file must be covered by a changed doc or listed in `knowledge/project/sync-ignore`, that doc's `verified` must postdate the change, and `knowledge/log.md` must change. Stamp docs with `okf.py stamp verified PATH... --run CMD...`, which runs CMD and stamps only on exit 0. A spec that has shipped is folded into `knowledge/capabilities/` and its status moves from `draft` to `stable`, or to `deprecated` when superseded.

For delta intent, preview and apply the approved spec with `lifecycle.py merge SPEC --dry-run` then `lifecycle.py merge SPEC` before Verify. Run current convergence and the existing gates. Verify additionally requires a completed merge receipt, matching postimages, removed-ID absence and target provenance/bookkeeping. Do not defer the delta fold to post-commit Ship.

## Brownfield deltas

`okf.py onboard` inventories tracked paths into absent draft architecture and repository-inventory documents. It keeps existing documents, runs no code, and makes no runtime or capability claim. An analyst inspects cited implementation/configuration and tests, writes claim-level sources, and obtains human approval before establishing living requirements. Whole-feature specs with legacy `R<n>` IDs and prose capabilities remain valid.

A structured capability has a unique uppercase `namespace`, for example `EXPORT`, and one `## Requirements` section containing `EXPORT-R1` bullets and indented named `- Scenario NAME:` blocks. IDs remain stable; retained removal deltas/receipts reserve retired IDs. Do not convert prose automatically.

A delta names one existing capability in frontmatter `target: /capabilities/export.md`. Its `## Target baseline` body repeats `Target: /capabilities/export.md` and pins each operated ID with `- EXPORT-R1: sha256:<hash>` or `- EXPORT-R3: absent`. Hash the complete UTF-8 block, including continuations/scenarios and its final line terminator, excluding separating blank lines. The mirror protects the path under body-only approval hashing.

Use `## Added requirements`, `## Modified requirements`, `## Removed requirements`, and one Acceptance bullet for each operated ID, plus Constraints, Non-goals, Assumptions and Open questions. Empty operation sections contain `None.`. Removals state a MUST retirement behavior and nonempty `Reason:`. Modified entries replace prose and keep existing scenarios by default. To replace or clear scenarios, include an indented `Scenarios: replace` followed by the complete replacement scenario set (empty clears it). This directive does not enter the capability. Acceptance commands stay in the delta and are executed only by converge.

`lifecycle.py merge SPEC --dry-run` produces the capability diff before approval without writing state. `merge SPEC` requires the active task's approved, unedited delta and passing audit. It appends additions, replaces modifications in place, deletes removals and records the spec source. Only operated blocks are pinned: unrelated prose/blocks remain mergeable. Conflict diagnostics name stale IDs; local draft overlaps are advisory, with unobserved branches outside warning coverage. No remote or other-worktree scanning occurs.

Apply publishes a pending lifecycle merge receipt before replacing the capability, then records one log entry, updates indexes and publishes completion. Rerun the same approved delta after interruption; the receipt permits only before/after states and deduplicates bookkeeping. Third-state edits refuse; restore or resolve the conflict with human review. Completed valid reruns report `up to date` without writes. Merge completes no lifecycle stage. Retain the delta and receipt for provenance; no living tombstones are added. Audit detects drift, not deliberate forgery of both artifacts and receipts.

## Stage 5: Ship

1. Fetch the default branch and merge it into the candidate, then confirm the gate evidence still covers the head (§8.4 reuse rules).
2. Offer the user these options and act only on their choice: open or update the PR, keep the branch, or discard it. Discarding deletes work, so confirm it.
3. L3 delivers through the single milestone PR (§9.9). Agents never merge into the default branch.
4. Remove only worktrees and branches this task created.
5. `lifecycle.py stage ship` closes the record. A later commit or PR for review feedback needs a fresh `lifecycle.py tier ... --new`, or a `wip:` commit.

## Debugging flow

Use for any bug, failing check, or unexpected behavior, at any tier above L0.

1. **Reproduce.** Capture the exact failing command and output. If it is not reproducible, say so and gather evidence before changing code.
2. **Isolate.** Narrow to the smallest failing input, test, or commit. Compare against a passing case.
3. **Hypothesize.** State one cause and the observation that would disprove it. Test it with a read-only probe before editing.
4. **Pin.** Write the failing test or reproduction that fails for that cause (§8.6).
5. **Fix and verify.** Make the smallest fix, show the test green, and run the narrowest regression check.
6. **Stop rule.** After three disproved hypotheses or fixes, stop. Question the design or the assumed surface, then report the evidence and the decision needed. Do not stack patches.

## Recording and enforcement

Optional learning: `lifecycle.py learn TEXT [--stage S] [--evidence REF]` records inert observations in active L1–L3 tasks. Capture never gates progression. `promote RECORD#N --approved-by human:ID` and `retire RULE_ID --reason TEXT --approved-by human:ID` require human authorization; attribution records claims rather than authenticating consent, and `decision:` is refused. Active approved rules have repository-instruction precedence and are injected at SessionStart within an 8,192-byte UTF-8 block. Missing rules preserve prior behavior; invalid rules emit a diagnostic without partial injection. Identical promotion/retirement retries repair interrupted log/index publication. At milestone close use repeatable `okf.py checkpoint --lessons-from RECORD` for every milestone record and include unpromoted observations in the retrospective. See the learning-loop capability and playbook in `knowledge/` when present; an installed adopter starts without template knowledge.

`python3 .ai/scripts/lifecycle.py` keeps its working state per branch (untracked, in the git scratch directory) and validates each stage's artifact before recording it. Above L0 it also writes the committed audit record `knowledge/history/lifecycle/<task>.json` (one per task). The record holds no command output, and it stores a sha256 of each `--ref`. Commit the record with the change.

| Stage | Command | What it checks |
|-------|---------|----------------|
| Tier | `tier L2 --reason T [--kind feature\|bugfix\|logic\|refactor\|docs] [--user-set] [--new]` | A user-set tier cannot be lowered. `--new` starts a different task. An L0 declaration ends at the next commit. |
| Analyze | `lifecycle.py analyze SPEC [SPEC...]` | One `<Severity> <category> <file>: <message>` line per finding; exit 1 on any Critical or High. Critical: missing section, no requirements, duplicate ID, uncovered requirement, orphan or placeholder acceptance. High: no `MUST`/`SHOULD`, vague term (defaults plus `## Vague terms` bullets in `knowledge/project/*.md`), identical requirements, open questions. Medium: an acceptance bullet with no backticked command (manual). |
| 0 Intent | `stage intent --note T` (L1) or `--ref SPEC --approved-by human:ID` (L2, L3) | The `analyze` rules report no Critical or High finding (Medium findings print as warnings). L3 may use `--note "queue:IDS"` with `decision:<ADR>` approval. |
| 1 Plan | `stage plan --note T` (L1) or `--ref PLAN` (L2, L3) | The plan cites every spec requirement ID. |
| 3 Review | `stage review --note T` (L1) or `--ref REPORT` (L2, L3) | The report's `## Verdict` is Approved. |
| Converge | `lifecycle.py converge SPEC [--timeout SECONDS]` | Only for the active L2+ task's approved intent `--ref`, after the audit passes. Runs each requirement's first acceptance backtick span without a shell, from the repository root, stdin closed, disk-backed scratch `TMPDIR`, 600 s default timeout; prints `R<n> PASS`, `FAIL (exit N\|timeout\|cannot run)` or `MANUAL`; exit 1 on any FAIL. The run (no output) is stored under `converge` in the record. |
| 4 Verify | `stage verify --note "commands and outcomes"` | Review done at L2+, red/green recorded for `--kind bugfix\|logic`, the audit passes, at L2+ with a spec `--ref` a converge run for that spec with no FAIL whose HEAD and non-Markdown files outside `knowledge/` are unchanged and whose MANUAL IDs are cited in the review's `## Validation Reviewed`, and `okf.py records` passes. |
| Audit | `lifecycle.py audit [RECORD]` | Exit 1 when a recorded `--ref` is missing or its body changed since recording, an L2+ intent lacks `approved_by`, or the record is malformed. Re-record a changed stage (intent with fresh approval). |
| 5 Ship | `stage ship` | All required stages are recorded; the record is closed. |
| Test-first | `redgreen red -- CMD`, then after the fix `redgreen green -- CMD` | Red must fail; green must pass on a changed working tree (staged or not). Red proves only that the command failed, so state in the report that it failed for the reported reason. |
| Traceability | `trace SPEC --plan PLAN --tests PATH...` | Every requirement is cited by the plan and by a test. |
| L3 | `queue-from-spec SPEC --group G` | Prints §9.3 queue entries, one per requirement, with its acceptance check. |
| State | `status`, `gate implement\|review\|verify\|ship` | Exit 1 with the missing stages. |

Hooks (Claude Code, Codex, Cursor) call `lifecycle.py hook`. They deny source edits until the tier is declared and the stages required before Implement are recorded, deny `git commit` (other than `wip:`) and PR creation until Verify is recorded, deny such a commit when it would leave the audit record untracked or unstaged, and inject the Router at session start. Markdown and `knowledge/` edits are exempt. `LIFECYCLE_GUARD=off` bypasses tool gates, and autonomous driver sessions are gated by the work queue instead. Both bypasses still receive approved project rules at SessionStart, without the interactive lifecycle router. An approval is a recorded claim that must come from a user message; the guard raises the cost of skipping a stage and does not prove human consent.

## Evals

`python3 .ai/scripts/lifecycle_eval.py run [--repeat N --json OUT] -- AGENT_COMMAND` evaluates fresh copied-kit repositories and records deterministic behavior/artifact checks. Completed L2/spec-backed L3 outcomes additionally require a unique verified candidate and operator-observed independent-review evidence; the queue-only L3 case is separate. `--observation-adapter ID` captures an operator-owned argv parser from `--checks-dir`; unsupported review visibility is a measurement error, not assumed independence.

`results-check FILE_OR_DIR` reads versioned results without launching agents. Only explicit `--recover-interrupted` may reconcile validated orphaned process groups and settle interrupted reservations; it never starts or retries a cell. A plain schema PASS is not a qualified real-agent baseline. The unit suite uses scripted stand-ins and synthetic adapter observations; full qualification and real-agent adherence remain unclaimed. See [the runner capability](../knowledge/capabilities/pressure-evaluation-runner.md) for current implementation limits and exact evidence.

For gap 5, the user explicitly released evaluation-fixture creation and real-agent execution on 2026-10-19, and separately authorized read-only project review. The 16-case evaluation suite is distinct from repository governance documentation. Live identity/hook qualification, frozen inputs and the approved campaign limits still govern launch; scripted tests do not establish real-agent adherence. Scratch must pass the disk-backed preflight; process-birth recovery currently requires Linux `/proc`.
