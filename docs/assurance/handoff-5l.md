# Next slice candidate: AGENTS cold-start encoded-text budget input profile

Prepared 2026-10-29 America/Chicago at the user's request: “Commit and push verified 5k, then prepare the handoff for the next slice. No PR, merge, or base refresh.” This is a selection recommendation and handoff, NOT an approved specification or implementation plan. Continue substantive next-slice work in a FRESH chat under AGENTS.md §9.

## Critical checkout and delivered state

Run EVERY repository command with explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Saved-project default `/home/enramosjr/Projects/agentic` is a DIFFERENT checkout. Do not work there, create another worktree, switch/reset or refresh the base.

Existing branch: `claude/assurance-increment-7`. Delivered HEAD: **cf158b53b9c164b22a3172792ab3c86980106e0e** (Add assurance documentation input profile), pushed to matching origin branch. Delivery `git ls-remote --exit-code origin refs/heads/claude/assurance-increment-7` confirmed remote/local identity. Subsequent local context uses local refs only; infer no new remote check. Tracked state clean after delivery.

Read leading **Delivery complete — authoritative** in implementation-5k.md first. It supersedes older verified/uncommitted/pending sections. Exactly three tracked files delivered; no PR, merge or base refresh. 5k Intent/Plan/Review/Verify/Ship closed. A separate docs-only L0 serves ONLY this handoff; never reopen 5k or treat L0 as source approval.

ELEVEN delivered profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract, python-installer-doc-contract, python-validation-policy-contract, python-audit-doc-contract, python-analysis-convergence-doc-contract, python-stage-doc-contract, python-tier-doc-contract and python-assurance-doc-contract. Preserve all eleven COMPLETE entries, rationales, exports, tests and positive sibling registrations. Export stays literal/advisory/manual; inference, full suites, matching, freshness, schemas, gates and producer receipt exclusions unchanged.

5k evidence: converge-5k.log **6 PASS / 0 FAIL / 0 MANUAL**; independent actual one-test/count proof; stable bytes; framework/adopter identity/freshness; TWENTY-NINE intended assertion failures (section match,27 body tokens, row prefix); THREE confirmed controls (sole-doc omission, loose matching, actual zero); THIRTEEN freshly demonstrated reachable additions. Each addition failed actual selected execution absent excluded data, passed exactly one test after supplying data, then hit intended boundary rejection. Capture-aware all-occurrence removals preserved earlier assertions, with explicit later UNVERIFIED collateral for VERIFIED. All those results verify the eleventh profile only, NOT the next profile.

review-5k.md Approved/no findings, both passes clean; complete canonical report preserved unchanged. ONE full framework PASS on frozen source tree **ccd2f31**, framework-5k.log. Retrospective closed BEFORE Verify with evidence-backed no-new-lessons; no binding promotion. Prior observations advisory. Registration RED: three tests/three absent-profile failures, then identical GREEN. No failed lifecycle run label required correction. Initial sandbox wait lacked host PID visibility; same-host wait confirmed actual completion without rerun. Preserve 5j/5i/5h and earlier evidence unchanged.

Delivery reran no product suite. Same-host reuse reported execution-environment/runtime drift, NOT REUSE or a fresh PASS. Original evidence retains tested source/runtime scope; successful child output is suppressed and establishes no full-suite count. Commit author identity reused from preceding commit through per-command Git options; no Git config change.

Framework has NO knowledge bundle: use `python3 .ai/scripts/repo.py context --json`. NEVER initialize invoking-framework knowledge or invent baseline/log/records PASS. `okf.py handoff --prompt` is inapplicable. ALL docs/assurance remain ignored/local/UNCOMMITTED. Fresh chat loads context then declares NEW L2 with `--new` for any selected next profile.

## Recommended bounded candidate — NOT approved

