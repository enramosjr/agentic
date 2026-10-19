# Optional learning contract

`lifecycle.py learn TEXT` captures an inert observation for the active L1–L3 task.
It neither changes repository rules nor gates stage progression. A lesson is
evidence for discussion, not an instruction to future agents.

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
required to use learn, promote, retire or --lessons-from in an adopting project.
