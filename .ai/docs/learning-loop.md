# Retrospectives and project observations

`lifecycle.py learn TEXT` captures an inert observation for the active L1–L3 task.
It does not change repository rules. Capture alone does not close a task.
Before Verify, L1–L3 tasks must explicitly close their retrospective with
`lifecycle.py retrospect --lessons 1 2` for existing lessons with nonblank
`--evidence`, or `lifecycle.py retrospect --no-new-lessons REASON` with a nonblank
explanation. Verify, commit/PR and ship gates require closure; L0 stays exempt.
Outcome, UTC timestamp and lesson numbers or reason persist in the lifecycle audit
record. Historical records without closure remain auditable; active legacy tasks
must close before newly verifying or delivering. Conflicting recovery fails closed.

`lifecycle.py observations --query TEXT` retrieves project observations read-only.
Task declarations use the task reason; SessionStart also surfaces observations.
Case-insensitive token overlap with lesson text/evidence ranks results, followed
by recency and stable source reference. With no matches, a labeled recent fallback
is used. At most five whole entries fit in an 8,192-byte UTF-8 advisory block,
separate from approved rules. Entries include evidence and `RECORD#N` provenance;
omissions and corrupt records are reported. These observations are advisory data
to evaluate against the current task, without instruction precedence. Report the
closing outcome in the delivery summary; never invent a lesson to fill the gate.

`lifecycle.py promote RECORD#N --approved-by human:ID` establishes a rule only
after human authorization. `lifecycle.py retire RULE_ID --reason TEXT
--approved-by human:ID` retires one under the same approval requirement. Actor
attribution records claims and does not authenticate a human. Decision actors
cannot replace that human approval.

Approved active project rules have repository-instruction precedence. SessionStart
injects a UTF-8 block capped at 8,192 bytes. Missing rules preserve prior behavior;
invalid rules emit a diagnostic without partial injection. Promotion and retirement
retries repair interrupted bookkeeping and avoid duplicate log entries.

`okf.py checkpoint --lessons-from RECORD` includes optional milestone observations
without promoting them. Repeated checkpointing is supported. See the
[learning workflow](learning-loop-playbook.md); no source knowledge import is
required to use learn, retrospect, observations, promote, retire or --lessons-from
in an adopting project.
