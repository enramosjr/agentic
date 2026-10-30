# Spec: static harness-wiring validation input profile

Approved by human:enramosjr in this chat, 2026-10-29 America/Chicago: “Approve specification-5c.md and all four recommended decisions. Record the approval and draft the implementation plan for review; do not start coding yet.” L2; analyst role; Python principal engineer. Approval authorizes planning only. Acceptance commands below name future checks, not existing results; no product-test execution or new runtime evidence is recorded.

## Problem and outcome

Maintainers have two declared Python input profiles but no reviewed profile for the existing class-selected static cross-harness wiring check. The proposed outcome is one additional exact-command profile through the existing literal catalog/export mechanism, with explicit adoption and bounded freshness evidence. This framework has no knowledge bundle or structured capability baseline; this standalone follow-up does not create either or revise earlier specifications/evidence.

## Users and scenarios

A maintainer invokes the exporter from the repository root for exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py HarnessWiring
```

Proposed ID: `python-harness-wiring`. The selected class currently has three tests. They parse the three hook JSON files and assert lifecycle wiring declarations: Claude Edit/Write/Bash and SessionStart, Codex apply_patch/Bash and SessionStart, and Cursor preToolUse/beforeShellExecution/sessionStart. They do not run the declared hook commands or prove native enforcement, session authenticity or model behavior.

Approved ordered scope:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.claude/settings.json
.codex/hooks.json
.cursor/hooks.json
```

The script-directory scope conservatively covers production imports and lazy-loader setup, including future supported non-test descendants and unused files. It is not a copied-script boundary: this class copies no directory and reads no lifecycle guide. Existing ordered fnmatch semantics exclude tests, then restore only the selected module and disk temporary helper. The three JSON literals are direct reads. Extra invalidation from unrelated non-test script descendants is an explicit tradeoff proposed in D2.

## Requirements

- R1: The exporter MUST add only the exact repository-root argv above as `python-harness-wiring`. Full-module, other-class/method, discovery, option and other-interpreter variants MUST remain unregistered unless they match an existing profile. Both existing profiles MUST preserve their identities, argv, ordered inputs, rationales and behavior.
- R2: The new profile MUST export exactly the seven ordered patterns above before positive supplements, with per-pattern rationale for conservative production import/lazy-setup coverage, test exclusion/restoration and the three direct JSON reads. An independent source-derived oracle MUST cover the selected class's repository reads and import-time dependencies, exclude unrelated tests/documents, and flag changes to reviewed dependency boundaries. It MUST NOT inherit architecture-profile helpers, guide inputs or copied-script rationale without a newly established read.
- R3: The profile MUST retain existing read-only text/JSON export, ordered supplement, path/inventory validation and refusal contracts. Export MUST expose consistent exact argv, ID, ordered Inputs, lifecycle tokens, rationale and review/runtime limitations without importing/executing the selected module, parsing hook JSON for semantic validity, adopting Inputs or recording evidence. Missing required literals, unsafe/unsupported boundaries and unknown commands MUST refuse nonzero with a reason and no usable candidate. Malformed JSON remains an execution failure of the selected check, not a new export parser responsibility.
- R4: Automatic inference, full-suite refusal/coverage, lifecycle/assurance matching and freshness, report schemas, gates and producer receipt exclusions MUST remain unchanged. Adoption MUST remain explicit and advisory. Documentation MUST identify this exact command/profile, static declaration scope, conservative invalidation, runtime/read-completeness limits and manual adoption without claiming native enforcement, approval or VERIFIED evidence from export.
- R5: An isolated framework fixture MUST drive the public exporter and real lifecycle run/reuse for the exact selected command. Independent preflight output MUST prove exactly three tests execute and pass before interpreting exit status. Recorded argv, ordered inputs and exit MUST match export, and selected repository bytes MUST stay unchanged during execution. Fresh evidence MUST REUSE unchanged and after an unrelated test or non-input document edit, and MUST RERUN after separate edits to each JSON, the target, disk_tmp, a production import, or a newly added supported non-test script. The invoking framework checkout MUST acquire no knowledge bundle. Disposable malformed-JSON and missing-required-wiring controls for each harness MUST make the actual selected command fail, while export retains its existing path-only validation.
- R6: A separate ordinary adopter fixture MUST explicitly adopt the public export, become VERIFIED after actual three-test execution, remain VERIFIED after unrelated test/document edits, and become STALE after each JSON, helper/target or representative production input edit and a new supported non-test script. Changed unmatched ordered declarations or command identity MUST yield UNVERIFIED under existing matching rules; producer receipt exclusion MUST remain effective. Confirmed disposable broken variants MUST be rejected for omitting each JSON from scope, loosening exact-command matching, or accepting zero-test execution. Each omitted-JSON variant MUST fail the intended freshness assertion even when the valid static wiring command still passes. Controls MUST independently confirm mutation bytes and intended failure, preserving historical evidence and avoiding native/model/session/trust operations.

