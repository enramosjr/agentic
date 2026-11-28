# ADR 0011: Unattended work only through a supervised driver with fresh sessions and circuit breakers

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §12](../0001-agentic.md#12-autonomous-execution)

## Context

Long unattended conversations fail in two ways. Some stop early, citing size
or complexity. Others never converge, rewriting tests and re-recording evidence
while the context, and with it the per-turn cost, grows without bound.
Compaction does not restore a fresh context. Limits written only in prose can be
"reset" by relaunching the run.

## Decision

- Unattended implementation runs only through `autonomy_driver.py`. Each
  session starts fresh from `okf.py handoff --prompt`, advances one bounded
  batch (or orchestrator round) and ends at a SAFE `okf.py checkpoint`.
- Acceptance is frozen when a batch is claimed. A task gets at most three
  sessions, counted in the queue's `Sessions` field so that relaunching cannot
  reset it. A task at the cap must be split.
- The defaults are:
  - 1,200-second session target with a cooperative handoff;
  - 3,600-second run budget;
  - two consecutive sessions without newly evidenced DONE (at most four);
  - one recovery session per run;
  - two failed model-backed qualification cases per slice per run.
- Limits override keep-going instructions and are never reset by automatic
  restarts.
- Full validation runs between sessions (`autonomy_validation.py submit`),
  outside the model's process group. No model waits on tests.
- Acceptance must be unattended and deterministic. Environment-dependent checks
  get one repair, then move to a deterministic layer or out of scope.
- A launching chat relays progress through `autonomy_progress.py`'s read,
  comment, `ack` sequence. `--headless` needs an explicit user choice.
- Open decisions are classified Tier A (decide, record, continue) or Tier B
  (block the task, continue other work).

## Consequences

- Runs converge or stop with a precise blocker. They are reported as blocked,
  never as completed.
- Bounded context per session keeps cost proportional to work.
- Some legitimately large tasks must be decomposed before work starts.
- A real-model qualification baseline is on hold. Scripted evaluations prove
  only the mechanics.

## Alternatives considered

- **Long-lived interactive sessions with "keep going".** Rejected because of
  unbounded cost and the inability to enforce limits.
- **Limits held only in the driver.** Rejected because relaunching with larger
  flags would reset them. The counts live in repository state.
- **The model polling validation.** Rejected because every poll re-sends the
  full context.

## Evidence

`.ai/scripts/autonomy_driver.py`, `autonomy_validation.py`, `autonomy_progress.py`,
`autonomy_hook.py`, `okf.py` (`queue`, `checkpoint`, `handoff`),
`.ai/autonomous-execution.md` §9.2–§9.12, `.ai/agents/orchestrator.md`.

## Revisit when

Real-model qualification criteria are defined, or harnesses expose
enforceable per-session budgets.
