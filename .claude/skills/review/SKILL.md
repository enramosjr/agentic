---
name: review
description: Use after implementing and before shipping or marking work done. Runs the independent two-pass review (spec compliance, then quality) with the completeness audit and knowledge-sync check.
---

Run lifecycle Stage 3 (Review).

1. Load the stage: `python3 .ai/scripts/okf.py show .ai/lifecycle.md --section "Stage 3: Review"`.
2. At L2 and above delegate to the `reviewer` subagent with the spec, plan, diff, and the command evidence, and save its report (it opens with a `## Verdict` section). At L1 review your own diff against the same two passes.
3. Fix Critical and High findings, then re-review only the fix. Report Medium findings as fixed or accepted.
4. Record it: `lifecycle.py stage review --note "<self-review>"` (L1) or `lifecycle.py stage review --ref <report>` (L2). The stage refuses a verdict that is not Approved.
