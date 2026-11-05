---
name: debug
description: Use for any bug, failing test or check, or unexpected behavior before changing code. Finds the root cause with a reproduce, isolate, hypothesize, pin, fix flow and a three-attempt stop rule.
---

Run the debugging flow.

1. Load it: `python3 .ai/scripts/okf.py show .ai/lifecycle.md --section "Debugging flow"` and the test rules: `python3 .ai/scripts/okf.py show AGENTS.md --section "8.6 Test-first and root cause"`.
2. Declare the task as a bug fix: `python3 .ai/scripts/lifecycle.py tier L1 --reason "<symptom>" --kind bugfix`.
3. Reproduce and name the cause before editing. Pin it with `lifecycle.py redgreen red -- <failing test command>`, fix, then `lifecycle.py redgreen green -- <same command>`.
4. After three disproved hypotheses, stop and report the evidence and the decision needed.
