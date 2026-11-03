---
name: plan
description: Use after the spec is approved and before implementing a non-trivial change (lifecycle tier L1 and above). Produces a light or full implementation plan whose steps trace to spec requirements.
---

Run lifecycle Stage 1 (Plan).

1. Load the stage: `python3 .ai/scripts/okf.py show .ai/lifecycle.md --section "Stage 1: Plan"` and the role: `python3 .ai/scripts/okf.py show .ai/agents/planner.md --section Contract --section Investigation --section "Plan size"`.
2. Use the light plan at L1 and the full plan at L2. Delegate L2 planning to the `planner` subagent and persist its plan.
3. Success criteria cite spec requirement IDs; every step names its failing-closed check and, for bug fixes and new logic, the test written first.
4. Record it: `lifecycle.py stage plan --note "<light plan>"` (L1) or `lifecycle.py stage plan --ref <plan>` (L2). The stage refuses a plan that omits a spec requirement ID.
5. Do not start implementing while the plan has an open decision.