## Acceptance

These proposed classes belong in existing `.ai/scripts/tests/test_assurance_inputs.py`; they are not implemented or executed during drafting. Missing classes, absent execution counts or missing required end states fail acceptance. Expectations and source-derived oracles require review when the selected class changes. JSON freshness edits must preserve valid JSON and required wiring, distinguishing freshness checks from deliberate malformed/missing-wiring execution controls.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py HarnessWiringProfileTests` checks exact ID/argv/root matching, rejection of variants, and unchanged identities/argv/ordered inputs for both prior profiles.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py HarnessWiringDependencyTests` checks exact ordered patterns/rationale, independent import/direct-read coverage through actual ledger selection, exclusion of unrelated tests/documents and inclusion of future non-test scripts/descendants. Source sentinels require review on dependency-boundary drift.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py HarnessWiringExportTests` checks public text/JSON and parser/token parity, positive supplements, source/evidence immutability, nonexecution sentinels, refusal for each missing literal and unsafe/unsupported path, and successful path-only export with invalid hook JSON.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py HarnessWiringCompatibilityTests` checks static/advisory guide claims, both prior profiles, full-suite refusal/coverage and inference, exact command/declaration evidence matching and receipt behavior using existing public mechanisms.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py HarnessWiringFrameworkEndToEndTests HarnessWiringFailureTests` independently checks exactly three passing tests, real lifecycle record/reuse identity and byte stability, every listed framework freshness outcome, and actual target failures for malformed JSON and removed required wiring in each of the three fixture JSON files. JSON fixtures are data; native hooks are never installed or invoked by these checks.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py HarnessWiringAdopterEndToEndTests HarnessWiringControlTests` asserts the adopter's listed statuses, command/declaration mismatch and receipt behavior, then confirms and rejects all five broken variants: three omitted-JSON scopes, loose exact-command matching and zero-test execution. Omitted-JSON controls fail on missed freshness, not on JSON syntax or static wiring.

## Constraints

Use existing literal catalog/export mechanism, Python 3.9+, standard library and unittest conventions. No additional options, schemas, loader, normalization, inference, automatic adoption, enforcement gate or approval authority. Repository inventory remains tracked plus supported nonignored untracked files under existing ledger rules. Runtime executable/environment, temporary storage/mount state, ignored files and external mutable data remain outside the repository-file claim. Unresolved new reads require review and retaining current scope.

Operate only in `/home/enramosjr/Projects/agentic-assurance-7`, existing branch `claude/assurance-increment-7`, delivered HEAD `95c873d896e1ef53b89dcb75e6f6e1c1984c517e`. Keep all `docs/assurance` artifacts ignored, local and uncommitted. Preserve historical evidence with its original source/runtime scope. This drafting task authorizes no source edits, product tests, native/model evaluation, sessions, fixture trust grant, historical rescoring, new worktree, base refresh, knowledge bundle, commit/push/PR/merge. Human spec approval permits planning only; a separately approved plan is required before implementation.

## Non-goals

Full conformance-module registration; other test classes; native hook execution or qualification; session authentication; model evaluation; import discovery/inference; minimum possible input set; reduced full gates; automatic adoption; architecture-profile dependency copying; project-wide savings claims; implementation planning before approval.

