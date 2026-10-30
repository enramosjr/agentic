# Next slice candidate: stage documentation and runtime stage-name input profile

Prepared 2026-10-29 America/Chicago at the user's explicit request: “Commit and push verified 5h, then prepare the handoff for the next slice.” This is a selection/handoff recommendation, not an approved specification, plan or implementation. Continue substantive next-slice work in a fresh chat under AGENTS.md §9.

## Critical checkout and delivered state

Run EVERY repository command with explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Saved-project default `/home/enramosjr/Projects/agentic` is a DIFFERENT checkout. Do not work there, create another worktree, switch/reset or refresh the base.

Existing branch: `claude/assurance-increment-7`. Delivered HEAD: **0efa2240b6109f6e69fe7a5dacaa3f9be16482c2** (Add static analysis-convergence documentation input profile), pushed to matching origin branch. Delivery `git ls-remote --exit-code origin refs/heads/claude/assurance-increment-7` confirmed remote/local identity. Subsequent context uses local refs only; do not infer another remote check. Tracked status clean after delivery.

Read leading **Delivery complete — authoritative** in implementation-5h.md first. It supersedes historical verified/uncommitted/pending sections. Exactly three tracked files delivered; no PR or merge.

EIGHT delivered profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract, python-installer-doc-contract, python-validation-policy-contract, python-audit-doc-contract and python-analysis-convergence-doc-contract. Preserve all eight complete entries/rationales/behavior and historical evidence. Export remains literal/advisory/manual; inference, full suites, matching, freshness, schemas, gates and receipt exclusions unchanged.

5h evidence: converge-5h.log **6 PASS / 0 FAIL / 0 MANUAL**; independent actual one-test proof, framework/adopter identities/freshness, seven intentional static failures, five confirmed omission/matching/actual-zero controls and thirteen individually confirmed reachable dependency additions. review-5h.md Approved/no findings; full canonical report preserved. One full framework PASS on frozen source tree **fab7ae8**, framework-5h.log. Intent/Plan/Review/Verify/Ship closed. No source changed after acceptance/review/full gate.

5h corrected intentional method-pin and guide diagnostics under their SAME lifecycle run labels after reuse returned RERUN. Preserve that distinction and keep same-label corrected PASS for future deliberate run failures. Retrospective closed before Verify with evidence-backed no-new-lessons reason; no selected new lesson or binding promotion. Prior observations remain advisory.

Delivery reran no product suites. Sandbox and host reuse both reported execution-environment/runtime drift, not REUSE or a fresh PASS. Keep historical source/runtime scopes. Suppressed successful child output establishes no full-suite count. Earlier results verify no ninth profile. Preserve 5g and earlier evidence unchanged.

Framework has no knowledge bundle: use `python3 .ai/scripts/repo.py context --json`. NEVER initialize invoking-framework knowledge or invent capability baseline/log/records PASS. `okf.py handoff --prompt` is inapplicable. All docs/assurance stay ignored/local/UNCOMMITTED. Separate docs-only L0 after Ship is solely this handoff. Fresh chat loads context then declares NEW L2 with --new; never reopen 5h or treat L0 as source approval.

## Recommended bounded candidate — NOT approved

Consider one exact-method profile for the existing command:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Tiers.test_every_stage_the_script_gates_is_described_in_the_lifecycle
```

Suggested ID: `python-stage-doc-contract`. Neither ID nor candidate is approved.

The selected method at `test_lifecycle_conformance.py:197-201` reads `.ai/lifecycle.md` once via literal `text`. It loops over FIVE literal heading labels and requires each corresponding `## {heading}\n` substring. The labels are Stage 0 Intent, Stage 1 Plan, Stage 3 Review, Stage 4 Verify and sync, Stage 5 Ship. Stage 2 is NOT checked. It separately asserts `set(lifecycle.STAGES)` equals the literal set {intent, plan, review, verify, ship}. This is five case-sensitive newline-sensitive substring checks plus one runtime set-equality assertion within ONE test, not six tests.

CRITICAL DIFFERENCE from 5h: this method DOES access a runtime lifecycle attribute. `lifecycle.py:71` defines STAGES as a five-element tuple. Do not repeat 5h's no-lifecycle-attribute claim, or treat source-only extraction of STAGES as proof of its runtime value. The selected command imports lifecycle and evaluates the attribute; future acceptance needs actual execution/count proof. Set equality ignores order and duplicate values; the method proves neither tuple order nor uniqueness/type. Heading substrings prove neither correct sections/bodies/order nor real stage gates/enforcement. The method runs no lifecycle command, executes no extracted command and copies nothing.

