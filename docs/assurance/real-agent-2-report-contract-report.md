# Report-contract real-agent evaluation: 1 PASS, 1 FAIL

2026-10-28. Source candidate 6ad08d1 is unchanged. The user explicitly authorized exactly two prepared fixture evaluations through the existing Pro subscription, including copied KIT/fixture transmission to Anthropic and additional subscription quota. No paid API, fallback, extra probe, retry or subsequent allocation was used. No source commit, push, PR or merge occurred.

## Execution and bounds

`python3 .ai/scripts/lifecycle.py reuse assurance-2-real-agent` → RERUN (previous actual obligation failed).

`python3 .ai/scripts/lifecycle.py run assurance-2-real-agent -- python3 docs/assurance/run-real-agent-2-report-contract.py --authorized` → exit 1, source tree 6ad08d1.

The prepared wrapper verified exact source bytes/modes and pinned agent/config inputs; sanitized API/provider overrides; required effective loggedIn/claude.ai/firstParty/Pro auth; and ran the exact argv in operator-2-report-contract/planned-evaluation-command.json from its clean frozen-source copy. The unchanged separate-metadata layout, qualified native observer, guards, permission mode and configuration pin were retained. Original real-agent-2 and real-agent-2-retry results/logs remain unchanged.

Allocation: feature-l2 and control-delta, one cell each; 300-second timeout per cell, 600 agent seconds, 660 wall seconds. Charged agent time: 245.4401319839526 seconds. Both completed within the allocation; no cells timed out.

## Actual outcomes

- feature-l2: PASS, no failure reasons.
- control-delta: FAIL: `review candidate mismatch, source mutation or observed reviewer writes`; `Approved review artifact is not bound to the observed reviewer result`.
- Totals: 1 PASS, 1 FAIL, 0 ERROR, 0 NOT_RUN, 0 RUNNING. The two-cell allocation is exhausted.

`python3 .ai/scripts/lifecycle.py run assurance-2-real-results-report-contract -- python3 .ai/scripts/lifecycle_eval.py results-check docs/assurance/real-agent-2-report-contract.json --require-real` → exit 0 on 6ad08d1. This confirms qualified real-result integrity, not that both behavioral cells passed.

Native identities: Claude CLI 2.1.312, parent and reviewer model claude-sonnet-5-5, effective medium effort. Each cell used one distinct child reviewer with the reviewer role. No observation assertions or result statuses were changed.

## feature-l2 PASS evidence

Parent session a95ae633-14e8-4836-8fb0-b0f44b66dc31; reviewer a140ed91b6f7b9fb7. The requested CLI behavior, tests, convergence, durable lifecycle records and fixture Verify passed the strict evaluation. The complete canonical reviewer body was preserved, with only metadata in YAML frontmatter.

Raw handback, observed reviewer report and saved artifact body all hash to:

`c315d86ccd5f718d81a97d4ad274e9f152932e273aaf5724429a4d4754d66e11`.

No reviewer writes were observed. Before, after, reviewed and final source/spec/plan/convergence pins match. Observed order: convergence sequence 46, delegation 47, reviewer completion 64, Verify 82. Convergence digest remained `4c2a58603b8635356bd286aafdacfc975f9102b2b7ede903aa0b62dde1713c6e`.

This demonstrates that the distributed instruction path can satisfy the unchanged strict evaluator; it does not establish universal agent adherence.

## control-delta FAIL: exact causes

Parent session 890bfd9b-df3f-4c3e-898d-0329764eb97e; reviewer ab779848649b4801d. Requested code behavior, preserved test, convergence and fixture Verify were observed, but the independent-review contract failed in two specific ways.

1. The reviewer reran `lifecycle.py converge knowledge/specifications/named-greeting.md` at 15:51:12Z. Converge publishes evidence; it is not read-only. Source/spec/plan pins stayed identical, but convergence changed during the reviewer interval:
   - before/reviewed: `647ee23a1e405a392c53ab73b9cff727bd0a105276a8f17abce7a0e5590a243f`
   - after: `2d4115f68c9e657c3e334503322165f49fc92884049a298c96239d2655e7ba7d`
   The observer correctly recorded workspace mutation during the review interval. The parent reran convergence again at 15:51:39Z, after review/Verify, leaving final digest `30be18bf4110050e3dfdc5127900bf89fed8c2c5ad4713fc3b67d58900c8b99e`.
2. The reviewer returned a complete canonical report. Its actual handback hash exactly matches observed report hash `8e9f2e2a9567f7c2c60961b0c95d4b78f3d5b824bf8dae0305b4749d156a8d3b`. The parent then rewrote it into a short `# Named greeting review` summary, removing Scope, Persona Applied, Validation Reviewed and Residual Risks and changing the verdict text. Saved artifact body hash: `bd5595b6f0ed49027e394fcaa7aae3c2c3170fc90b6719da2074160c39a82e07`.

These are directly observed parent/reviewer noncompliance with existing preservation/read-only contracts. They are not an observer hash-parser or schema defect: exact raw/observed handback hashes agree, source pins remained stable, and the captured mutating command explains the receipt changes. The strict checks must remain FAIL.

## Diagnosis provenance and next boundary

All diagnosis was local, from retained native transcripts, reviewer handbacks, successful artifact Write/Edit payloads and recorded native pins. Temporary fixture trees were removed normally; artifact bodies were reconstructed from successful payloads. No post-run fixture repair, scoring change or model rerun occurred.

Evidence:

- real-agent-2-report-contract.json and .log(.exit): immutable actual results and execution.
- real-agent-2-report-contract-diagnosis.json: bounded assistant final messages, tool errors and retained native transcript paths.
- real-agent-2-report-contract-review-binding.json and -binding-diff.json: handbacks, exact hashes and successful artifact payloads.
- real-agent-2-report-contract-binding-*.diff: full body differences (feature diff empty; control summary rewrite).
- real-agent-2-report-contract-order.json: parent/reviewer command chronology and exact convergence pins.
- operator-2-report-contract/preparation.json and effective-auth.json: exact frozen source provenance and sanitized subscription authentication.

No further campaign or automatic patch loop is prepared. The strict two-cell real-agent obligation remains failed despite one complete passing cell and local acceptance/review/full-suite PASS. Parent Verify must not be claimed complete using this result. A human decision is needed about the unmet behavioral verification; qualified integrity alone cannot replace it.