## Assumptions

D1-D4 below are approved decisions. Source inspection is not runtime proof. Earlier PASS evidence does not verify this new profile. Future fixture evidence would establish only controlled repository-file/runtime boundaries, not universal portability or complete dependency discovery.

## Open questions

None. The user approved the specification and all four recommended decisions. Ready for planning only; implementation requires separate plan approval.

## Approved decisions

The user approved the recommended defaults in D1-D4 below. Questions and alternatives are retained as decision context.

- D1: Approve only the exact class-selected command and ID `python-harness-wiring`? Recommended: yes; no aliases or broader forms. Source proves an entry point exists, but cannot settle intended registration scope.
- D2: Approve the seven ordered patterns with conservative non-test script coverage and extra invalidation, or require a smaller independently reviewed import closure? Recommended: seven patterns; import/lazy-setup coverage is the rationale, not directory copying.
- D3: Approve the R5-R6 execution/freshness matrix, independent three-test count, malformed/missing-wiring controls per harness, and five confirmed broken variants including each omitted JSON? Recommended: yes. This establishes controlled freshness and execution evidence, not native enforcement.
- D4: Keep the extension advisory with explicit manual adoption, unchanged existing profiles/full suites/inference/schemas/gates, and static wiring claims only? Recommended: yes.

## Investigation evidence

Non-executing source inspection only:

- `.ai/scripts/tests/test_lifecycle_conformance.py:15-27,270-298`: root calculation, disk_tmp/lifecycle imports, direct text reads, three static JSON tests and direct unittest entry point. Other classes' broader reads are not selected.
- `.ai/scripts/tests/disk_tmp.py:10-20` imports scratch and immediately probes tempfile storage, potentially creating/configuring a cache directory and changing environment state. `.ai/scripts/scratch.py:11-25` imports stdlib and probes `/proc/self/mountinfo`; these are ambient runtime effects outside the repository-file claim.
- `.ai/scripts/lifecycle.py:41-66` eagerly imports scratch/review_guard and registers lazy modules brownfield/okf/learning/ledger/scan/project_context/assurance. `.ai/scripts/review_guard.py:23-26` eagerly imports ledger/scratch; `.ai/scripts/ledger.py:10-22` imports stdlib only. Ledger is already loaded when lazy setup sees it; the other lazy module bodies remain unexecuted because HarnessWiring accesses no lifecycle attributes. Lazy setup uses script paths; the conservative scope includes them without asserting their bodies run.
- `.ai/scripts/review_guard.py:629-639` constructs protected wrappers during import; producer activity requires a wrapper call. `.ai/scripts/lifecycle.py:1994-1995` guards CLI execution. No additional non-script repository read was found on this selected path. This is static inspection, not runtime tracing or universal dependency discovery.
- `.ai/scripts/assurance_inputs.py:17-53,75-161,169-204`: both existing literal profiles; exact argv/root matching; ordered scope/path validation; formats/refusal and advisory limitations. Export does not import supplied tests or parse their hook JSON.
- `.ai/scripts/tests/test_assurance_inputs.py:341-529`: existing independent oracle, actual count-before-exit preflight, public export, framework lifecycle identity and freshness conventions. Architecture copied-script and guide assumptions do not apply to HarnessWiring.
- `.claude/settings.json:17-73`, `.codex/hooks.json:2-57`, `.cursor/hooks.json:3-27`: declared events/matchers/command strings parsed as data; this inspection executes none of them.
- `.ai/lifecycle.md:210-222`: existing explicit/advisory export and compatibility contract.

Human approval is recorded above; lifecycle Intent registration follows non-executing validation. No acceptance or product command has run for this proposal.

## Draft validation

- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5c.md` -> exit 0, six requirements traced to acceptance commands. This does not establish implementation or execution.
- Before approval, `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5c.md` -> exit 1, High open-questions finding for D1-D4; no other finding reported. Historical drafting result, superseded by approval and subsequent validation.
- `git check-ignore docs/assurance/specification-5c.md` -> exit 0, ignored path confirmed. No historical receipt or tracked source was changed by drafting.