Proposed ordered scope for analyst investigation, NOT approved:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.ai/lifecycle.md
```

The first pattern conservatively covers production eager imports, runtime STAGES definition/access and lazy-loader/decorator construction, including unused non-test descendants and future supported scripts. Extra invalidation requires approval. Exclusion restores selected module/imported helper; final literal is the direct document read. Root AGENTS, .ai/docs/lifecycle.md and validation-policy are not this method's direct reads, although prior-profile compatibility fixtures require their own inputs. Broader Tiers class/module/sibling registration is unapproved.

## Nonexecuting selection evidence and investigation cautions

- `test_lifecycle_conformance.py:197-201` and `lifecycle.py:70-76` were inspected after delivery without executing the candidate. Source-derived oracle must independently resolve the literal document call, heading tuple/interpolation and lifecycle.STAGES attribute/set comparison; pin the reviewed method and relevant setup. The loop binds heading labels, NOT file paths. Do not copy 5g's path-loop oracle or 5h's mixed path-loop/literal union. Future runtime proof is separate from structural oracle checks.
- Shared root/import setup and text are `test_lifecycle_conformance.py:15-27`; entry point :297-298. Reinspect actual closure including disk_tmp/scratch.require_disk, lifecycle eager imports/lazy setup, review_guard/ledger initialization and protected/nested decorate construction. 5h setup pins and thirteen reached controls are mechanism references only, not ninth-profile proof.
- disk_tmp may probe mounts/create cache paths/update environment. Executable/runtime/storage/mount effects remain outside repository-file claims. Uncalled wrapped producer bodies may be conservatively pinned, not claimed reached.
- For each newly claimed reachable addition, confirm mutation bytes; absent excluded data must break actual selected execution before data is supplied, exactly one passing test proved, then intended boundary rejection required. Insert AST body changes after docstrings and BEFORE first statement's earliest decorator.
- Exact-one proof must independently inspect actual unittest output before exit interpretation. Actual-zero control ignores selector in a disposable empty suite, confirms Ran 0 tests, then rejects count before Python-dependent exit. Missing exact method may instead yield one loader _FailedTest.
- 5h changed an obsolete audit sibling-refusal assertion because its candidate became registered. Search compatibility expectations for THIS candidate before specifying; do not presume the same adjustment exists or copy its prior authorization. Preserve all eight entries and other refusals.

No next-slice product test, runtime STAGES check, extracted command or native/model/session qualification ran during handoff selection.

## Decisions for the fresh analyst chat

Apply spec skill, bounded analyst/Python persona reads and required analyst delegation. Draft ignored specification-5i.md or named equivalent. Present consequential decisions HERE IN THE NEW CHAT before planning/coding:

1. D1: Approve exact candidate and python-stage-doc-contract, select another candidate or stop expansion? Recommend exact method/ID only.
2. D2: Approve five ordered patterns with conservative extra production invalidation, or require a smaller independently justified closure? Recommend five, with per-pattern rationales, runtime/read-completeness limits and independent literal-document/heading/runtime-attribute oracle.
3. D3: Approve independent actual one-test proof, public export/framework run/reuse and ordinary-adopter freshness/identity; unrelated-test/non-input-document reuse; separate invalidation for direct doc, target/helper, representative production import and new supported script; exact argv/ordered declaration identity, receipts and source-derived boundary controls? Recommend yes. Candidate static failures: remove each of five exact required heading substrings from direct document (all occurrences), plus disposable lifecycle.STAGES set-member drift: SIX proposed cases. Candidate omission/matching/count controls: omit sole direct document, loose matching, actual zero: THREE proposed controls. Counts/breadth require human approval and final derivation from source. Prove runtime drift produces the intended set assertion, not import/CLI errors. Freshness edits preserve all assertions and restore bytes; static failures are distinct.
4. D4: Preserve all EIGHT complete profiles, inference/full suites/schemas/matching/freshness/gates/manual advisory adoption, and claim only heading-substring presence plus the observed runtime STAGES set? Recommend yes. Exclude actual gate behavior, ordering/duplicates/tuple-type checks, documentation semantics, native/model/session/governance qualification.

No next spec or plan approved. Obtain explicit human spec approval, then separately approved plan before coding. Nonexecuting analyze/trace may run during drafting. Historical results do not verify a ninth profile; no old suite rerun merely for fresh context.

## Restrictions and first action

Fresh chat starts with read-only context/spec drafting. No source edits, product tests, implementation plan before spec approval, native/model evaluations, session registration/allocation, fixture trust grants, historical rescoring/evidence modification, new worktree, invoking-framework knowledge bundle, commit/push/PR/merge or base refresh during initial drafting. All native allocations remain consumed. 5h delivery authorization is fulfilled and does not carry forward. Do not launch autonomy_driver.

Suggested fresh-chat prompt:

> Start from docs/assurance/handoff-5i.md. Run every repository command with explicit cwd /home/enramosjr/Projects/agentic-assurance-7. Read leading authoritative delivery update in implementation-5h.md. Inspect exact candidate, including literal document read, five heading substrings and runtime lifecycle.STAGES set comparison, then draft its specification. Present consequential decisions in this new chat before planning/coding. Keep docs/assurance ignored/local/uncommitted; preserve delivered branch/HEAD. No product tests/source edits/native/model/session/trust actions, knowledge bundle, base refresh or delivery during drafting.
