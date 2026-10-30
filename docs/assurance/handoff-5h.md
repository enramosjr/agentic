# Next slice candidate: analysis/convergence documentation input profile

Prepared 2026-10-29 America/Chicago at the user's explicit request: “Commit and push verified 5g, then prepare the handoff for the next slice.” This is a selection/handoff recommendation, not an approved specification, plan or implementation. Continue substantive next-slice work in a fresh chat under AGENTS.md §9.

## Critical checkout and delivered state

Run EVERY repository command with explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Saved-project default `/home/enramosjr/Projects/agentic` is a DIFFERENT checkout. Do not work there, create another worktree, switch/reset or refresh the base.

Existing branch: `claude/assurance-increment-7`. Delivered HEAD: **8cb4d804a620e0761c2bab45846e7cd62c98ddd4** (Add static audit-documentation input profile), pushed to matching origin branch. Delivery `git ls-remote --exit-code origin refs/heads/claude/assurance-increment-7` confirmed remote/local identity. Later context uses local refs only; do not infer another remote check. Tracked status clean after delivery.

Read leading **Delivery complete — authoritative** in implementation-5g.md first. It supersedes historical verified/uncommitted/pending sections. Exactly three tracked files delivered; no PR or merge.

Seven delivered profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract, python-installer-doc-contract, python-validation-policy-contract and python-audit-doc-contract. Preserve all seven complete entries/rationales/behavior and historical evidence. Export remains literal/advisory/manual; inference, full suites, matching, freshness, schemas, gates and receipt exclusions unchanged.

5g evidence: converge-5g.log **6 PASS / 0 FAIL / 0 MANUAL**; independent actual one-test proof, framework/adopter identities/freshness, four intentional static failures, four confirmed omission/matching/actual-zero controls and thirteen confirmed reachable dependency additions. review-5g.md Approved/no findings, full canonical report preserved. One full framework PASS on frozen source tree **db2bf12**, framework-5g.log. Intent/Plan/Review/Verify/Ship closed. No source changed after acceptance/review/full gate.

5g Verify initially refused the original failed guide diagnostic label because the corrected pass used a separate label. `reuse inputs-5g-guide-red` -> RERUN; same-label focused corrected PASS closed it, then Verify/audit succeeded without source changes, convergence rerun or second full gate. Preserve this exact evidence distinction. For future intentional `lifecycle.py run` failures, use the same label for corrected PASS.

