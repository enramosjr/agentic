# Spec: architecture compatibility validation input profile

Approved by human:enramosjr in chat, 2026-10-28 America/Chicago, including all four recommended defaults D1-D4. L2; Python principal engineer; analyst role. Approval authorizes planning only; implementation requires subsequent plan approval. All acceptance commands below are future checks, not execution receipts.

## Problem and outcome

The delivered exporter has one maintained Python profile. Maintainers need a second reviewed declaration for an existing architecture compatibility command whose repository reads include copied script inventories and Markdown, beyond Python imports. The outcome is one additional exact-command profile through the existing exporter, with explicit adoption and bounded freshness evidence. It does not reduce full-suite validation.

This framework has no knowledge bundle or structured capability baseline. This standalone follow-up specification extends the delivered framework feature; it does not convert a prose capability or alter the approved increment 5 specification or evidence.

## Users and scenarios

A maintainer invokes the exporter from the repository root for exactly:

```text
python3 .ai/scripts/tests/test_assurance_architecture.py CompatibilityTests
```

Proposed profile ID: `python-architecture-compatibility`. The class currently has two tests: the published demo/checkout-immutability check and the ungoverned public-shape check. The demo check asserts UNVERIFIED, VERIFIED, STALE, FAILED, VERIFIED, and reads the lifecycle guide.

