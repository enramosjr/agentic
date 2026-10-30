# Next slice candidate: assurance documentation section and recording-row input profile

Prepared 2026-10-29 America/Chicago at the user's explicit request: “Commit and push verified 5j, then prepare the handoff for the next slice. No PR or merge.” This is a selection recommendation and handoff, NOT an approved specification or implementation plan. Continue substantive next-slice work in a FRESH chat under AGENTS.md §9.

## Critical checkout and delivered state

Run EVERY repository command with explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Saved-project default `/home/enramosjr/Projects/agentic` is a DIFFERENT checkout. Do not work there, create another worktree, switch/reset branches or refresh the base.

Existing branch: `claude/assurance-increment-7`. Delivered HEAD: **22c65521b281fce485ec5d10e45359cded53ec3f** (Add tier documentation and runtime key-set input profile), pushed to matching origin branch. Delivery `git ls-remote --exit-code origin refs/heads/claude/assurance-increment-7` confirmed local/remote identity. Subsequent local context is local refs only; do not infer another remote check. Tracked state clean after delivery.

Read leading **Delivery complete — authoritative** in implementation-5j.md first. It supersedes historical verified/uncommitted/pending sections. Exactly three tracked files delivered; no PR or merge. 5j Intent/Plan/Review/Verify/Ship closed. A separate docs-only L0 serves ONLY this handoff; never reopen 5j or treat L0 as source approval.

TEN delivered profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract, python-installer-doc-contract, python-validation-policy-contract, python-audit-doc-contract, python-analysis-convergence-doc-contract, python-stage-doc-contract and python-tier-doc-contract. Preserve all ten COMPLETE entries, rationales, exports, tests and positive sibling registrations. Export remains literal/advisory/manual; inference, full suites, matching, freshness, schemas, gates and producer receipt exclusions unchanged.

5j evidence: converge-5j.log **6 PASS / 0 FAIL / 0 MANUAL**; separate four-tier runtime observation and actual one-test/count proof; framework/adopter identity/freshness; NINE intended failures (four bold removals, four regex-match removals, actual REQUIRED-key drift reaching final set assertion); FOUR controls (each direct-doc omission, loose matching, actual zero); thirteen freshly confirmed reachable additions. Each reached addition failed actual execution with excluded data absent, passed exactly one test after supplying data, then hit intended boundary rejection. Source values alone were not runtime proof. All those results verify the tenth profile only, NOT a next profile.

review-5j.md Approved/no findings, complete canonical report unchanged. ONE full framework PASS on frozen source tree **b19245a**, framework-5j.log. Retrospective closed BEFORE Verify with evidence-backed no-new-lessons; no binding promotion. Prior observations advisory. Registration RED: three tests/two absent-profile failures, then identical GREEN. Self-review fixed count-first ordering and added explicit restoration assertion before acceptance; no selected-test/prior-profile changes. No failed lifecycle run label required correction in 5j. One malformed tool-script string failed before any command executed. Preserve 5i/5h and earlier evidence unchanged.

Delivery reran no product suites. Sandbox and host reuse both reported execution-environment/runtime drift, NOT REUSE or a fresh PASS. Original evidence retains tested source/runtime scope; suppressed successful child output establishes no full-suite count. Commit author identity reused from preceding commit with per-command options, no Git config change.

Framework has NO knowledge bundle: use `python3 .ai/scripts/repo.py context --json`. NEVER initialize invoking-framework knowledge or invent baseline/log/records PASS. `okf.py handoff --prompt` is inapplicable. All docs/assurance remain ignored/local/UNCOMMITTED. Fresh chat loads context then declares NEW L2 with `--new` for any selected next profile.

## Recommended bounded candidate — NOT approved

Consider exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Assurance.test_assurance_documented
```

Suggested ID: `python-assurance-doc-contract`. Neither selector nor ID is approved. Fresh structured search found neither in assurance_inputs.py/test_assurance_inputs.py after 5j delivery; inspect refusals afresh, never assume an obsolete negative needs replacement. Broader Assurance class, module or sibling registration is unapproved.

Inspected selected source at test_lifecycle_conformance.py:255–267:

1. Calls `text(".ai/lifecycle.md")` inside `re.search(r"(?s)## Assurance status\n(.*?)(?=\n## )", ...)` and asserts the match is not None.
2. Assigns `body = section.group(1)`.
3. Iterates a literal 20-term tuple and requires each substring in captured body.
4. Iterates a separate literal seven-term tuple and requires each substring in captured body.
5. Separately calls `text(".ai/lifecycle.md")` for `assertRegex` with `r"(?m)^\| Assurance \| `assure"` and message Recording table row.

These are TWO literal reads of ONE document. Proposed source count: 27 substring checks plus match-not-None and final whole-document regex = 29 assertions within ONE test, NOT 29 tests. Re-derive tuple contents/counts from source before spec approval. Source inspection is not actual execution/count proof. The method copies nothing, executes no extracted/lifecycle command, and directly accesses no lifecycle runtime attribute; lifecycle imports still cause shared setup effects.

CRITICAL limits: extraction regex is unanchored and DOTALL, requiring literal heading text and a subsequent newline/level-two-heading prefix for its lookahead. It captures only the first matching section, not a Markdown parser or assurance semantics. Substrings are case-sensitive presence checks, not normative behavior or correct examples. The final MULTILINE regex anchors only a row prefix and has no end anchor; it does not validate a complete table/command. No actual statuses, assure behavior, freshness/enforcement, authentication, model/session behavior or runtime/extracted-command validity is established. Do not strengthen selected assertions as part of catalog expansion.

Proposed ordered scope for investigation, NOT approved:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.ai/lifecycle.md
```