Consider exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py AgentsBudget.test_agents_md_stays_below_its_cold_start_budget
```

Suggested ID: `python-agents-budget-contract`. Neither selector nor ID is approved. Fresh structured regex search found neither in assurance_inputs.py/test_assurance_inputs.py after delivery. Reinspect actual refusals afresh; never assume an obsolete negative needs replacement. Broader AgentsBudget class/module and sibling registration is unapproved.

Selected source at test_lifecycle_conformance.py:167–168:

```python
def test_agents_md_stays_below_its_cold_start_budget(self) -> None:
    self.assertLess(len(text("AGENTS.md").encode()), 30_000)
```

This is ONE literal read of ONE document and ONE strict less-than assertion within ONE test. Re-derive the actual call chain and numeric bound before spec approval. Source inspection is not actual execution/count proof. It does not directly read lifecycle attributes, call baseline/flat, run Git or extracted/lifecycle commands, or copy files. Shared imports/setup/class-body construction still matter.

Exact length claim: `text` at lines26–27 returns `(ROOT / path).read_text()` with no encoding/newline arguments, then no-argument str.encode() returns UTF-8 bytes. The assertion counts the re-encoded returned string, NOT necessarily raw on-disk size: default text decoding and universal-newline translation precede encoding. CRLF and other decoded-newline forms can differ from raw bytes. Do not silently claim raw-file-byte, character, token, performance, cold-start latency, Markdown semantics, normative preservation, governance/enforcement or native/model/session qualification. Encoding/locale/runtime are external environment assumptions, not repository-file completeness proof. Invalid decoding is not the intended threshold assertion failure.

AgentsBudget source at lines150–165 also defines BASELINES, a compiled NORMATIVE regex and baseline/flat helpers. The selected method does NOT call these helpers: its siblings do, including historical `git show` and possible skipTest. Pin conservative setup where warranted; never claim those uncalled helpers reached or copy their subprocess/history requirements into this method's selected read oracle. No canonical historical commit is required by the selected method's own assertion.

Proposed ordered scope for investigation, NOT approved:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
AGENTS.md
```

Conservative production scope covers eager imports, lazy/decorator construction, unused non-test descendants and future supported scripts; extra invalidation needs approval. Exclude tests then restore selected module/helper. AGENTS is the SOLE direct document, explicit despite Markdown exemptions. `.ai/lifecycle.md`, `.ai/docs/lifecycle.md` and validation-policy are NOT selected direct reads. Compatibility fixtures retain their own required inputs, including lifecycle documents for prior profiles.

## Investigation and evidence cautions

- Independent source oracle must resolve exact method/class, one literal text call/path, nested no-argument encode(), len() and assertLess(...,30000), including strict comparison semantics. Retain reviewed method/setup pins. Do NOT copy 5k section/two-call/two-tuple/row oracle or 5j TIERS/REQUIRED or 5i STAGES oracle.
- Reinspect root/import/text, disk_tmp/called scratch.require_disk, lifecycle eager imports/lazy setup, review_guard/ledger initialization and protected/nested decorate construction. Prior setup pins/13 reached variants are references, NOT next-profile proof. No lifecycle runtime attribute observation is needed for the selected assertion.
- Every newly claimed reachable addition needs confirmed mutation bytes, actual selected failure with excluded data absent, supplied-data exactly-one-test PASS, then intended boundary rejection. Insert AST body additions after docstrings and BEFORE earliest decorator of first statement. Uncalled producer/baseline helpers may be conservatively pinned, never called reached without proof.
- Keep actual selected execution/count proof separate from source extraction and any independently constructed length fixture. Prove the original selected command executes exactly one passing test. Actual-zero control must ignore selector in an actual empty suite, independently confirm Ran0tests, then reject count BEFORE version-dependent exit. Missing-method loader _FailedTest is insufficient.
- Freshness edits must preserve the threshold assertion, restore exact bytes and remain separate from threshold-failure fixtures. Choose a short preserving document edit with enough observed margin, or otherwise explicitly construct a passing preserving variant; do not assume arbitrary growth always passes near the limit.
- Proposed boundary matrix, subject to analyst derivation and approval: a passing re-encoded length29999, TWO intended failures at exactly30000 and30001, and a valid multibyte fixture distinguishing encoded length from character count. Construct independent deterministic valid text with LF and a declared/confirmed decoding assumption; count its expected UTF-8 encoding independently and confirm bytes. Each failure must execute exactly one selected test and reach assertLess, not decoding/import/CLI failure. Reconcile fixture encoding/newline treatment and final counts before approval; do not inherit29failures.
- Proposed THREE broken controls: sole-doc omission, loose matching, actual zero. Threshold boundary and encoding sensitivity may need additional guard checks, but breadth/count must be specified and approved in the fresh chat rather than invented during implementation.
- Full class/module registration would invoke additional history/linked-document behavior. Keep it unapproved. Preserve existing positive sibling registrations, not broadening them.

