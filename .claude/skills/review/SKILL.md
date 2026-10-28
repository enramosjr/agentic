---
name: review
description: Use after implementing and before shipping or marking work done. Runs the independent two-pass review (spec compliance, then quality) with the completeness audit and knowledge-sync check.
---

Run lifecycle Stage 3 (Review).

For an explicitly opted-in mechanically bound task, load `.ai/lifecycle.md` section `Mechanically bound review (opt-in)`. The parent prepares native capture before spawning the reviewer; during the interval all protected writers are frozen. The reviewer returns the full canonical report. The parent uses `lifecycle.py review save-report` and records Review from the reserved path; it must not reconstruct the report, rerun convergence or treat pending capture as approval.

1. Load the stage: `python3 .ai/scripts/okf.py show .ai/lifecycle.md --section "Stage 3: Review"`.
2. At L2 and above, after OKF sync run `python3 .ai/scripts/lifecycle.py converge <spec>` and fix any FAIL, then delegate to the `reviewer` subagent with the spec, plan, diff, the converge output and the other command evidence, and save its report (it starts with `# Review Report` and contains `## Verdict`; its `## Validation Reviewed` section cites the converge result and each MANUAL requirement ID). At L1 review your own diff against the same two passes.
   Save the complete returned Markdown body unchanged, including its title and every section. Existing YAML frontmatter may hold metadata outside that body; replace any scaffold body with the returned report. Do not add a heading, introduction, summary or verdict to its body, or rewrite its content. If the handback is noncanonical, request a corrected complete report from the reviewer; the parent must not reconstruct an independent approval.
3. Fix Critical and High findings, then re-review only the fix. Report Medium findings as fixed or accepted.
4. Record it: `lifecycle.py stage review --note "<self-review>"` (L1) or `lifecycle.py stage review --ref <report>` (L2). The stage refuses a verdict that is not Approved.
5. Check the closing retrospective before Verify: selected evidence-backed lessons or an explicit no-new-lessons reason. Capture alone does not close it. Check that delivery reports the outcome and treats retrieved observations as advisory.