Retrospective retains its evidence-backed no-new-lessons closure made before final Verify. A later advisory observation (#1) captured the label issue. Attempted replacement with `retrospect --lessons 1` was refused (`retrospective retry conflicts with recorded closure`); the closure remains unchanged. Observation is captured but unselected and unpromoted. Do not rewrite that history or claim it was selected. No binding promotion.

Delivery reran no product suites. Sandbox and host `reuse inputs-5g-framework` both reported execution-environment/runtime drift, not REUSE or a fresh PASS. Keep historical source/runtime scopes. Suppressed successful child output establishes no full-suite count. Earlier results verify no eighth profile. Preserve 5f and all prior records.

Framework has no knowledge bundle: use `python3 .ai/scripts/repo.py context --json`. NEVER initialize invoking-framework knowledge or invent capability baseline/log/records PASS. `okf.py handoff --prompt` is inapplicable. All docs/assurance stay ignored/local/UNCOMMITTED. Separate docs-only L0 after Ship is solely this handoff; load context then declare NEW L2 with --new. Never reopen 5g or treat L0 as source-edit approval.

## Recommended bounded candidate — NOT approved

Consider one exact-method profile for this existing command:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Tiers.test_analyze_and_converge_are_documented
```

Suggested ID: `python-analysis-convergence-doc-contract`. Neither ID nor candidate is approved. The method loops over three literal paths: `.ai/lifecycle.md`, `.ai/docs/lifecycle.md`, `.ai/validation-policy.md`. In each whole document it requires `lifecycle.py analyze` and `lifecycle.py converge`. A separate literal read of validation-policy requires `cites a passing converge run of an identical command on the current tree`.

These are seven case-sensitive substring assertions, not seven tests. They establish no section placement, command validity, actual analysis/convergence, evidence matching/reuse, record behavior, enforcement, native/model/session behavior or governance. No extracted command executes and no lifecycle attribute is accessed. Exactly one actual passing test is a future acceptance expectation, not current runtime proof. The method copies nothing.

Proposed ordered scope for analyst investigation, NOT approved:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.ai/lifecycle.md
.ai/docs/lifecycle.md
.ai/validation-policy.md
```

First pattern conservatively covers production eager imports and lazy-loader/decorator construction, including unused non-test descendants and future supported scripts. Extra invalidation and final completeness require approval. Exclusion restores selected module/imported helper; last three literals are direct reads. Root AGENTS is not implied by this method, though prior-profile compatibility fixtures still need it. Broader Tiers class/module/sibling registration is not approved.

## Nonexecuting selection evidence

- `test_lifecycle_conformance.py:208-212`: inspected exact method. It combines a bounded literal path loop with an additional literal text call. The independent source-derived read oracle must resolve both paths of dataflow: tuple elements bound to `path` for two text calls, plus the explicit validation-policy read. Literal-call-only extraction finds policy alone and silently misses two documents; copying 5g's loop-only oracle also misses the separate call boundary. Verify both, deduplicate to three direct documents and pin the reviewed method. This remains bounded inspection, not universal dataflow discovery.
- `.ai/lifecycle.md:44,59,163,167`, `.ai/docs/lifecycle.md:8,10`, `.ai/validation-policy.md:27`: structured search found command tokens/current required phrase; phrase is on the policy's long line. Terms can occur multiple times. Future removal fixtures must remove every occurrence of the chosen token from that document. Presence does not validate prose or command behavior.
- Shared root/import setup and text helper are `test_lifecycle_conformance.py:15-27`; entry point `:297-298`. Future analyst must recheck the actual closure, including disk_tmp/scratch.require_disk, lifecycle eager imports/lazy setup, review_guard/ledger initialization and protected/nested decorate construction. 5g pins and thirteen reached variants are mechanism references, not eighth-profile proof.
- disk_tmp may probe mounts, create cache paths and update environment. Runtime/executable/storage/mount effects remain outside repository-file claims. Uncalled wrapped producer bodies may be conservatively pinned but not claimed reachable.
- For every newly claimed reachable addition, confirm mutation bytes; absent excluded data must actually break selected execution before supplying data, proving exactly one passing test, then requiring intended boundary rejection. Insert AST body changes after docstrings and before earliest decorator of the first statement.
- Actual-zero control must ignore selector in a disposable empty suite, independently confirm Ran 0 tests and reject count before Python-dependent exit. A missing exact method can instead produce one loader _FailedTest.

No next-slice product test, extracted command or runtime qualification ran during selection.

## Decisions for the fresh analyst chat

Apply spec skill, bounded analyst/Python persona reads and analyst delegation required by skill. Draft ignored specification-5h.md or named equivalent. Present consequential decisions in the new chat before planning/coding:

1. Approve exact method and suggested ID, select another candidate or stop expansion? Recommend exact method/ID only.
2. Approve seven ordered patterns with conservative extra production invalidation or require a smaller independently justified closure? Recommend seven, explicit per-pattern rationales and runtime/read-completeness limits. Resolve the mixed loop-plus-literal oracle independently rather than copying 5g extraction.
3. Approve independent actual one-test proof, public export/framework run/reuse and ordinary-adopter freshness/identity; unrelated-test/non-input-document reuse; separate invalidation for all three direct docs, target/helper, representative production import and new supported script; exact argv/ordered declaration identity, receipt exclusions and source-derived boundary controls? Suggested static failures: remove each of two command tokens from each of three docs, plus remove the separate required policy phrase: **seven cases**. Suggested omission/matching/count controls: omit each direct doc, loose matching, actual zero: **five controls**. Counts/breadth are recommendations requiring approval and must follow actual inspected source. Freshness edits preserve assertions/restore bytes; static failures are separate.
4. Preserve all SEVEN complete existing profiles, inference/full suites/schemas/matching/gates/manual advisory adoption, and claim substring presence only? Recommend yes, excluding real analysis/convergence/evidence/reuse/enforcement/native/model/session behavior.

No next spec or plan is approved. Obtain explicit human spec approval, then separately approved implementation plan. Nonexecuting analyze/trace may run during drafting. No old suite rerun merely for a new chat; historical results verify no eighth profile.

## Restrictions and first action

Fresh chat starts with read-only context/spec drafting. No source edits, product-test execution, implementation plan before spec approval, native/model evaluation, session registration/allocation, fixture trust grants, historical rescoring/evidence modification, new worktree, invoking-framework knowledge bundle, commit/push/PR/merge or base refresh during initial drafting. All native allocations remain consumed. 5g commit/push authorization is fulfilled and does not carry forward. Do not launch autonomy_driver.

Suggested fresh-chat prompt:

> Start from docs/assurance/handoff-5h.md. Run every repository command with explicit cwd /home/enramosjr/Projects/agentic-assurance-7. Read authoritative delivery update in implementation-5g.md. Inspect exact candidate, including mixed literal path loop and explicit policy read, then draft a specification. Present consequential decisions in this new chat before planning/coding. Keep docs/assurance ignored/local/uncommitted; preserve delivered HEAD/branch. No product tests, source edits, native/model/session/trust actions, knowledge bundle, base refresh or delivery during initial drafting.