No next-profile product test, runtime candidate import/observation, native/model/session qualification or session allocation ran during handoff preparation.

## Decisions for fresh analyst chat

Use spec skill with required read-only analyst delegation and bounded analyst/Python persona reads. Draft ignored specification-5l.md or named equivalent. Present consequential D1–D4 IN THAT CHAT before planning/coding:

- D1: exact AgentsBudget method and python-agents-budget-contract, another candidate or stop? Recommend exact method/ID only.
- D2: five ordered conservative patterns/extra invalidation plus independent one-read/encode/len/strict-bound oracle, or smaller independently justified closure? Recommend five, with accurate limits.
- D3: independent actual-one-test proof; framework/adopter identities/freshness; unrelated-test/non-input-doc reuse; sole-doc/target/helper/production/new-supported-script invalidation; exact argv/ordered declaration identity/receipt exclusion; freshly reached boundary challenges; proposed29999positive,30000/30001 intended failures, multibyte distinction and3controls? Recommend yes with final source/encoding/newline/count derivation before approval.
- D4: preserve all ELEVEN complete profiles and existing mechanisms/manual adoption; claims limited to strict re-encoded-text budget and declared-file freshness? Recommend yes; explicitly exclude raw-file-size/character/token/latency/semantics/history-preservation/enforcement/native/model/session claims.

Obtain explicit HUMAN SPEC approval, then SEPARATE plan approval before implementation. Nonexecuting analyze/trace allowed while drafting. Never rerun old suites just for fresh context.

## Restrictions and first action

Fresh chat starts read-only context/spec drafting. No source edits/product tests/runtime candidate import/implementation plan before spec approval, native/model evaluation, session registration/allocation, fixture trust grants, historical rescoring/evidence modification, new worktree, knowledge bundle, commit/push/PR/merge or base refresh. All native allocations remain consumed. 5k delivery authorization is fulfilled and does NOT carry forward. Do not launch autonomy_driver.

Suggested fresh-chat prompt:

> Start from docs/assurance/handoff-5l.md FIRST. Run every repository command with explicit cwd /home/enramosjr/Projects/agentic-assurance-7. Read leading authoritative delivery update in implementation-5k.md. Investigate exact AgentsBudget.test_agents_md_stays_below_its_cold_start_budget selection, text/read_text/encode/len/strict30000 chain and external decoding/newline limits; draft its specification and present D1–D4 here before planning/coding. Keep docs ignored/local/uncommitted, preserve delivered branch/HEAD, and await explicit spec then separate plan approval. No source/product/native/model/session/trust work, knowledge initialization, delivery or base refresh while drafting.

## Handoff checks

`git check-ignore docs/assurance/handoff-5l.md docs/assurance/implementation-5k.md` -> exit0/both ignored. `git diff --check` -> exit0; `git status --short --untracked-files=no` -> exit0/empty. Local context confirms delivered HEAD/branch, equal local upstream refs and clean tracked state; remote_verified false for that local-only query. Delivery's earlier ls-remote supplied actual remote identity confirmation. `okf.py affected` on both ignored docs -> exit1/no invoking-framework bundle; synchronization INAPPLICABLE, not records PASS. No next-profile product check ran. Handoff changes remain ignored/local/uncommitted.