Approved ordered scope:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_assurance_architecture.py
.ai/scripts/tests/test_assurance.py
.ai/scripts/tests/test_assurance_gate.py
.ai/scripts/tests/disk_tmp.py
.ai/lifecycle.md
```

The first pattern conservatively covers all supported non-test script-directory descendants, including non-Python files and future additions. It is intentionally broader than the top-level `*.py` files actually copied/watched today. Existing ordered fnmatch semantics exclude all tests, then restore the target and its three imported test helpers. The guide is a direct repository read. This is a reviewed repository-file declaration, not complete runtime read discovery.

## Requirements

- R1: The existing exporter MUST add only the exact repository-root argv above as `python-architecture-compatibility`. Full-module invocation, discovery variants, another class/method selection, additional options and other interpreter tokens MUST remain unregistered unless they already match a preexisting profile. The `python-runner-test` profile MUST retain its existing identity, argv and four inputs.
- R2: The new profile MUST export exactly the seven ordered patterns above before any positive supplements, preserving existing fnmatch exclusion/restoration semantics. Its per-pattern rationale MUST explain the conservative copied/watched script inventory, test exclusion, restored imports/helpers and direct guide read. A handwritten source-derived oracle independent of the catalog MUST establish coverage of the actual repository reads and exclusion of an unrelated test. It MUST NOT add `test_merge.py` without a newly established dependency or replace the copied-script boundary with only current imports.
- R3: The new profile MUST use the existing read-only export, validation, supplemental-input, text/JSON and refusal contracts. Export MUST NOT execute the supplied target, import its test modules or launch its demo, adopt Inputs or record evidence. Success MUST expose the exact argv, profile ID, ordered patterns, rationale, review/runtime limitations, Inputs line and lifecycle input tokens consistently in both formats. Missing required literal files, unsupported inventory/path boundaries and unregistered commands MUST refuse with nonzero, a reason and no usable candidate; positive supplements MUST remain validated and appended in order.
- R4: The change MUST preserve automatic inference, full-suite refusal and coverage, lifecycle/assurance matching and freshness rules, report schemas, gates and producer receipt exclusions. Adoption MUST remain explicit through existing mechanisms; new or reordered obligation inputs or changed command identity MUST require matching evidence under existing semantics. The lifecycle guide MUST document this exact profile, the copied-file and Markdown boundaries, conservative scope, explicit adoption and runtime/read-completeness limitations without claiming approval or VERIFIED evidence from export.
- R5: In an isolated framework fixture, acceptance MUST drive the public exporter and execute the exact selected command through existing lifecycle `run --inputs` and `reuse`. Independent preflight output MUST prove both current tests execute and pass, independently of suppressed lifecycle output, while preserving the target's five-state demo and checkout-immutability assertions. The recorded command, ordered declaration and successful exit MUST match the export. Fresh evidence MUST yield REUSE after an unrelated test edit and RERUN after an edit to each restored test/helper, the guide, a production script, or addition of a supported untracked top-level script. Selected inputs MUST remain unchanged during execution, and the invoking framework checkout MUST acquire no knowledge bundle.
- R6: In a separate ordinary adopter fixture, explicit adoption of the public export MUST yield VERIFIED after the actual selected command passes, retain VERIFIED after an unrelated test edit, yield STALE after relevant guide/helper/production-script edits and a newly added supported script, and yield UNVERIFIED after an unmatched ordered declaration change. Existing receipt exclusion MUST be retained. Acceptance MUST demonstrably fail for confirmed broken variants that omit the guide or a restored helper, loosen exact command matching, or permit zero tests to stand as successful execution. Controls MUST use disposable copies and independently confirm their mutation and failing criterion; they MUST NOT modify historical evidence or invoke native/model evaluation.

## Acceptance

These proposed NEW classes belong in the existing `.ai/scripts/tests/test_assurance_inputs.py`. They are not implemented or executed during drafting. Each command must fail for a missing class; preflight must check the actual nonempty unittest count before interpreting an exit code. The current selected command runs exactly two tests; a later change to that expectation requires review of the oracle and profile.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py ArchitectureProfileTests` checks the single new identity/exact argv, rejects full-module/class/method/interpreter/option variants, and asserts the original profile remains unchanged.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py ArchitectureDependencyTests` checks exact ordered patterns and rationale, resolves the exported scope through existing ledger semantics against an independent handwritten oracle, covers top-level copied scripts and a future supported script, restores all four test files, includes the guide and excludes an unrelated test. Source sentinels flag changes to the reviewed import/copy/guide boundaries for review.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py ArchitectureExportTests` exercises public text/JSON, token/order parity, positive supplements, source/evidence immutability, target/test/demo nonexecution sentinels and refusal without candidates for missing required literals and existing unsafe/unsupported boundaries.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py ArchitectureCompatibilityTests` checks guide statements and unchanged first-profile, full-suite refusal, inference, declaration identity and receipt behavior, retaining the existing profile acceptance coverage.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py ArchitectureFrameworkEndToEndTests` runs the real class-selected command, asserts exactly two passing tests from independent output, preserves the real demo assertions, checks exact ledger identity and stable execution inputs, then asserts every framework reuse/invalidation outcome in R5. Empty execution, unusable export or missing end states fail.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py ArchitectureAdopterEndToEndTests ArchitectureControlTests` asserts all adopter end states and receipt exclusion, and confirms the four broken variants in R6 are present and rejected by their intended assertions. A missing guide scope must fail a guide-freshness assertion even when the underlying command still passes.

## Constraints

Use the existing literal catalog/export mechanism in `assurance_inputs.py`, Python 3.9+, standard library and unittest conventions. No new CLI options, schema, loader, inference, automatic adoption or evidence authority. Keep existing first-profile tests meaningful when the catalog contains two profiles. Future implementation requires both human spec approval and approval of a subsequent plan.

The file inventory remains tracked plus supported nonignored untracked files under existing ledger rules. Ignored/external mutable data, resolved runtime executables, environment, temporary storage and mount state remain outside the profile's repository-file completeness claim. Generated adopter capabilities, checkers and data are temporary fixture content, not invoking-checkout input paths. New unresolved repository/application reads require review and retaining current scope rather than silently narrowing.

Use only `/home/enramosjr/Projects/agentic-assurance-7`, existing branch `claude/assurance-increment-7`, base HEAD `4ed2aec3a33f3369ff44abf686a7796e5661be3a`. Working `docs/assurance` artifacts stay ignored, local and uncommitted. Preserve increment 5 receipts and its historical full-gate scope. No source changes, product tests, native/model attempts, native sessions, trust grants, rescoring, historical evidence changes, new worktree, knowledge bundle, commit, push, PR or merge are authorized by this drafting task.

## Non-goals

Full architecture-module registration; all-tests catalog; import inference or runtime tracing; minimum possible input set; narrower full gates; profile auto-application; test selection; new language adapter; whole-project savings claims; executing acceptance or creating an implementation plan before approval.

## Assumptions

D1-D4 below are approved decisions; their recommended defaults were accepted by the user. Source inspection establishes candidate reads, not a new runtime PASS. No preexisting evidence verifies this new profile. The future fixtures demonstrate only their controlled boundaries and runtime, not arbitrary environment portability or complete dependency discovery.

## Open questions

None. The user approved all four recommended defaults and the specification. Ready for planning only.

## Approved decisions

The recommendations in D1-D4 below are approved; alternatives are retained only to explain the decision.

- D1 — Register only the exact class-selected argv and suggested profile ID, or also support the full architecture module? Recommendation: exact class only, ID `python-architecture-compatibility`; no aliases or normalization. Source shows the class executes, but cannot settle desired registration scope.
- D2 — Approve the seven ordered patterns, including the intentionally conservative `.ai/scripts/**` boundary, or require a smaller production scope? Recommendation: approve the seven patterns; tolerate invalidation from unused non-test script descendants to cover directory-copy growth. This is a conservatism choice, not an import-completeness inference.
- D3 — Require both real framework/adopter freshness flows and the four confirmed broken variants described in R5-R6? Recommendation: yes, including independently proven execution of both tests, unrelated-test reuse, guide/helper/script/addition invalidation and the missing-guide control. These checks establish bounded usefulness rather than measured project-wide savings.
- D4 — Keep this a standalone advisory export with manual adoption, unchanged original profile, inference and full-suite behavior? Recommendation: yes. Export does not establish authority or approval. The framework source answers current behavior; human approval settles the extension's compatibility contract.

## Investigation evidence

Non-executing source inspection only:

- `.ai/scripts/tests/test_assurance_architecture.py:11-14,22-25,303-332`: helper imports, inherited fixture, two selected tests, script byte watches, demo subprocess, all five statuses, direct guide reads and unittest entry point.
- `.ai/scripts/tests/test_assurance.py:13-15,29-47` and `.ai/scripts/tests/test_assurance_gate.py:7-9`: actual helper chain and all-top-level-script fixture copy. DeltaCase is in the gate module, not test_merge.
- `.ai/scripts/assurance_architecture_demo.py:15,51-93` and `.ai/scripts/assurance_demo.py:24,89-106`: demo helper, temporary flow and independent all-top-level-script copy.
- `.ai/scripts/tests/disk_tmp.py:10-20` and `.ai/scripts/scratch.py:16-25`: disk-backed temporary helper and runtime mount boundary.
- `.ai/scripts/assurance_inputs.py:17-35,58-83,93-144,152-183`: current single profile, exact matching, ordered export, catalog/path validation and refusal contract.
- `.ai/scripts/ledger.py:44-48,55-91`: fnmatch semantics, unchanged inference and ordered supported Git inventory.
- `.ai/scripts/tests/test_assurance_inputs.py:22-25,111-117,265-338`: independent oracle, count preflight and current framework/adopter fixtures; no new acceptance execution.
- `.ai/lifecycle.md:210-218`: current advisory exporter/adoption documentation. Leading delivery updates in `handoff-5.md` and `implementation-5.md` preserve the authoritative increment 5 closeout.
