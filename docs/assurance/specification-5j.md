# Spec: tier documentation and runtime tier/key-set input profile

Approved by human:enramosjr in this chat on 2026-10-29 America/Chicago: “Approved. Proceed with the implementation plan for 5j using the recommended D1–D4 decisions. Keep implementation pending separate plan approval.” L2; analyst role; Python principal engineer. Approval authorizes planning only; implementation requires separate plan approval. Acceptance commands below are proposed future checks, not execution evidence.

## Problem and outcome

Maintainers have nine delivered literal Python input profiles but no exact-method profile for the existing runtime-tier documentation and set-consistency check. Add one explicitly adopted profile through the existing exporter, with reviewed repository inputs and controlled freshness evidence. Framework mode has no knowledge bundle or structured capability baseline; this standalone specification creates neither and revises no historical evidence.

## Users and scenarios

A maintainer invokes the exporter from the repository root for exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Tiers.test_tier_definitions_agree_across_agents_lifecycle_and_script
```

Proposed ID: `python-tier-doc-contract`.

The selected method iterates runtime `lifecycle.TIERS`. For each observed `tier`, it calls `text("AGENTS.md")` and requires the bold substring `f"**{tier}**"`; it separately calls `text(".ai/lifecycle.md")` and requires regex `rf"\| {tier} "`. Both literal document reads repeat per observed tier. Finally it compares `set(lifecycle.REQUIRED)` with `set(lifecycle.TIERS)`. It executes no lifecycle or extracted command and copies nothing.

Inspected source currently defines TIERS with L0, L1, L2 and L3 and REQUIRED as a mapping with those keys. This is source evidence, not observed runtime proof. With those four runtime values, eight document assertions plus one set assertion occur within ONE test. Exactly one passing test and the runtime baseline require separate future evidence.

There is no independent fixed expected taxonomy. Simultaneous TIERS/REQUIRED-iteration drift can pass; empty TIERS and empty REQUIRED can make document assertions vacuous. Set conversion proves neither mapping/tuple type nor order/uniqueness. “Keys” describes iteration of the currently defined REQUIRED mapping, not a mapping-type assertion. REQUIRED values and stage requirements are unchecked. Regex interpolation does not escape tier values; no arbitrary-tier safety is claimed. Presence checks establish no documentation table, section or body semantics, nor actual tier/stage enforcement.

Proposed ordered scope:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
AGENTS.md
.ai/lifecycle.md
```

The first pattern conservatively includes production eager imports, runtime TIERS/REQUIRED access and lazy-loader/decorator construction, including unused non-test descendants and future supported scripts. Extra invalidation is deliberate and requires D2 approval. Exclude unrelated tests before restoring the selected module and imported helper. The final two literals are direct document reads, explicit despite general Markdown freshness exemptions. `.ai/docs/lifecycle.md` and validation-policy are not direct reads of this method; predecessor compatibility fixtures retain their own required inputs. Broader Tiers class/module or sibling registration is unapproved.

## Requirements

