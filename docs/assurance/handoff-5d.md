# Next slice candidate: reviewer-report contract input profile

Prepared 2026-10-29 America/Chicago. Selection/handoff only, not an approved specification or plan. The user requested identifying the next segment and continuing. AGENTS.md section 9 requires a fresh conversation after a delivered slice; do not implement the next slice in the 5c chat. A new user-owned chat needs the user's authorization to create it.

## Checkout and delivered state

Run EVERY repository command with explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Saved-project default `/home/enramosjr/Projects/agentic` is a different checkout. Do not create a worktree, change branches, reset, refresh the base or use the other checkout.

Branch `claude/assurance-increment-7`; delivered HEAD `652a77b811cb8ac0584940a990d6f266bb4acefd`, pushed to matching origin branch. Remote/local identity was confirmed at 5c delivery. Current repo context reports clean tracked status and equal local refs without a new remote verification. Read the leading Delivery complete update in implementation-5c.md, which supersedes historical pending language.

Three delivered profiles: python-runner-test, python-architecture-compatibility and python-harness-wiring. Export remains literal/advisory/manual, with unchanged inference, full-suite coverage, schemas and gates. Preserve all three profiles and their evidence.

5c evidence: 6 PASS / 0 FAIL / 0 MANUAL convergence, five confirmed controls, six malformed/missing-wiring cases, Approved independent review, one full framework PASS on source tree 1bfe7b7. Intent/Plan/Review/Verify/Ship closed. Retrospective closed with no new lessons. Delivery reuse reported runtime/environment drift, not a fresh PASS or REUSE; retain original source/runtime scopes and never use them to verify a fourth profile.

Framework has no knowledge bundle: use repo.py context --json, never initialize knowledge or invent capability baselines. All docs/assurance artifacts remain ignored/local/UNCOMMITTED. A separate documentation-only L0 declaration was used for this handoff, leaving the closed 5c record unchanged. In the new chat, declare a NEW L2 lifecycle with --new after loading context; do not reuse L0 or reopen 5c.

## Recommended next bounded slice

Propose one exact-method profile for the EXISTING command:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py RolesAndSkills.test_reviewer_completion_report_contract
```

Suggested ID: `python-reviewer-report-contract`. This adds role-registration TOML and role/skill/lifecycle Markdown reads to the existing profile examples. It would demonstrate a method-selected static governance check with explicit non-code inputs, without broadening full-suite behavior or adding native/model qualification. The target method contains one unittest test with subtests; actual one-test execution must be proven later, not inferred from source alone.

Candidate ordered scope, NOT approved:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.claude/agents/reviewer.md
.codex/agents/reviewer.toml
.ai/agents/reviewer.md
.ai/lifecycle.md
.claude/skills/review/SKILL.md
```

The first pattern conservatively covers production eager imports/lazy setup, including unused non-test descendants and future supported scripts; extra invalidation is a deliberate proposed tradeoff, not a copied-directory requirement. The target imports disk_tmp/lifecycle just as HarnessWiring does. Inspect actual current closure before approving scope; do not infer completeness from prior acceptance or import lists alone.

## Inspected target evidence

- test_lifecycle_conformance.py:15-27 calculates root, imports disk_tmp/lifecycle and defines direct text reads. Same module import-time boundaries as 5c; temporary-storage/mount/runtime effects remain outside repository-file scope.
- :68-91 selected method reads exactly five direct documents listed above. SHOW regex extracts command strings from the two role registrations; shlex.split parses the first match and checks Completion report section loading. It does not execute those strings or parse TOML structurally.
- :77-91 checks canonical reviewer report headings/directions and preservation language in lifecycle review instructions and review skill.
- :297-298 direct unittest main exists. No executing check was run during selection.
- .claude/agents/reviewer.md:11 and .codex/agents/reviewer.toml:6 currently contain the inspected show command and Completion report section.
- Full RolesAndSkills is NOT selected: other methods recurse directories, inspect a directory symlink/registration inventory and execute discovered show commands (:93-131). Full-class/module scope needs separate investigation and cannot inherit this proposed method boundary.

Claim static reviewer-report instruction conformance only. This command does not prove actual reviewer behavior, independent review execution, native enforcement, model adherence or session authenticity.

## Decisions for the fresh analyst chat

Draft ignored specification-5d.md, after bounded analyst/Python persona reads and spec skill, and present decisions to the user before planning/coding:

1. Exact method command and suggested ID only versus broader forms. Recommend exact method only, no aliases/full class/module.
2. Nine ordered patterns versus a smaller independently justified production scope. Recommend nine with accurate per-pattern rationale and documented extra invalidation; inspect current eager/lazy import setup and all five reads first.
3. Independent actual one-test proof before exit interpretation; public export/run/reuse and ordinary-adopter freshness; unrelated test/document reuse; each direct doc/target/helper/representative production edit invalidation; exact command and ordered declaration identity; confirmed omitted-TOML and omitted-Markdown freshness controls plus loose-command/zero-test controls. Final breadth and expected outputs require human specification approval. Fixture Markdown edits for freshness should preserve target conformance so static failure is not confused with staleness.
4. Advisory/manual application, preserving all existing profiles/inference/full suites/schemas/gates. Recommend yes; no target/role/skill/hook contract edits by analogy, no native/model or review-session allocation.

No spec is approved by this recommendation. Obtain explicit spec approval, then a separately approved implementation plan. No product tests before approval/implementation stage. Analyze/trace may run without executing product checks.

## Restrictions and next action

Continue with fresh-chat spec drafting only. No source edits, product-test execution, implementation plan before spec approval, native/model evaluations, native session registration/allocation, fixture trust grant, historical rescoring/evidence modification, new worktree, knowledge bundle, commit, push, PR, merge or base refresh. All native allocations are consumed. 5c commit/push authorization was fulfilled and does not carry forward.

Do not launch autonomy_driver; this is an interactive bounded slice. If the human authorizes creating the fresh chat, create it with the exact checkout override and this handoff, then wait for its initial spec/decision handback as appropriate. Otherwise give the user the handoff and ask them to start a fresh chat from it.
