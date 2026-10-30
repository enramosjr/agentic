# Handoff: assurance initiative, increment 7 (measurement and pruning)

Updated 2026-10-28 after increment 7 implementation and verification. Candidate is reviewed and verified, retained uncommitted at the user’s request; do not restart Step 1.

## Rules from the user (carry these forward)

- Do NOT commit documents to the repository. The framework generates OKF for adopters; specs, plans, reviews and handoffs here are untracked working files. `docs/` is gitignored and `docs/assurance/` files stay out of commits.
- Commit, push and PR creation only when the user says so. Never merge: the user merges. Git identity is not configured; pass it per command with `git -c user.name="Eduardo Nicolas Ramos, Jr" -c user.email="enramos@live.com"` and end commits with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; PR bodies end with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- Spec and plan approvals must come from a user message (`--approved-by human:enramosjr`). A subagent report is never approval.
- Shell guard: use `Read`, `Edit`, `Write` and `python3 .ai/scripts/repo.py grep|files|read` (grep needs `--regex`/`-E` for alternation); no heredoc or inline-Python edits, no `ls`/`find`/`cat`. Run scripts from the repository root.
- Confirm a broken-variant mutation is actually applied before trusting a pass. A mutant that cannot be observed is equivalent: replace it, do not count it.
- Settle open decisions with the user BEFORE implementing; amended spec wording needs the user's approval and the intent stage re-recorded.

## State

| Item | Value |
|---|---|
| Main checkout | `/home/enramosjr/Projects/agentic`, `main` at `9efcfb7`. `stash@{0}` holds another session's `docs/evaluation/v1/*` files; leave it |
| Worktree | `/home/enramosjr/Projects/agentic-assurance-7`, branch `claude/assurance-increment-7` at `9efcfb7`, four changed/new candidate files; no commit, push or PR |
| Lifecycle | L2. Intent, plan, independent Approved review (`review-7.md`), retrospective and Verify recorded. D1-D5 remain settled. Shipping awaits user instruction |
| Artifacts | Approved `specification-7.md` and `plan-7.md`; `implementation-7.md`, `review-7-initial.md`, `review-7.md`, convergence and mutation logs. Implementation in `.ai/scripts/assurance_measure.py` and its tests; lifecycle sentence and conformance assertion updated. NEXT ACTION: await user instruction about delivery; do not rerun unchanged gates |
| Merged | #19 inc 1 (`assure`), #20 docs removal, #21 inc 6 (`assurance_demo.py`), #22 inc 4 (attested evidence and `Accept-risk:`) |
| Left | 2 gate, 3 architecture constraints, 5 input adapters, 7 measurement. User chose 7 |
| Old worktree | `/home/enramosjr/Projects/agentic-assurance-4` can be removed once the user agrees (`git worktree remove`) |

## Resume prompt (paste into a fresh conversation)

> Read /home/enramosjr/Projects/agentic-assurance-7/docs/assurance/handoff-7.md. Increment 7 is implemented, independently reviewed and verified in this worktree, left uncommitted. Reuse the recorded passing evidence for source tree cb75486. Do not commit, push or open a PR until I say so. No knowledge bundle or committed working documents.

## Design in one paragraph

New stdlib-only `.ai/scripts/assurance_measure.py` reuses `Session`, `DemoFailure`, `_base` from `assurance_demo.py` (unchanged) and imports nothing from `assurance`, `lifecycle` or `ledger`. Six scenarios (feature, requirement-change, regression, stale-evidence, dependency, handoff) each build a throwaway repo, record evidence, apply a change, and read `assure --json` and `assure --changed --base HEAD`. Ground truth is a hand-declared true-reads map per requirement (independent of `Inputs:`); expected caught/false_stale/missed counts are hand-written constants, so the command exits 1 if the mechanism's behavior drifts. Known profile: missed 1 for the undeclared dependency (`config.ini`), false STALE 1 for the whole-tree requirement, `changed_missed` 1 for a requirement-block edit (reported, not a failure). Output is deterministic text or `--json` (`schema_version` 1) with a `contribution` section; report-only, nothing removed. Full detail: plan-7.md D-a to D-f.

## Why 7 first

Increment 2 (the gate: L2+ `stage verify` refuses touched STALE/FAILED/UNVERIFIED requirements) is blocked on a "measured false-positive rate". Increment 7 is the zero-spend way to get that number, and it also decides what to prune. Increments 3 and 5 have no framework-side data source (no `knowledge/` here; Rust-first).

## Source material

- Architecture §8 (git history: `git show 4031aab:docs/assurance/architecture.md`; sections 6 and 8 matter): "A deterministic scenario fixture set (feature, requirement change, regression, stale evidence, dependency change, multi-agent handoff) that reports detection counts, false STALE counts and rerun counts versus a 'rerun everything' baseline. This measures mechanism behavior, not agent outcomes." Second source: existing evaluation protocol and normal development records (accepted changes later found to have invalidated earlier verification). No paid or long campaign; comparisons with competitors stay descriptive.
- Existing code to reuse: `.ai/scripts/assurance_demo.py` (`Session`, `build`, `observe`, `run`; throwaway repo, VERIFIED, STALE, VERIFIED), `tests/test_assurance.py` `Case`, `tests/test_assurance_attested.py` (golden fixture helpers), `assurance.py` (`evaluate`, `changed`, `summary`), `lifecycle.py assure [--changed --base REV --json]`.
- Constraints carried from earlier increments: standard library only, Python 3.9+, report-only, `schema_version` 1 unchanged, no new gate/hook/stage, no `okf.py` rule, no committed documents (editing existing `.ai/lifecycle.md` plus its conformance test is allowed).