- R1: The exporter MUST register only the exact repository-root argv above as `python-tier-doc-contract`. Class/module, sibling, discovery, option, alias and other-interpreter variants MUST remain unregistered unless already registered. All nine delivered profiles MUST retain complete IDs, argv, ordered inputs, rationales and behavior.
- R2: The profile MUST export exactly the six ordered patterns above before positive supplements, with per-pattern rationales. An independent source-derived oracle MUST resolve the runtime TIERS loop and its binding, BOTH literal text calls, distinct interpolated bold-substring and regex assertions, and the final runtime REQUIRED/TIERS set comparison. Reviewed method and relevant setup fingerprints MUST remain pinned. The boundary MUST cover the text helper, eager initialization, disk_tmp/called scratch.require_disk, lazy setup and protected/nested decorate construction. Guards MUST reject boundary drift and confirmed reachable excluded additions. Source extraction MUST NOT stand for runtime-value proof. Conservative pins MUST NOT imply universal dependency discovery or execution of uncalled wrapped producer bodies. Unrelated tests and non-input documents MUST remain excluded.
- R3: Public text/JSON export MUST preserve existing token/Inputs/rationale parity, supplement order, root/path/inventory validation, nonexecution and refusal behavior. Export MUST neither import/execute the selected test nor evaluate its document/runtime assertions, adopt Inputs or record evidence. Missing required literals and unsafe/unsupported paths or unknown commands MUST refuse nonzero with a reason and no usable candidate. Existing inputs with failing selected assertions MUST remain exportable through path-only validation.
- R4: Adoption MUST remain explicit, advisory and manual. Existing inference, full suites, matching, freshness, schemas, gates and producer receipt exclusions MUST remain unchanged. The guide MUST name the exact command/ID, per-observed-tier bold substring and regex matches, observed REQUIRED/TIERS set equality, conservative extra invalidation and runtime/read-completeness limits. It MUST state the taxonomy, vacuity, type/order/uniqueness, REQUIRED-value, unescaped-regex and semantics/enforcement limits above. Export MUST NOT imply VERIFIED evidence or native/model/session qualification.
- R5: An isolated framework fixture MUST drive public export and real lifecycle run/reuse. Independent captured unittest output MUST prove exactly one test executed and passed before exit interpretation; separately observed runtime values MUST confirm the baseline before deriving failure counts. Recorded argv, ordered inputs and exit MUST match export, with selected repository bytes unchanged during execution. Evidence MUST REUSE unchanged and after unrelated-test/non-input-document edits, and MUST RERUN after separate assertion-preserving edits to EACH direct document, target, disk helper, representative production import and new supported non-test script. Edits MUST restore original bytes. The invoking framework MUST acquire no knowledge bundle. On the separately confirmed four-tier baseline, NINE disposable static failures MUST fail actual selected execution while export succeeds: remove every occurrence of each of four bold tier tokens from AGENTS separately, remove every match of each of four tier regexes from the direct lifecycle document separately, and introduce REQUIRED-key drift. Each MUST confirm bytes and the intended assertion failure. REQUIRED drift MUST reach the final set assertion, rather than fail import or CLI setup. Freshness edits and failure fixtures MUST remain distinct. A different runtime baseline MUST stop for scope/count review, not silently change approved breadth.
- R6: A separate ordinary adopter fixture MUST explicitly adopt public export, become VERIFIED after independently proven actual one-test execution, remain VERIFIED after unrelated-test/non-input-document edits, and become STALE after EACH direct-document, target/helper, representative production import and new supported non-test script edit. Unmatched ordered declarations and argv identity MUST yield UNVERIFIED under existing rules; receipt exclusion MUST remain effective. FOUR confirmed disposable broken controls MUST be rejected: omission of AGENTS, omission of the direct lifecycle document, loose command matching and acceptance of actual zero-test execution. Each omission MUST fail the intended freshness assertion while assertion-preserving document edits leave the selected check passing. Actual-zero MUST ignore the selector in an actual disposable empty suite, independently confirm Ran 0 tests, then reject count before Python-dependent exit interpretation. A missing exact method yielding one loader failure is insufficient. Every control MUST confirm mutation bytes and its intended failure without altering historical evidence.

## Acceptance

Proposed TierDoc classes below belong in `.ai/scripts/tests/test_assurance_inputs.py`; they do not yet exist. Missing classes, counts or end states fail acceptance. These commands MUST NOT run during drafting. Guards are conservative review guards, not general dependency discovery. Each static-failure fixture must independently establish exactly one selected test and its intended failure. Independent two-pass review and the required full framework gate remain required after implementation; no prior result verifies this tenth profile.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py TierDocProfileTests` checks exact ID/argv/root matching, variant refusal and complete preservation of all nine prior entries/rationales/behavior. Existing registered sibling expectations remain preserved; inspected source justifies no obsolete negative replacement.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py TierDocDependencyTests` checks ordered scope/rationales, independent ledger selection, runtime loop binding, both literal reads/interpolations and final observed-set boundaries with reviewed method/setup pins. It checks unrelated exclusions and future supported non-test descendants. Each newly claimed reachable addition MUST first fail actual selected execution with excluded data absent, then pass exactly one test with supplied data, before intended boundary rejection. Derive variants from current source, not thirteen historical controls. Confirm bytes; insert AST changes after docstrings and BEFORE the earliest decorator of the first statement. Uncalled bodies may be conservatively pinned, never claimed reached.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py TierDocExportTests` checks public formats, supplements, immutability/nonexecution, every missing required literal and unsafe boundary, and path-only export when existing inputs fail selected assertions.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py TierDocCompatibilityTests` checks guide claims/limits and preservation of nine profiles, inference/full suites, matching, schemas, gates and receipts through existing mechanisms. Predecessor compatibility fixtures retain required inputs.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py TierDocFrameworkEndToEndTests TierDocFailureTests` checks independent one-test/count and runtime-baseline proof, byte stability, identities and all framework freshness outcomes, separately from nine confirmed intended assertion failures on the four-tier baseline.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py TierDocAdopterEndToEndTests TierDocControlTests` checks every adopter state/identity and receipt exclusion plus four confirmed broken controls, including EACH direct-document omission and independent actual-zero rejection.

## Constraints

Use the existing literal catalog/export mechanism, Python 3.9+, standard library and unittest conventions. No new options, schemas, normalization, loader, inference, adoption automation, gates or approval authority. Inventory follows existing tracked/supported nonignored-untracked ledger rules. Executable/runtime environment, temporary storage/mount state, ignored files and external mutable data remain outside repository-file claims. Unresolved additional reads require review and retention of current scope.

Preserve all nine complete profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract, python-installer-doc-contract, python-validation-policy-contract, python-audit-doc-contract, python-analysis-convergence-doc-contract and python-stage-doc-contract.

