# Spec: static audit-record documentation input profile

Approved by human:enramosjr in this chat on 2026-10-29 America/Chicago: “Approved. Proceed with the implementation plan for 5g using the recommended D1–D4 decisions.” L2; analyst role; Python principal engineer. Acceptance commands name future checks, not execution results. Specification approval authorizes planning only; a separately approved plan is required before implementation.

## Problem and outcome

Maintainers have six delivered literal Python input profiles but no profile for the existing method-selected audit-record documentation check. Add one explicitly adopted profile through the existing exporter, with reviewed repository inputs and controlled freshness evidence. Framework mode has no knowledge bundle or structured capability baseline; this standalone specification creates neither and revises no historical evidence.

## Users and scenarios

A maintainer invokes the exporter from the repository root for exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Tiers.test_the_committed_audit_record_is_documented
```

Proposed ID: `python-audit-doc-contract`. The method loops over the literal tuple `(".ai/lifecycle.md", ".ai/docs/lifecycle.md")`. For each path it requires `knowledge/history/lifecycle/` and `lifecycle.py audit` in the whole document via `text(path)`. These are case-sensitive substring assertions. They do not establish section placement, path resolution, command validity, record creation, persistence, provenance, tamper detection or governance. The method executes no extracted command, accesses no lifecycle attribute and copies no scripts. Exactly one actual passing test is a future acceptance expectation, not current runtime proof; two loop iterations and four assertions are not four tests.

Approved ordered scope:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.ai/lifecycle.md
.ai/docs/lifecycle.md
```

The first pattern conservatively covers production eager imports and lazy-loader/decorator setup, including unused non-test descendants and future supported scripts. Extra invalidation is deliberate. The exclusion restores only the selected module and imported test helper. The last two literals are direct document reads, explicit despite general Markdown freshness exemptions. Neither root AGENTS nor validation-policy is a direct read of this method; prior-profile compatibility fixtures still need their own inputs. Class, sibling and module-wide execution are outside this exact-method claim.

## Requirements

- R1: The exporter MUST register only the exact repository-root argv above as `python-audit-doc-contract`. Class/module, sibling, discovery, option, alias and other-interpreter variants MUST remain unregistered unless already registered. All six delivered profiles MUST retain their IDs, argv, ordered inputs, rationales and behavior.
- R2: The profile MUST export exactly the six ordered patterns above before positive supplements, with per-pattern rationales distinguishing conservative import/setup scope, test exclusion/restoration and direct reads. An independent source-derived oracle MUST cover the selected method, its bounded literal path loop and `text(path)` calls, called text helper, eager initialization, called require_disk, lazy setup and protected/decorate construction. It MUST derive both document paths independently of the catalog; extracting only literal arguments to text calls is insufficient. Review guards MUST reject boundary drift and confirmed reachable excluded additions. Unrelated tests/documents MUST remain excluded. Conservative pins MUST NOT imply universal dataflow/read discovery or reachability of uncalled wrapped producer bodies.
- R3: Public text/JSON export MUST preserve existing token/Inputs/rationale parity, supplement order, root/path/inventory validation, nonexecution and refusal behavior. Export MUST neither import/execute the selected test nor validate document assertions, adopt Inputs or record evidence. Missing required literals and unsafe/unsupported paths or unknown commands MUST refuse nonzero with a reason and no usable candidate. Existing documents with failing assertions MUST remain exportable through path-only validation.
- R4: Adoption MUST remain explicit, advisory and manual. Existing inference, full suites, matching, freshness, schemas, gates and producer receipt exclusions MUST remain unchanged. The guide MUST name the exact command/ID, substring-only claim, conservative extra invalidation and runtime/read-completeness limits. It MUST NOT claim audit-record creation, persistence, provenance, tamper detection, command validity, native hooks, agent/model behavior, dynamic governance, session qualification or VERIFIED evidence from export.
- R5: An isolated framework fixture MUST drive public export and real lifecycle run/reuse. Independent captured unittest output MUST prove exactly one test executed and passed before exit interpretation. Recorded argv, ordered inputs and exit MUST match export; selected repository bytes MUST remain unchanged during execution. Evidence MUST REUSE unchanged and after unrelated-test/non-input-document edits; it MUST RERUN after separate assertion-preserving edits to each direct document, target, disk helper, representative production import and new supported non-test script. Edits MUST restore original bytes. The invoking framework MUST acquire no knowledge bundle. Four separate static-failure fixtures MUST make the actual selected command fail while export succeeds: remove each of the two required tokens from each of the two documents. Each removal MUST remove every occurrence of the selected token in that document, confirm changed bytes and establish the intended assertion failure.
- R6: A separate ordinary adopter fixture MUST explicitly adopt public export, become VERIFIED after independently proven actual one-test execution, remain VERIFIED after unrelated-test/non-input-document edits, and become STALE after each direct-document, target/helper, representative production import and new supported non-test script edit. Unmatched ordered declarations and argv identity MUST yield UNVERIFIED under existing rules; receipt exclusion MUST remain effective. Four confirmed disposable broken controls MUST be rejected: omission of either direct document, loose command matching and acceptance of actual zero-test execution. Each omission MUST fail its intended freshness assertion while assertion-preserving edits leave the selected check passing. The zero control MUST ignore the selector in an actual empty disposable suite, independently confirm Ran 0 tests, and reject count before version-dependent exit interpretation. A missing exact method yielding one loader failure is insufficient. Every control MUST confirm mutation bytes and its intended failure without altering historical evidence.