Conservative production scope includes eager imports/lazy/decorator construction, unused non-test descendants and future supported scripts; extra invalidation needs approval. Exclude tests then restore selected module/helper. Final literal is the SOLE direct document, explicit despite Markdown exemptions. Root AGENTS is NOT this method's direct read (unlike 5j); .ai/docs/lifecycle.md and validation-policy are also not direct reads. Predecessor compatibility fixtures retain their own required documents, including AGENTS for earlier profiles.

## Investigation and evidence cautions

- Independent source oracle must resolve section regex/flags, sole document path at BOTH call sites, assigned match/body and group(1), BOTH distinct literal term tuples and loop bindings, substring assertions into captured body, and separate whole-document row regex. Retain reviewed method/setup pins. Do NOT copy 5j runtime-TIERS/set oracle or 5i heading/STAGES oracle unchanged.
- Reinspect root/import/text at test_lifecycle_conformance.py:15–27; disk_tmp/scratch.require_disk; lifecycle eager imports/lazy setup; review_guard/ledger initialization and protected/nested decorate construction. Prior pins/thirteen reached variants are references, NOT next-profile proof. No lifecycle attribute/value observation is needed for this selected method's own assertions.
- Every newly claimed reachable addition needs confirmed mutation bytes, actual selected failure with excluded data absent, supplied-data exactly-one-test PASS, then intended boundary rejection. Insert AST body mutations after docstrings and BEFORE earliest decorator of first statement. Uncalled producer bodies can be conservatively pinned, never described as reached.
- Keep actual selected execution/count proof separate from source extraction. Actual-zero control must ignore selector in an actual empty disposable suite, independently confirm Ran 0 tests, then reject count BEFORE Python-dependent exit. Missing method can yield one loader _FailedTest and is insufficient.
- Assertion-preserving freshness edits restore bytes and remain separate from static failures. Scope of document failures must follow actual capture boundaries: removing every occurrence of a term in the captured body must not accidentally fall through to a second section or an earlier unrelated failure. Require intended assertion, not AttributeError/group failure, import/CLI failure or incidental missing token.
- Proposed failure matrix, subject to analyst derivation/approval: one missing-section match failure, 27 separate body-term removals, one row-prefix regex failure = 29 cases. Proposed controls: sole-doc omission, loose matching, actual zero = three controls. Remove EVERY matching occurrence for each target; confirm bytes, preserve unrelated assertions where needed and prove actual one-test intended failure. Reconcile overlap/regex boundaries before approval; counts are recommendations, not inherited acceptance.

No next-profile product test, selected execution, native/model/session qualification or new runtime observation ran during handoff preparation.

## Decisions for the fresh analyst chat

Use spec skill with required read-only analyst delegation and bounded analyst/Python persona reads. Draft ignored specification-5k.md or named equivalent. Present consequential decisions IN THAT CHAT before planning/coding:

- D1: exact method and python-assurance-doc-contract, another candidate or stop? Recommend exact method/ID only.
- D2: five ordered conservative patterns/extra invalidation plus independent section/two-call/two-tuple/body/row oracle, or smaller independently justified closure? Recommend five with accurate limits.
- D3: independent actual one-test proof; framework/adopter identities/freshness; unrelated-test/non-input-doc reuse; sole-doc/target/helper/production/new-supported-script invalidation; exact argv/ordered identity and receipts; source-derived boundary mutations; proposed 29 intended failures and three controls? Recommend yes, with final counts/overlap/boundary derivation before approval.
- D4: preserve all TEN complete profiles and existing mechanisms/manual adoption, limit claims to selected regex extraction/body substrings/row-prefix presence? Recommend yes; no semantics/status/enforcement/native/model/session qualification.

Obtain explicit HUMAN SPEC approval, then SEPARATE plan approval before implementation. Nonexecuting analyze/trace allowed during drafting. Never rerun old suites just for fresh context.

## Restrictions and first action

Fresh chat starts read-only context/spec drafting. No source edits/product tests/implementation plan before spec approval, native/model evaluation, session registration/allocation, fixture trust grants, historical rescoring/evidence modification, new worktree, knowledge bundle, commit/push/PR/merge or base refresh. All native allocations remain consumed. 5j delivery authorization is fulfilled and does NOT carry forward. Do not launch autonomy_driver.

Suggested fresh-chat prompt:

> Start from docs/assurance/handoff-5k.md FIRST. Run every repository command with explicit cwd /home/enramosjr/Projects/agentic-assurance-7. Read leading authoritative delivery update in implementation-5j.md. Investigate exact Assurance.test_assurance_documented selection, section regex/capture/body, both term tuples and separate row regex; draft its specification and present D1–D4 here before planning/coding. Keep docs ignored/local/uncommitted, preserve delivered branch/HEAD, and await explicit spec then separate plan approval. No source/product/native/model/session/trust work, knowledge initialization, delivery or base refresh during drafting.

## Handoff checks

`git check-ignore docs/assurance/handoff-5k.md docs/assurance/implementation-5j.md` -> exit 0/both ignored. `git diff --check` -> exit 0; `git status --short --untracked-files=no` -> exit 0/empty. Final local context confirms expected delivered HEAD/branch, equal local upstream refs and clean tracked state; remote_verified false for that local-only query. The earlier delivery ls-remote supplied actual remote confirmation. `okf.py affected` on both ignored docs -> exit 1/no framework bundle; synchronization INAPPLICABLE, not records PASS. No next-profile product check ran.
