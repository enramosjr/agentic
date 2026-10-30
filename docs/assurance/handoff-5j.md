# Next slice candidate: tier documentation and runtime tier/key-set input profile

Prepared 2026-10-29 America/Chicago at the user's explicit request: “Commit and push verified 5i, then prepare the handoff for the next slice. No PR or merge.” This is a selection/handoff recommendation, not an approved specification, plan or implementation. Continue substantive next-slice work in a fresh chat under AGENTS.md §9.

## Critical checkout and delivered state

Run EVERY repository command with explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Saved-project default `/home/enramosjr/Projects/agentic` is a DIFFERENT checkout. Do not work there, create another worktree, switch/reset or refresh the base.

Existing branch: `claude/assurance-increment-7`. Delivered HEAD: **f2c0b6db99e797b99781034a7f8b4b44b17f5f00** (Add stage documentation and runtime names input profile), pushed to matching origin branch. Delivery `git ls-remote --exit-code origin refs/heads/claude/assurance-increment-7` confirmed remote/local identity. Subsequent context uses local refs only; do not infer another remote check. Tracked state clean after delivery.

Read leading **Delivery complete — authoritative** in implementation-5i.md first. It supersedes historical verified/uncommitted/pending sections. Exactly three tracked files delivered; no PR or merge.

NINE delivered profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract, python-installer-doc-contract, python-validation-policy-contract, python-audit-doc-contract, python-analysis-convergence-doc-contract and python-stage-doc-contract. Preserve all nine complete entries/rationales/behavior and historical evidence. Export remains literal/advisory/manual; inference, full suites, matching, freshness, schemas, gates and receipt exclusions unchanged.

5i evidence: converge-5i.log **6 PASS / 0 FAIL / 0 MANUAL**; independent actual one-test proof, framework/adopter identities/freshness, six intended selected-assertion failures (five exact heading removals plus actual runtime STAGES drift), three confirmed omission/matching/actual-zero controls and thirteen individually confirmed reachable dependency additions. review-5i.md Approved/no findings; complete canonical report preserved. One full framework PASS on frozen source tree **025ea73**, framework-5i.log. Intent/Plan/Review/Verify/Ship closed. No source changed after acceptance/review/full gate.

5i test-first registration RED: three tests, two absent-profile failures; identical GREEN after catalog addition. Later-written guards challenged by disposable broken variants. Self-review corrected new fixture escaping before execution; no selected-test or prior-profile changes. No failed lifecycle run label required correction in 5i. Preserve 5h's earlier same-label diagnostic history as historical evidence, not a 5i event.

Retrospective closed before Verify with evidence-backed no-new-lessons reason; no selected new lesson or binding promotion. Prior observations remain advisory. Delivery reran no product suites. Sandbox and host reuse both reported execution-environment/runtime drift, not REUSE or a fresh PASS. Keep historical source/runtime scopes. Suppressed successful child output establishes no full-suite count. Earlier results verify no tenth profile. Preserve 5h and earlier evidence unchanged.

Framework has no knowledge bundle: use `python3 .ai/scripts/repo.py context --json`. NEVER initialize invoking-framework knowledge or invent capability baseline/log/records PASS. `okf.py handoff --prompt` is inapplicable. All docs/assurance stay ignored/local/UNCOMMITTED. Separate docs-only L0 after Ship is solely this handoff. Fresh chat loads context then declares NEW L2 with --new; never reopen 5i or treat L0 as source approval.

## Recommended bounded candidate — NOT approved

