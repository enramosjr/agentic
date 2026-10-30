# Next slice candidate: validation-policy documentation input profile

Prepared 2026-10-29 America/Chicago after explicit user authorization: “Commit and push verified 5e, then prepare the handoff for the next slice.” This is a selection/handoff recommendation, not approved specification, plan or implementation. Continue substantive next-slice work in a fresh chat under AGENTS.md section9. Do not implement another slice in the delivered 5e chat.

## Critical checkout and delivered state

Run EVERY repository command with explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Saved-project default `/home/enramosjr/Projects/agentic` is a DIFFERENT checkout. Do not work there, create another worktree, switch branches, reset or refresh the base.

Existing branch: `claude/assurance-increment-7`. Delivered HEAD: **4b89221b6f1c416303452abd57fb4fb15816b2b3** (Add static installer documentation input profile), pushed to matching origin branch. `git ls-remote --exit-code origin refs/heads/claude/assurance-increment-7` confirmed remote/local identity at delivery. Later repo context uses local refs only; do not infer another remote check. Tracked status is clean after delivery.

Read the leading **Delivery complete — authoritative** update in implementation-5e.md first; it supersedes historical pending/uncommitted sections. Exactly three tracked files were delivered. No PR or merge.

Five delivered profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract and python-installer-doc-contract. Preserve all five entries, rationales, behavior and historical evidence. Export remains literal/advisory/manual; existing inference, full suites, matching, freshness, schemas, gates and receipt exclusions remain unchanged.

5e evidence: converge-5e.log **6 PASS / 0 FAIL / 0 MANUAL**; independent actual one-test proof; framework/adopter freshness and identities; seven intentional static failures; five confirmed omission/matching/actual-zero controls; 13 confirmed reachable dependency additions. Canonical review-5e.md Approved/no findings. Full framework PASS once on frozen source tree **a872f48**, framework-5e.log. Intent/Plan/Review/Verify/Ship closed. Retrospective closed with advisory lesson1 about placing AST mutations before decorators; no binding promotion. Preserve 5d and all earlier records in their original scopes.

Delivery changed no source and reran no product suites. `lifecycle.py reuse inputs-5e-framework` reported execution-environment/runtime drift, not fresh PASS or REUSE. Keep original source/runtime scopes. Suppressed successful child output gives no full-suite test count. Historical results do not verify a sixth profile.

Framework mode has no knowledge bundle: use `python3 .ai/scripts/repo.py context --json`. NEVER initialize knowledge or invent a capability baseline/log/records PASS. `okf.py handoff --prompt` is inapplicable. All docs/assurance artifacts remain ignored/local/UNCOMMITTED. A separate docs-only L0 declaration after Ship was solely for this handoff; begin a NEW L2 lifecycle with --new after context loading in the fresh chat. Never reopen 5e or treat L0 as source-edit approval.

## Recommended bounded candidate — NOT approved

Consider one exact-method profile for the EXISTING command:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Relocation.test_agents_md_points_to_the_policy_and_the_policy_keeps_its_must_rules
```

Suggested ID: `python-validation-policy-contract`. It checks static text references and location of four named policy strings across root AGENTS.md and .ai/validation-policy.md. It does NOT prove policy compliance, actual reuse/wait/batch enforcement, native hooks, agent behavior or dynamic governance. It executes no extracted commands. Exactly one actual passing test is a future acceptance expectation, not current runtime evidence.

Proposed ordered scope for analyst investigation, NOT approved:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
AGENTS.md
.ai/validation-policy.md
```

The first pattern conservatively covers eager production imports and lazy-loader/decorator setup, including unused non-test descendants and future supported scripts. It is not a script-copy boundary; this selected method copies nothing. The exclusion then restores selected module/helper. The final two literals are direct text reads; root AGENTS.md must be explicit despite general Markdown freshness exemptions. Extra invalidation and final completeness require human approval.

## Nonexecuting selection evidence

