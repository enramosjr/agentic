# Addendum: preserve canonical reviewer reports

User requested continuation of the focused report-format/preservation repair. Analyst confirmed this enforces existing canonical-template and exact-body provenance contracts; it adds no gate policy, schema, observer or hashing semantics. Approved specification R1-R8 and the hash-bound original plan stay unchanged. This addendum records implementation detail for existing Steps4-5 and R8 compatibility; it does not claim human approval of new behavior.

## Evidence

Both reviewer registrations require returning the role completion report but make loading its template optional. The role already defines # Review Report and ## Verdict. The skill incorrectly says the report opens with ## Verdict. Existing lifecycle/observer hashing excludes YAML frontmatter and trims outer whitespace, while eval_outcome requires saved and observed report hashes to match. Native retry results pin parent prefixing and parent rewriting as failures. Existing failed runs remain immutable.

## Steps and checks

1. Write focused conformance RED: both registrations must initially load Completion report; role must require complete canonical final Markdown with no preface/fence; parent skill/lifecycle must preserve the entire returned body, allow only existing YAML metadata outside it and request reviewer corrections instead of authoring a verdict.
2. Repair only .claude/agents/reviewer.md, .codex/agents/reviewer.toml, .ai/agents/reviewer.md, .claude/skills/review/SKILL.md and .ai/lifecycle.md Stage3. Record focused GREEN. No scorer, observer or report-hash change.
3. Add bounded OutcomeTests regression: intact canonical body and YAML metadata bind; parent prefix, summary/rewrite and manufactured verdict fail exact report binding even after legitimate lifecycle artifact hashes are refreshed and audit passes. Confirm an ignored broken variant of the binding check is rejected. Retain existing identity/order/write checks.
4. Confirm independent registration-loading and parent-preservation mutations are rejected. Refresh required convergence for current candidate, get independent review, and preserve its report body unchanged. Run the full applicable framework suite once on the frozen reviewed candidate; consult reuse before repeats. Framework has no knowledge bundle, so update existing docs and ignored evidence only.

## Commands

- `python3 -m unittest discover -s .ai/scripts/tests -p test_lifecycle_conformance.py -k reviewer_completion_report_contract`
- `python3 -m unittest discover -s .ai/scripts/tests -p test_lifecycle_eval.py -k reviewer_report_body_binding`
- `python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-2.md`
- `python3 .ai/scripts/lifecycle.py run assurance-2-framework -- python3 .ai/scripts/run_tests.py -j 8`

## Boundary

No new model calls authorized. Deterministic checks do not convert failed real-agent results into PASS and cannot satisfy the outstanding real evaluation. Do not commit, push, open a PR or Git merge. Do not modify the original approved spec/plan or scorer to accept rewritten approvals. Original a491524 evidence remains historical; changed candidate needs appropriately refreshed evidence. Another external allocation needs a separate user decision.