## Decisions to settle with the user FIRST

- **D1. Shape.** (a) A new script `.ai/scripts/assurance_measure.py` (like `assurance_demo.py`) that builds each scenario in a throwaway repository and prints a table; (b) tests only; (c) a `lifecycle.py assure --measure` flag. Recommended: (a), stdlib only, no change to `assure` output, with a unit-test file that runs it. A flag would touch `cmd_assure` for a developer-only feature.
- **D2. Ground truth.** Each scenario needs a known answer for which requirements SHOULD be stale (oracle declared in the scenario). Recommended: the oracle is written by hand per scenario, because deriving it from `assure` would be circular. Confirm the six scenario names or change the set.
- **D3. Baseline.** "Rerun everything" counted as: every declared obligation rerun after each change. Confirm; the measured quantities are detected-stale (true positive), false-STALE (flagged but unaffected), missed-stale (false VERIFIED, the dangerous one), and reruns needed with `--changed` versus the baseline.
- **D4. Pruning.** Spec says "keep only what earns its cost". Recommended: the increment only REPORTS which features never contributed in the scenarios (for example whether `Inputs:` scoping saved reruns vs whole-tree) and makes no removal; any removal is a later, user-approved change.
- **D5. Real-usage source.** Whether to also scan this repository's own committed lifecycle records for "accepted change later found to invalidate earlier verification". Recommended: out of scope for the first cut (framework source has no capability requirements with `Verify:`), state it as a known limit.

## Then (outline; analyst/planner stages produce the real artifacts)

1. `lifecycle.py tier L2 --reason ...`; write `docs/assurance/specification-7.md` (requirements with IDs, acceptance commands, non-goals); lint with `lifecycle.py analyze`; user approves; `stage intent --ref ... --approved-by human:enramosjr`.
2. `docs/assurance/plan-4`-style plan: test-first (scenario oracle tests red), harness, scenarios, report format, mutation proof (each scenario must fail against a variant of `assure`: an under-declared `Inputs:` that causes a missed-stale, a whole-tree obligation that causes a false-STALE), docs, verify. `stage plan`.
3. Implement, mutation proofs, `retrospect`, independent review by the `reviewer` subagent (save its report yourself as untracked `docs/assurance/review-7.md`), `stage review --ref`, `converge`, the full suite through `lifecycle.py run` (`python3 .ai/scripts/run_tests.py`), `stage verify`. Ask the user before committing, pushing or opening a PR.

## Success looks like

A command a maintainer can run in seconds, with no network or spend, printing per-scenario and total: true STALE detected, false STALE, MISSED (must be 0 for the declared-inputs scenarios, and reported honestly for the deliberately under-declared one), reruns with `--changed` versus rerun-everything. The output is the evidence base for deciding increment 2.

## Known limits to carry

Records and review reports on unmerged branches are invisible; attestations and approvals are unauthenticated claims; the framework source is exercised only through fixtures; scenario results measure mechanism behavior, not agent outcomes.

The handoff fixture separates its tasks by 1.05 seconds because real evidence/task timestamps have second precision and same-second ordering can select older committed evidence after a passing rerun. This is a discovered framework limit, not repaired by this report-only increment; the retrospective records it as advisory.

## Final verification (2026-10-28)

- Source tree `cb75486`, HEAD remains `9efcfb7939cd6818f28caab48d3dadf4b2d69f4a`.
- Red tests recorded before implementation, then GREEN; review found and closed null-evidence handling and numeric text-rendering test gaps.
- `lifecycle.py converge docs/assurance/specification-7.md`: 9 PASS, 0 FAIL, 0 MANUAL (`converge-7-final.log`).
- `lifecycle.py run measure-framework -- python3 .ai/scripts/run_tests.py -j 8`: PASS (`framework-7.log`). Covers existing assurance, attestation, demo and lifecycle conformance tests.
- `lifecycle.py run measure-cli -- python3 .ai/scripts/assurance_measure.py`: PASS.
- `lifecycle.py run measure-demo-cli -- python3 .ai/scripts/assurance_demo.py`: PASS.
- All 20 original planned mutations killed; seven affected/new report and expectation mutations killed on the final candidate, including zeroed text counts. See `mutations-7.json` and `mutations-7-targeted.json`.
- Output: caught 7, false_stale 1, missed 1, changed_missed 2; reruns 8 vs baseline 19. Contribution: avoided 11, whole-tree false_stale 1, affected changed_listed 6, changed_missed 2, committed-record handoff detections 1.
- `git diff --check` and `lifecycle.py scan-diff`: PASS. Framework has no knowledge bundle; `okf.py affected` / `records` report no bundle and are not represented as PASS. Verify correctly skips adopter bundle checks in framework mode.
- `lifecycle.py stage review --ref docs/assurance/review-7.md` and `stage verify`: recorded. Retrospective closed with lesson 1. Ship not recorded; no commit, push or PR performed.