- `test_lifecycle_conformance.py:15-27,134-146,297-298`: root/import setup, called text(path), single selected method and direct unittest entry point inspected. It reads AGENTS.md and .ai/validation-policy.md, requires the policy path and “MUST load it by section” in AGENTS, then requires four rule strings in policy and absent from AGENTS. No test or extracted command ran during selection.
- Four strings: “MUST NOT rerun an unchanged failing check”; “`--max` below 300 s is a violation”; “MUST be split before work continues”; “MUST NOT satisfy §8.1 by adding tests whose only purpose is more evidence”. These are literal text assertions, not checks that their rules are followed.
- `AGENTS.md:234`, `.ai/validation-policy.md:3,11,15,28,33`: structured search found current policy reference/loading instruction and policy term locations. Prior bounded sections were read during 5e; future analyst must inspect actual current text rather than treating this selection as universal completeness proof.
- `disk_tmp.py:10-20` calls scratch.require_disk, with potential cache/environment changes and mount/storage probing. Selected module imports lifecycle eagerly. The familiar scratch/lifecycle/review_guard/ledger initialization and lazy/protected setup must be checked again for this candidate; selected method accesses no lifecycle attributes. Keep runtime/executable/storage/mount effects outside repository-file claims.
- Sibling/class/module coverage is not approved. Other conformance classes execute commands, inspect historical Git data or read broader inventories. Never inherit their behavior by analogy.
- 5e dependency guards include fixed setup/called-body pins and a selected-method pin. Its 13 variants cover six module initializations, selected method, text, require_disk, lazy, protected, nested decorate and an excluded helper import. Each first proves missing excluded data actually breaks the selected command, then supplies data and proves exactly one passing test before checking boundary rejection. Reuse mechanisms only after independently justifying this candidate's actual closure, not by copying the number13.
- AST mutation insertion must occur after docstrings and before the first statement's earliest decorator. An insertion between @wraps and def was a confirmed fixture defect fixed in 5e. Uncalled wrapped producer bodies are covered conservatively by pins but must not be described as reachable on this selected path.
- Actual zero control must ignore the selector in a disposable empty suite and confirm Ran0 before count rejection. A missing exact method can produce one loader _FailedTest. Confirm mutation bytes and intended failure; neither a passed static scan nor a no-op mutation is proof.

## Decisions to present in the fresh analyst chat

Apply bounded analyst/Python persona reads and the spec skill. Draft ignored specification-5f.md (or clearly named equivalent) and present consequential decisions BEFORE planning/coding:

1. Approve the exact candidate and ID above, choose another candidate or stop profile expansion? Recommend exact method/ID only. Selection is not approval.
2. Approve six ordered patterns and conservative extra production invalidation, or require a smaller independently justified closure? Recommend six with per-pattern rationale and runtime/read-completeness limits, explicitly preserving root AGENTS.md as an input.
3. Approve independent actual one-test proof; public export/framework run/reuse and ordinary-adopter freshness; unrelated-test/non-input-document reuse; separate invalidation for both direct documents, target/helper, representative production import and new supported script; exact argv/ordered declaration identity; confirmed omission of either direct document, loose matching and actual-zero controls; source-derived reachable boundary controls; and targeted static failures? Suggested static failures are removal of either required AGENTS token, removal of each of four policy strings, and insertion of each forbidden string into AGENTS (ten separate cases). Suggested omission/matching/count controls total four. Final breadth/expected output needs human approval; counts here are recommendations only. Freshness edits should preserve all selected assertions and restore original bytes; deliberate static failures remain separate.
4. Preserve explicit advisory/manual adoption, all FIVE existing profiles/inference/suites/schemas/gates and static documentation-location claims only? Recommend yes. No actual policy enforcement/native/model/session qualification by analogy.

No next specification is approved. Obtain explicit human spec approval, then separately approved implementation plan. Nonexecuting analyze/trace may run during drafting. Do not rerun old product suites merely for a fresh chat or claim historical PASS verifies the sixth profile.

## Restrictions and first action

Fresh chat begins with read-only context/specification drafting. No source edits, product-test execution, implementation plan before spec approval, native/model evaluations, native session registration/allocation, fixture trust grants, historical rescoring/evidence modification, new worktree, knowledge bundle, commit/push/PR/merge or base refresh during initial drafting. All native allocations remain consumed. 5e commit/push authorization was fulfilled and does not carry forward. Do not launch autonomy_driver.

Suggested fresh-chat prompt:

> Start from docs/assurance/handoff-5f.md. Run every repository command with explicit cwd /home/enramosjr/Projects/agentic-assurance-7. Read the authoritative delivery update in implementation-5e.md. Inspect the candidate and draft its specification; present consequential decisions here before planning/coding. Keep docs/assurance artifacts ignored/local/uncommitted, preserve existing branch and delivered HEAD. No product tests, source edits, native/model/session/trust actions, knowledge bundle, base refresh or delivery actions during initial drafting.