Consider one exact-method profile for the existing command:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Tiers.test_tier_definitions_agree_across_agents_lifecycle_and_script
```

Suggested ID: `python-tier-doc-contract`. Neither ID nor candidate is approved. Structured search found no exact candidate/ID occurrence in assurance_inputs.py or test_assurance_inputs.py at delivery; reinspect actual refusal expectations rather than assuming any obsolete negative needs replacing.

The selected method at `test_lifecycle_conformance.py:191-195` iterates **runtime `lifecycle.TIERS` values**, not literal paths or heading labels. For each observed `tier`, it calls `text("AGENTS.md")` and requires `f"**{tier}**"`; it separately calls `text(".ai/lifecycle.md")` and requires regex `rf"\| {tier} "`. Finally it compares `set(lifecycle.REQUIRED)` with `set(lifecycle.TIERS)`. Both text-call paths are literal, but execution frequency and interpolated assertions depend on runtime TIERS. No lifecycle or extracted command executes; the selected method copies nothing.

`lifecycle.py:70-77` currently defines source TIERS as `(L0, L1, L2, L3)` string values and REQUIRED with the same four keys. Source inspection is not observed runtime proof. With those four values, the source describes eight document assertions plus one set assertion within **ONE test**, not nine tests. A later actual one-test execution/count proof and intended assertion failures are separate requirements to propose.

CRITICAL limits: this method has NO independent fixed expected taxonomy. If runtime TIERS and REQUIRED keys changed together, the final equality could still pass; an empty TIERS plus empty REQUIRED could make document checks vacuous. Set conversion itself establishes no REQUIRED mapping type; “keys” describes iteration of the currently defined mapping, not a type assertion. Do not claim nonempty/canonical four-tier coverage, exact tuple type/order/uniqueness, REQUIRED values or stage requirements, correct table/section semantics, or actual gating/enforcement. The regex is interpolated directly, without escaping the observed tier value; do not broaden that into a claim of arbitrary-tier validation. Registration should describe exactly this bounded observed-runtime behavior.

Proposed ordered scope for analyst investigation, NOT approved:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
AGENTS.md
.ai/lifecycle.md
```

The first pattern conservatively covers production eager imports, runtime TIERS/REQUIRED definition/access and lazy-loader/decorator construction, including unused non-test descendants and future supported scripts. Extra invalidation requires approval. Tests are excluded before restoring selected module/helper. The final two documents are direct reads, explicit despite Markdown exemptions. Root AGENTS is now a direct read, unlike 5i. `.ai/docs/lifecycle.md` and validation-policy are not direct reads; predecessor compatibility fixtures retain their own required inputs. Broader Tiers class/module/sibling registration is unapproved.

## Nonexecuting selection evidence and investigation cautions

- `test_lifecycle_conformance.py:191-195` and `lifecycle.py:70-77` were reinspected after delivery without candidate execution. Independent source oracle must resolve runtime TIERS loop binding, BOTH literal text calls, interpolated bold substring versus interpolated regex, and final REQUIRED-key/TIERS set comparison. Pin reviewed method and relevant setup. Do not copy 5g's path-loop, 5h's mixed-read or 5i's literal-doc/heading-tuple/STAGES oracle unchanged.
- Reinspect shared root/import setup and text at `test_lifecycle_conformance.py:15-27`, disk_tmp/scratch.require_disk, lifecycle eager imports/lazy setup, review_guard/ledger initialization and protected/nested decorate construction. Prior setup pins and thirteen reached variants are references only, not tenth-profile proof.
- Runtime executable/environment, temporary storage/mount state, ignored files and external mutable data remain outside repository-file claims. disk_tmp may probe mounts/create cache paths/update environment. Uncalled wrapped producer bodies may be conservatively pinned, not described as reached.
- Each newly claimed reachable addition needs confirmed mutation bytes, actual selected failure with excluded data absent, exactly one passing selected test after data is supplied, then intended boundary rejection. Insert AST body changes after docstrings and BEFORE the earliest decorator of the first statement.
- Actual-zero control ignores selector in a disposable empty suite, independently confirms Ran 0 tests, then rejects count before Python-dependent exit. A missing exact method may yield one loader _FailedTest and is insufficient.
- Do not alter selected assertions or strengthen the selected method into a fixed-taxonomy/enforcement test as part of literal profile expansion. Extra invariant requirements would be a new scope decision requiring human approval.