## Acceptance

Proposed AuditDoc classes below belong in `.ai/scripts/tests/test_assurance_inputs.py`; they do not yet exist. Missing classes, counts or end states fail acceptance. These commands MUST NOT execute during initial drafting. Boundary guards are conservative review guards, not general dependency discovery.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py AuditDocProfileTests` checks exact ID/argv/root matching, variant refusal and unchanged IDs/argv/ordered inputs/rationales of all six prior profiles.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py AuditDocDependencyTests` checks ordered scope/rationales, independent actual ledger selection, the bounded literal-loop read oracle, import/called-body boundaries, unrelated exclusions and future supported non-test descendants. The oracle MUST resolve the loop's literal tuple into both document paths, verify that the loop variable supplies the text calls, and retain an independently reviewed selected-method fingerprint. Each newly claimed reachable mutation MUST first fail actual selected execution with its excluded data absent, then pass exactly one test with that data supplied, before intended dependency-review rejection. Cover selected method, text helper, imported excluded helper and source-justified eager/called setup paths; derive the final variants from source rather than inheriting the previous profile's count. Confirm bytes; insert AST body changes after docstrings and before the earliest decorator of the first statement. Uncalled bodies may be pinned conservatively but MUST NOT be described as reached.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py AuditDocExportTests` checks public formats, supplements, immutability/nonexecution, every missing required literal and unsafe boundary, and path-only export of existing documents that fail selected assertions.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py AuditDocCompatibilityTests` checks guide claim/limitations and preservation of six profiles, inference/full suites, matching, schemas, gates and receipts through existing mechanisms. Prior compatibility fixtures retain their own required documents.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py AuditDocFrameworkEndToEndTests AuditDocFailureTests` checks independent actual one-test proof, byte stability, identities and each framework freshness outcome, separately from four confirmed static assertion failures.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py AuditDocAdopterEndToEndTests AuditDocControlTests` checks every adopter state/identity and receipt exclusion plus four confirmed broken controls, including both direct-document omissions and independent actual-zero rejection.

## Constraints

Use the existing literal catalog/export mechanism, Python 3.9+, standard library and unittest conventions. No new options, schemas, normalization, loader, inference, adoption automation, gates or approval authority. Inventory follows existing tracked/supported nonignored-untracked ledger rules. Executable/runtime environment, temporary storage/mount state, ignored files and external mutable data remain outside repository-file claims. Unresolved additional reads require review and retention of current scope.

