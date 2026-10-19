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
4. Consistency check before handoff: every requirement has an ID and an acceptance check, no two requirements contradict, terms are used one way, non-goals are stated.
5. Get approval. Interactive L2: the user approves the spec. L3: the spec becomes the queue entries' `Acceptance` and is frozen at claim time (§9.2).

## Stage 1: Plan

Run the `planner` role. Success criteria cite spec requirement IDs. Ship the light plan at L1 and the full plan at L2. At L3 the queue entry and batch plan are the plan.

## Stage 2: Implement

Run the `implementer` role on an isolated branch or worktree at L2 and above. Follow `AGENTS.md` §8.6: bug fixes start from a failing reproduction; new logic is written test-first. Commit in slices that each pass their focused checks.

## Stage 3: Review

Run the `reviewer` role. Pass 1 asks whether the change meets the spec and plan, with nothing missing and nothing extra. Run Pass 2 (correctness, safety, maintainability, tests, completeness audit, knowledge sync) when Pass 1 is clean. Fix Critical and High findings and re-review only the fix.

## Stage 4: Verify and sync

Run `AGENTS.md` Gate 3 then Gate 4 at the tier's breadth. A spec that has shipped is folded into `knowledge/capabilities/` and its status moves from `draft` to `stable`, or to `deprecated` when superseded.

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

`python3 .ai/scripts/lifecycle.py` keeps one record per branch (untracked, in the git scratch directory) and validates each stage's artifact before recording it.

| Stage | Command | What it checks |
|-------|---------|----------------|
| Tier | `tier L2 --reason T [--kind feature\|bugfix\|logic\|refactor\|docs] [--user-set] [--new]` | A user-set tier cannot be lowered. `--new` starts a different task. An L0 declaration ends at the next commit. |
| 0 Intent | `stage intent --note T` (L1) or `--ref SPEC --approved-by human:ID` (L2, L3) | Spec has Requirements, Acceptance, Non-goals and Open questions sections; every `R<n>` has an acceptance check; no open question. L3 may use `--note "queue:IDS"` with `decision:<ADR>` approval. |
| 1 Plan | `stage plan --note T` (L1) or `--ref PLAN` (L2, L3) | The plan cites every spec requirement ID. |
| 3 Review | `stage review --note T` (L1) or `--ref REPORT` (L2, L3) | The report's `## Verdict` is Approved. |
| 4 Verify | `stage verify --note "commands and outcomes"` | Review done at L2+, red/green recorded for `--kind bugfix\|logic`, and `okf.py records` passes. |
| 5 Ship | `stage ship` | All required stages are recorded; the record is closed. |
| Test-first | `redgreen red -- CMD`, then after the fix `redgreen green -- CMD` | Red must fail; green must pass on a changed working tree (staged or not). Red proves only that the command failed, so state in the report that it failed for the reported reason. |
| Traceability | `trace SPEC --plan PLAN --tests PATH...` | Every requirement is cited by the plan and by a test. |
| L3 | `queue-from-spec SPEC --group G` | Prints §9.3 queue entries, one per requirement, with its acceptance check. |
| State | `status`, `gate implement\|review\|verify\|ship` | Exit 1 with the missing stages. |

Hooks (Claude Code, Codex, Cursor) call `lifecycle.py hook`. They deny source edits until the tier is declared and the stages required before Implement are recorded, deny `git commit` (other than `wip:`) and PR creation until Verify is recorded, and inject the Router at session start. Markdown and `knowledge/` edits are exempt. `LIFECYCLE_GUARD=off` disables them, and autonomous driver sessions are gated by the work queue instead. An approval is a recorded claim that must come from a user message; the guard raises the cost of skipping a stage and does not prove human consent.

## Evals

`python3 .ai/scripts/lifecycle_eval.py run -- AGENT_COMMAND` runs each scenario in `.ai/evals/lifecycle/` against a real agent in a throwaway copy of the governance files and checks the outcome (final tier, recorded stages, red/green, lint-clean specs, changed files), not the prose. Use it when a change alters tier or stage rules. Example: `lifecycle_eval.py run -- claude -p --permission-mode acceptEdits`. Set `TMPDIR` to a disk-backed directory first. The unit suite runs the same runner against scripted compliant and non-compliant agents, so the runner itself fails closed.