No tenth-profile product test, runtime TIERS/REQUIRED observation, extracted command or native/model/session qualification ran during handoff selection.

## Decisions for the fresh analyst chat

Apply spec skill, bounded analyst/Python persona reads and required analyst delegation. Draft ignored specification-5j.md or named equivalent. Present consequential decisions IN THE NEW CHAT before planning/coding:

1. D1: Approve exact candidate and python-tier-doc-contract, select another candidate or stop expansion? Recommend exact method/ID only.
2. D2: Approve six ordered patterns with conservative extra production invalidation, or require a smaller independently justified closure? Recommend six with per-pattern rationales and independent runtime-loop/literal-read/interpolation/key-set oracle; source extraction is not runtime-value proof.
3. D3: Approve independent actual one-test proof, public export/framework run/reuse, ordinary-adopter freshness/identity, unrelated-test/non-input-document reuse, separate invalidation for BOTH direct docs/target/helper/representative production import/new supported script, exact argv/ordered declaration identity, receipts and source-derived boundary controls? Recommend yes. If the separately inspected/observed baseline confirms four TIERS, suggested failure matrix is four AGENTS bold-token removals, four lifecycle-regex-match removals and one REQUIRED-key drift: **NINE proposed cases**. Remove every occurrence/match in each disposable direct document and require the intended assertion failure. REQUIRED-key drift must reach final set assertion, not import/CLI failure. Suggested controls: omit each of two direct docs, loose matching and actual zero: **FOUR proposed controls**. Counts/breadth require human approval and final source/runtime derivation; historical counts are not proof. Assertion-preserving freshness edits restore bytes and remain separate from failures.
4. D4: Preserve all NINE complete profiles, inference/full suites/schemas/matching/freshness/gates/receipt exclusions/manual adoption, and claim only per-observed-tier bold-substring/regex-match presence plus observed REQUIRED-key/TIERS set equality? Recommend yes. Explicitly exclude canonical/nonempty taxonomy, tuple/order/duplicate guarantees, REQUIRED values, documentation semantics, actual tier/stage gating and native/model/session/governance qualification.

No next specification or plan approved. Obtain explicit human spec approval, then separately approved plan before coding. Nonexecuting analyze/trace may run during drafting. Historical results do not verify a tenth profile; do not rerun old suites merely for fresh context.

## Restrictions and first action

Fresh chat starts with read-only context/spec drafting. No source edits, product tests, implementation plan before spec approval, native/model evaluations, session registration/allocation, fixture trust grants, historical rescoring/evidence modification, new worktree, invoking-framework knowledge bundle, commit/push/PR/merge or base refresh during initial drafting. All native allocations remain consumed. 5i delivery authorization is fulfilled and does not carry forward. Do not launch autonomy_driver.

Suggested fresh-chat prompt:

> Start from docs/assurance/handoff-5j.md. Run every repository command with explicit cwd /home/enramosjr/Projects/agentic-assurance-7. Read leading authoritative delivery update in implementation-5i.md. Inspect exact candidate's runtime TIERS loop, both literal document reads with distinct substring/regex interpolation and REQUIRED-key/TIERS set comparison, then draft its specification. Present consequential decisions in this new chat before planning/coding. Keep docs/assurance ignored/local/uncommitted; preserve delivered branch/HEAD. No product tests/source edits/native/model/session/trust actions, knowledge bundle, base refresh or delivery during drafting.

## Handoff checks

`git check-ignore docs/assurance/handoff-5j.md docs/assurance/implementation-5i.md` -> exit 0, both ignored. `git diff --check` -> exit 0; `git status --short --untracked-files=no` -> exit 0, empty output. Final local context confirms delivered branch/HEAD, clean tracked state and equal local upstream refs, with remote_verified false for that local-only query. `okf.py affected` on both ignored docs -> exit 1/no framework bundle; synchronization INAPPLICABLE, not records PASS. No next-slice product check ran.