Use only `/home/enramosjr/Projects/agentic-assurance-7`, existing branch `claude/assurance-increment-7`, delivered HEAD `c50034260a8c7e8a5ff42b44296720081dc9c039`. Keep docs/assurance artifacts ignored/local/uncommitted. Preserve 5f and all earlier records and their original source/runtime scopes; historical results verify no seventh profile. During drafting: no source edits, product tests, implementation plan, native/model evaluations, session registration/allocation, fixture trust grants, historical rescoring/evidence modification, new worktree, base refresh, knowledge bundle, commit/push/PR/merge or autonomy driver. Prior delivery authorization is fulfilled.

## Non-goals

Class/module/sibling registration; changing selected assertions or governance contracts; validating documentation semantics, audit paths, commands or record behavior; executing extracted commands; native/model/session qualification; general dependency discovery; minimum input set; reduced full gates; automatic adoption; savings claims; planning before specification approval.

## Assumptions

D1-D4 are approved decisions. Static inspection establishes candidate scope only. Future controlled fixture evidence cannot establish universal dependency completeness or runtime portability. Framework mode has no capability baseline to merge or bundle to initialize. Historical PASS/REUSE does not verify this profile. No new-profile product test has run during drafting.

## Open questions

None. The user approved the specification and recommended D1-D4. Ready for planning only.

## Approved decisions

The recommended defaults below are approved; alternatives remain as decision context.

- D1: Approve the exact method and `python-audit-doc-contract`, select another candidate or stop expansion? Recommended: approve this exact method/ID only; registration scope is a human contract choice.
- D2: Approve six ordered patterns with conservative extra production invalidation, or require a smaller independently justified closure? Recommended: six with stated limits and an independent source-derived bounded literal-loop oracle.
- D3: Approve R2/R5/R6's source-derived boundary controls, independent one-test proof, framework/adopter freshness and identity matrix, four static failures and four omission/matching/count controls? Recommended: yes. Final reachable variant scope must follow inspected source and fresh reachability proof, not historical counts.
- D4: Approve explicit advisory/manual adoption, preservation of all six profiles and existing inference/suites/schemas/gates, and substring-presence claims only? Recommended: yes.

## Investigation evidence

Nonexecuting inspection only:

- `test_lifecycle_conformance.py:15-27,203-206`: root/import setup, called text helper, bounded literal path loop and assertions. Siblings read broader inputs and/or lifecycle attributes; those are not inherited.
- `disk_tmp.py:10-20`, `scratch.py:11-26`: eager helper and called storage/mount validation; possible environment/cache mutation is outside repository-file scope.
- `lifecycle.py:41-66,1011,1209,1321,1994-1995`, `review_guard.py:23-26,629-639`, `ledger.py:10-22`: production imports, lazy setup and protected/decorate construction, independently rechecked by the analyst subagent. The selected method calls no wrapped producer.
- `assurance_inputs.py:17-115,179-230`: six literal entries, exact argv match, path-only validation and advisory formats/limits.
- `test_assurance_inputs.py:1585-1695`: prior setup/method pins and reachable mutation mechanism are references only; literal-call-only extraction is unsuitable for the selected loop.
- `.ai/lifecycle.md:158,169`, `.ai/docs/lifecycle.md:113-114`: structured search found the required tokens. Presence is no proof of command or audit behavior.
- `handoff-5g.md` and leading `implementation-5f.md`: authoritative delivery scope retained. Local context confirms framework mode, expected branch/HEAD and clean tracked status without a remote check. New L2 declared after loading context; no approval stage recorded.

## Draft validation

- `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5g.md` -> exit 1, only High open-questions finding for D1-D4. These deliberate human-approval blockers remain unresolved; no other finding reported.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5g.md` -> exit 0, six requirements traced. Structural evidence only; no acceptance command executed.
- `git check-ignore docs/assurance/specification-5g.md` -> exit 0, ignored path confirmed. Final local context -> expected branch/HEAD and clean tracked status; no remote check.
- Read-only analyst subagent independently confirmed the literal-loop read boundary, shared eager/called/lazy/protected setup, conservative six-pattern scope, four proposed static failures and four proposed omission/matching/count controls. Python persona considerations affecting the draft were import-time effects, called-helper closure, storage/environment limits and independent actual test-count proof. No source edits, product tests or implementation plan occurred. Intent remains unapproved.
