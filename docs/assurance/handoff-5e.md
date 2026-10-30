# Next slice candidate: installer-documentation input profile

Prepared 2026-10-29 America/Chicago after the user's authorization: “Commit and push verified 5d, then prepare the handoff for the next slice.” This is a selection/handoff recommendation, not approved specification, plan or implementation authorization. Continue substantive work in a fresh chat under AGENTS.md section9; do not implement another slice in the delivered 5d chat.

## Critical checkout and delivered state

Run EVERY repository command with explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Saved-project default `/home/enramosjr/Projects/agentic` is a DIFFERENT checkout. Do not work there, create a worktree, change branches, reset or refresh the base.

Existing branch: `claude/assurance-increment-7`. Delivered HEAD: **bd34de90f4eb84c5be19d306418404e61a6985e5** (Add static reviewer report contract input profile), pushed to matching origin branch. Remote/local identity confirmed at delivery by git ls-remote. Subsequent repo context uses local refs only; no new remote check should be inferred. Tracked status is clean.

Read the leading **Delivery complete — authoritative** update in implementation-5d.md first; it supersedes historical pending/uncommitted text below it. Exactly three tracked files were delivered. No PR or merge.

Four delivered profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring and python-reviewer-report-contract. Export remains literal/advisory/manual. Existing inference, full-suite coverage, schemas, matching and gates remain unchanged. Preserve all four entries, rationales, behavior and historical evidence.

5d evidence: six requirements PASS/0 FAIL/0 MANUAL in converge-5d-complete.log; five intentional static contract failures; seven original confirmed controls; eight additional confirmed reachable dependency-boundary variants; final independent review Approved in review-5d.md; full framework PASS once on frozen source tree **0eb9132** in framework-5d.log. Earlier candidate convergence/review reports remain historical, with the two R2 findings resolved by final source. Intent/Plan/Review/Verify/Ship are closed. Retrospective selected advisory lesson1; no binding rule promoted.

Delivery changed no source and reran no product tests. lifecycle reuse reported execution-environment/runtime drift, not fresh PASS or REUSE. Preserve original source/runtime scopes; historical results do not verify a fifth profile. Full-suite counts are not inferred from suppressed child output.

Framework mode has no knowledge bundle: use `python3 .ai/scripts/repo.py context --json`. Never initialize knowledge, invent capability baselines or claim records PASS; okf.py handoff --prompt is inapplicable. All docs/assurance artifacts remain ignored, local and UNCOMMITTED. A separate docs-only L0 declaration was made after Ship solely for this handoff; in the new chat start a NEW L2 lifecycle with --new after loading context. Never reopen 5d or treat that L0 as approval for source edits.

## Recommended bounded candidate — not approved

Consider one exact-method profile for the EXISTING command:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Distribution.test_readme_and_playbook_document_the_installer
```

Suggested ID: `python-installer-doc-contract`. This introduces an explicit non-Markdown text input (.ai/VERSION) alongside installer docs. Claim only static documentation-token and numeric version-format consistency. The method does not run the installer, install/upgrade an artifact, validate drift/conflicts, activate hooks, grant trust or prove version compatibility. Do not call its regex full semantic-version validation.

Proposed ordered scope for analyst investigation, NOT approved:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.ai/README.md
.ai/docs/install-and-upgrade.md
.ai/VERSION
```

The first pattern conservatively covers production eager imports/lazy setup, including unused non-test descendants and future supported scripts. It is not a copied-script boundary. This selected method copies nothing. Extra invalidation is a proposed tradeoff, not minimum discovered scope. The three literals are direct reads. Inspect actual current closure before approving; preserve runtime/storage limitations.

## Nonexecuting selection evidence

- test_lifecycle_conformance.py:15-27 imports disk_tmp/lifecycle, calculates root and defines text(path). The shared import/runtime boundary is familiar from 5d but must be checked against current source, not copied by analogy.
- :60-65 selects one unittest method. It checks install.py text within README Quick start, five terms in the installation playbook (--check, --force, --no-knowledge, conflict, /hooks), and VERSION matching digits.digits.digits followed by newline. Exactly one actual passing test is a future expectation, not a fresh execution result. Direct unittest main exists at297-298.
- :30-58 is the unselected sibling method: imports installer/evaluator, examines real kit inventories and prepares fixture distribution files. Full Distribution/class/module scope must not inherit this proposed method profile.
- .ai/README.md:6-17, .ai/docs/install-and-upgrade.md:1-27 and .ai/VERSION were read. VERSION currently contains 0.1.0 plus newline. No installer, product test or extracted command was executed during selection.
- 5d's final oracle in test_assurance_inputs.py includes a fixed selected-method pin, setup fingerprints, called-body pins and eight confirmed reachable additions. Positive import sentinels alone missed added helper/import-time reads; excluding text(path)'s body also missed a new directly called read. Reuse mechanisms only after inspecting this method's actual boundary. Fixed pins are conservative review guards, not general dependency discovery.
- An empty module under an exact method selector can yield one loader _FailedTest. A zero-test control must confirm an actual empty suite (ignoring selector in the disposable fixture), assert Ran0 independently, and reject it at count-before-exit. This is the closed advisory 5d lesson, not native/model proof.

## Decisions to present in the fresh analyst chat

Apply bounded analyst/Python persona reads and the spec skill. Draft ignored specification-5e.md (or clearly named equivalent) and present consequential decisions BEFORE planning/coding:

1. Approve this exact method/ID, choose another candidate, or stop profile expansion? Recommend the exact method above if continuing this series; no broader command forms. Selection is not approval.
2. Approve seven ordered patterns and extra invalidation, or require a smaller independently justified import closure? Recommend seven with accurate per-pattern rationale and explicit runtime/read-completeness limits.
3. Approve future independent actual one-test proof; public export/framework run/reuse and ordinary-adopter freshness; unrelated test/document reuse; separate invalidation for each direct doc/VERSION, target/helper, representative production source and new supported script; exact command/ordered declaration identity; confirmed omitted-document/VERSION, loose-command and actual-zero controls; and targeted README/playbook/version-format failure cases? Final breadth and expected outputs require human approval. Keep freshness edits conformance-preserving: arbitrary whitespace can invalidate VERSION's exact format, so use another valid numeric version and restore original bytes. Static-failure controls must be separate.
4. Preserve advisory/manual adoption, all FOUR prior profiles/inference/suites/schemas/gates, and static installer-doc claims only? Recommend yes. No installation behavior or native/model/session qualification by analogy.

No next specification is approved. Obtain explicit human spec approval, then a separately approved implementation plan. Analyze/trace can run without product execution. Do not rerun old suites merely for fresh chat or present historical evidence as new-profile proof.

## Restrictions and first action

Fresh chat starts with read-only context/specification drafting. No source edits, product-test execution, implementation plan before spec approval, native/model evaluations, session registration/allocation, fixture trust grant, historical rescoring/evidence modification, new worktree, knowledge bundle, commit/push/PR/merge or base refresh. All native allocations remain consumed. 5d commit/push authorization was fulfilled and does not carry forward. Do not launch autonomy_driver.

Suggested fresh-chat prompt:

> Start from docs/assurance/handoff-5e.md. Run every repository command with explicit cwd /home/enramosjr/Projects/agentic-assurance-7. Read the authoritative delivery update in implementation-5d.md. Inspect the candidate, then draft its specification and present consequential decisions here before planning or coding. Keep all docs/assurance artifacts ignored/local/uncommitted; preserve the existing branch and delivered HEAD. No product tests, source edits, native/model/session/trust actions, knowledge bundle, base refresh or delivery actions during initial drafting.