Use ONLY `/home/enramosjr/Projects/agentic-assurance-7`, existing branch `claude/assurance-increment-7`, delivered HEAD `f2c0b6db99e797b99781034a7f8b4b44b17f5f00`. Keep ALL docs/assurance ignored/local/UNCOMMITTED. Preserve 5i and earlier evidence and source/runtime scopes; those results verify no tenth profile. During drafting: no source edits, product tests, implementation plan, native/model evaluation, session registration/allocation, fixture trust grant, historical rescoring/evidence modification, new worktree, base refresh, invoking-framework knowledge bundle, commit/push/PR/merge or autonomy driver. Native allocations remain consumed; prior delivery authorization is fulfilled.

## Non-goals

Class/module/sibling registration; changing selected assertions or governance contracts; canonical/nonempty taxonomy or tuple/mapping/order/duplicate guarantees; REQUIRED values/stage requirements; arbitrary-tier regex safety; documentation/table/section/body semantics; actual tier/stage gates; extracted-command execution; native/model/session qualification; general dependency discovery; minimum input set; reduced full gates; automatic adoption; savings claims; planning before specification approval.

## Assumptions

D1–D4 below are approved decisions. Descriptions above as proposed retain drafting context and are superseded by this approval. Static source inspection establishes candidate scope, not runtime values or execution/count proof. The nine-case matrix assumes a separately confirmed runtime baseline of the four source-defined tiers; any difference needs scope review. Framework mode has no capability baseline to merge or bundle to initialize. Historical PASS/REUSE verifies no tenth profile. No candidate product test ran during drafting.

## Open questions

None. The user approved the specification and recommended D1–D4. Ready for planning only.

## Approved decisions

The recommended defaults below are approved; alternatives remain as decision context. The initial-drafting restriction on writing a plan is fulfilled. Implementation remains pending separate plan approval; all other restrictions remain.

- D1: Approve the exact method and `python-tier-doc-contract`, choose another candidate or stop expansion? Recommended: this exact method/ID only.
- D2: Approve six ordered patterns with conservative extra production invalidation, or require a smaller independently justified closure? Recommended: six, with the independent runtime-loop/two-read/interpolation/set oracle and explicit runtime limits.
- D3: Approve independent actual one-test proof, framework/adopter identity/freshness matrix and source-derived boundary controls, including nine intended assertion failures conditional on the confirmed four-tier baseline and four omission/matching/actual-zero controls? Recommended: yes; counts remain subject to source/runtime derivation and scope review on mismatch.
- D4: Preserve all nine complete profiles and existing mechanisms/manual adoption, limiting claims to per-observed-tier bold-substring/regex presence plus observed REQUIRED/TIERS set equality? Recommended: yes, with all stated limitations.

## Investigation evidence

Nonexecuting source inspection only:

- `.ai/scripts/tests/test_lifecycle_conformance.py:15-27,191-195`: shared root/import setup, called text helper, runtime TIERS loop, two literal direct reads, distinct interpolations and final set comparison.
- `.ai/scripts/lifecycle.py:41-77,1011,1209,1321`: eager imports, lazy setup, source tier/key definitions and decorator applications. Source values are not runtime proof; wrapper construction does not establish producer-body execution.
- `.ai/scripts/tests/disk_tmp.py:10-20`, `.ai/scripts/scratch.py:11-26`: helper calls require_disk; mount/cache/environment effects remain outside repository-file claims.
- `.ai/scripts/review_guard.py:23-26,629-639`, `.ai/scripts/ledger.py:10-22`: eager ledger/scratch initialization and protected/nested decorate construction.
- `.ai/scripts/assurance_inputs.py:17-163`: nine complete literal entries. Fresh structured search of this file and test_assurance_inputs.py found neither proposed exact selector nor proposed ID; generic RefusalTests:190-202 do not authorize replacing a negative expectation.
- `docs/assurance/handoff-5j.md` and leading authoritative Delivery complete update in `implementation-5i.md`: delivered identity and restrictions; earlier evidence is historical only.
- Local `repo.py context --json`: framework, expected branch/HEAD, clean tracked state; local refs only, no new remote check. New L2 declared after context. Intent remains unapproved.

Python persona materially affected the draft through import-time/called-helper boundaries, external storage/environment exclusions and count-first runtime proof. Required read-only analyst independently returned a complete draft and D1–D4 after source investigation; this persisted draft incorporates its requirements, actual-one-test failure proof and scope-review condition. No analyst product tests/runtime imports or file edits occurred.

## Draft validation

- `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5j.md` -> exit 1, only High open-questions finding for D1–D4. These are intentional approval blockers, not resolved contracts.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5j.md` -> exit 0, six requirements traced; no acceptance command executed.
- `git check-ignore docs/assurance/specification-5j.md` -> exit 0, ignored path confirmed.
- `git diff --check` and `git status --short --untracked-files=no` -> exit 0, tracked state clean. No remote check performed.

The initial analysis finding above is historical drafting evidence. Human approval resolves D1–D4 and authorizes planning only. No source edits or product tests occurred. Framework OKF synchronization is inapplicable because no bundle exists; no knowledge/log or records PASS is created or claimed.
