# Handoff: assurance initiative, increment 1

Paused 2026-10-27 at the user's request (model switch). Nothing is committed or pushed.

## Read first

The user said they did not expect implementation to start yet. Before continuing,
**confirm with the user whether to resume implementation, revise the plan, or keep
only the research.** They did approve the increment 1 spec, zero-spend measurement,
and a separate worktree via the question prompt. That approval is recorded as
`human:enramosjr` on the intent stage.

## Where things are

| Item | Location |
|---|---|
| Worktree | `/home/enramosjr/Projects/agentic-assurance` |
| Branch | `claude/assurance-increment-1`, from `5f81468` (main) |
| Lifecycle | L2 feature. Recorded: intent (spec, approved), plan. Red run recorded. Still required: green, retrospective, review, verify |
| Main checkout | `/home/enramosjr/Projects/agentic` still has an untracked copy of `docs/assurance/` (assessment, architecture, specification) and another session's staged `docs/evaluation/v1/*` files with their own L2 task. Neither was touched by implementation |

## Artifacts (all in the worktree)

- `docs/assurance/assessment.md`: current-state audit and competitor comparison, with sources.
- `docs/assurance/architecture.md`: target design, alternatives, 7-increment plan, risks, answers to the 20 research questions.
- `docs/assurance/specification.md`: increment 1 spec, R1–R10. `lifecycle.py analyze` is OK.
- `docs/assurance/plan.md`: 9 steps. `lifecycle.py trace` traces all 10 requirements.

## Code changes (uncommitted)

- `.ai/scripts/assurance.py` (new): parses `- Verify:` / `- Inputs:` obligation lines, loads `req:` evidence from lifecycle records, evaluates VERIFIED, STALE, FAILED, UNVERIFIED, INVALID, MANUAL, UNDECLARED, computes `--changed`, renders text and JSON.
- `.ai/scripts/ledger.py`: optional `runtime_sha256` key plus `runtime_digest()`. Evidence goes STALE when the resolved executable changes. The full environment digest was not used because it differs in every shell session.
- `.ai/scripts/lifecycle.py`: `cmd_run`'s execution core moved into `execute_check()` and shared by `run` and `assure --run`. Adds `cmd_assure`, `assure_run`, the `assure` parser, and `assure` in `MUTATING_COMMANDS` (only `--run` counts as a mutation).
- `.ai/scripts/tests/test_assurance.py` (new): 28 tests in 11 classes.

## Evidence so far

- Red: `lifecycle.py redgreen red -- python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py` failed because `assure` was not a subcommand.
- `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py`: 28 tests, OK. Run directly, not yet through `lifecycle.py run`.
- Broken-variant check (scratch script `mutate.py` in the session scratchpad, not committed): 10 of 11 mutants were caught. The miss only reworded a VERIFIED reason string, which no requirement constrains.
- **Not run yet:** the full framework suite (`python3 .ai/scripts/run_tests.py`), `test_ledger.py` and `test_lifecycle.py` against the `execute_check` refactor, and `converge`.

## Remaining steps (plan.md steps 8–9)

1. R10 docs: add an "Assurance status" section to `.ai/lifecycle.md` covering syntax, statuses, `assure`, `--run`, `--changed`, `--strict`, the sentence "covers only that command on those inputs", the unscoped whole-tree rule (Markdown and `knowledge/` are exempt, as in `tree_hash`) and the squash-merge limit. Add a row to the Recording and enforcement table near line 130 (before `## Evals` at line 136).
2. Add class `Assurance` to `.ai/scripts/tests/test_lifecycle_conformance.py` that asserts those terms. Do not touch `AGENTS.md`: a budget test guards it.
3. Record green: `lifecycle.py redgreen green -- python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py`.
4. `lifecycle.py converge docs/assurance/specification.md`, then the full suite through `lifecycle.py run framework-suite -- python3 .ai/scripts/run_tests.py`.
5. Retrospective (`lifecycle.py learn` / `retrospect`), independent review with the `reviewer` subagent and a report with `## Verdict` and `## Validation Reviewed`, then `stage review --ref`, then `stage verify`.
6. Commit only when the user asks. Git identity is not configured here (`author_configured: false`). Ask the user rather than setting it.

## Known limits to carry into review

- Evidence recorded on commits that a squash merge drops shows as STALE (conservative).
- A schema-valid, hand-written record is accepted. The test `test_schema_valid_hand_written_record_is_not_detected` documents this. Audit detects drift, not forgery.
- Records on unmerged branches are not visible.
- Framework source has no `knowledge/`, so the feature is exercised only through fixtures, not on the framework's own requirements.
- `--changed` lists manual obligations without `Inputs:` on every change, per the literal R7. Revisit if this proves noisy.
