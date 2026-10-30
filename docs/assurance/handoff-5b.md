# Next slice handoff: architecture compatibility input profile

Selected after increment 5 delivery, 2026-10-28 America/Chicago. This is a scope and handoff plan, not an approved behavior specification or implementation plan.

## Start here

Use `/home/enramosjr/Projects/agentic-assurance-7` explicitly for every repository command. Existing branch `claude/assurance-increment-7`, HEAD `4ed2aec3a33f3369ff44abf686a7796e5661be3a`, pushed to the matching origin branch. Exact remote/local HEAD match and clean tracked status were confirmed after delivery. Do not create another worktree or use the project's default checkout.

Read the leading delivery updates in handoff-5.md and implementation-5.md first. Increment 5 is complete and delivered; do not restart or rerun it. Its lifecycle is closed through Ship. Start the next slice in a fresh chat and a NEW lifecycle only after its task context is loaded. Likely L2/Python principal engineer because adding a supported command changes the exporter's contract; select from actual scope.

Framework mode has no knowledge bundle. `okf.py handoff --prompt` reports no bundle here and cannot supply an adopter queue brief. Use this explicit prompt plus `repo.py context --json`; do not initialize knowledge or invent framework capabilities. All docs/assurance artifacts are ignored and must remain uncommitted.

## Why this chunk

The original roadmap's increments 1–7 have delivered slices under their accepted scopes: obligations/reporting, freshness gate, governed references, attested/risk reporting, Python input-profile pilot, demo and measurement. The historical roadmap's language order was superseded by the user's explicit Python/framework instruction. This follow-up extends the accepted increment 5 model rather than inventing an unfinished numbered roadmap step or a new language adapter.

The first profile covers four Python files. The next useful example is the EXISTING architecture compatibility check, which already reads real Markdown and executes/copies Python scripts. It demonstrates a non-code dependency and directory-wide copy boundary while keeping the full framework gate broad. It is a bounded second profile, not an all-tests catalog or import-inference feature.

## Proposed scope, requiring spec approval

One new exact registered argv:

```text
python3 .ai/scripts/tests/test_assurance_architecture.py CompatibilityTests
```

Suggested profile ID: `python-architecture-compatibility`. Keep `python-runner-test` and its behavior unchanged. No new CLI options, profile loader, automatic adoption, inference, evidence schema or gate changes are proposed.

Candidate ordered input scope, subject to full source review and explicit approval:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_assurance_architecture.py
.ai/scripts/tests/test_assurance.py
.ai/scripts/tests/test_assurance_gate.py
.ai/scripts/tests/disk_tmp.py
.ai/lifecycle.md
```

The starting directory scope conservatively covers all production scripts, including future copied-script additions. The exclusion avoids declaring every unrelated test module; explicit restores cover the target and imported fixture helpers. Include the guide because this command actually reads it. Do not replace this with an enumerated list of currently imported production modules: the fixture and demo copy every top-level script. Existing fnmatch semantics and pattern order must be preserved; ordinary filesystem glob assumptions are insufficient.

This is an inspected CANDIDATE, not an approved or verified complete read set. Any additional repository dependency found during the next analyst pass widens it or becomes a behavior decision. Do not claim all native/model or runtime dependencies are captured.

## Inspected source evidence

- `.ai/scripts/tests/test_assurance_architecture.py:11-14`: imports test_assurance, test_assurance_gate, assurance and lifecycle. `CompatibilityTests` inherits the real Case fixture via GovernedCase.
- `.ai/scripts/tests/test_assurance_architecture.py:303-328`: two selected compatibility methods. The demo method watches every top-level Python script, launches assurance_architecture_demo.py, asserts five actual statuses, then reads and checks `.ai/lifecycle.md`. The other method checks ungoverned report behavior.
- `.ai/scripts/tests/test_assurance_architecture.py:331-332`: unittest main exists, so the exact direct-script class selection is an executing check. This command shape already appears in the prior increment 3 acceptance contract.
- `.ai/scripts/tests/test_assurance.py:13-15,29-41`: disk_tmp/ledger/scratch helpers, copies all scripts, initializes a temporary ordinary adopter and drives actual CLI behavior.
- `.ai/scripts/tests/test_assurance_gate.py:7-9,248`: imports test_assurance and production modules; DeltaCase is defined in that same module. There is no test_merge import in this chain. Do not add test_merge just because its filename sounds relevant.
- `.ai/scripts/assurance_architecture_demo.py:15,51-93`: uses assurance_demo, runs an ordinary temporary assurance flow and checks actual status/governance results.
- `.ai/scripts/assurance_demo.py:24,89-106`: scratch helper and an all-top-level-script copy into a throwaway Git repository. Runtime/temp state remains outside the repository-file profile claim.
- `.ai/scripts/assurance_inputs.py`: existing literal profile catalog, exact matching, glob validation, inventory refusal and text/JSON exporter. Reuse it; do not add a second mechanism.
- `.ai/scripts/tests/test_assurance_inputs.py`: existing independent read oracle, source sentinels, profile/refusal/output coverage and public framework/adopter fixture flows. Preserve their coverage while adding profile-specific cases.

No check or product suite was run to select this chunk. These statements are based on bounded source inspection, not a new PASS claim.

## Behavior decisions to bring back before coding

1. Exact scope: register only the class-selected command above, or also the full architecture module? Recommended: class only; no automatic normalization or aliases.
2. Input boundary: accept the candidate ordered scope after complete source review? Recommended: copied production-script directory scope, restored actual test helpers and explicit guide; widen on discovered reads rather than guessing them away.
3. Evidence: which new fixture assertions establish useful narrowing? Recommended: nonempty execution of the actual command, lifecycle reuse after an unrelated test edit, invalidation after guide/helper/production-script edits or newly added copied scripts, and a control that omits the guide. Preserve the actual five-state demo assertions. Do not derive the expected reads from the profile itself.
4. Compatibility/application: keep standalone advisory export, manual adoption, unchanged first profile and full-suite refusal? Recommended: yes; no new authority or gate.

## Handoff execution outline

1. Fresh chat: load this brief, repo context, matching analyst/persona/spec instructions; declare a new lifecycle without modifying the closed increment 5 record. Draft a short spec with requirement IDs and future failing-closed acceptance commands. Resolve the decisions above and obtain human approval before planning/coding.
2. After spec approval: full implementation plan, likely changes only to existing assurance_inputs.py, its test module and lifecycle guide. Plan fixture ownership, test-first behavior and exact input/provenance assertions; obtain plan approval.
3. After plan approval: implement one catalog addition and bounded tests/guide edits. Use an independent handwritten source-read oracle, exact command matching and positive/negative path tests. Do not recursively invoke the entire adapter test module as its own E2E target.
4. Run focused tests and the real slice E2E, then source controls, guide synchronization, retrospective, convergence and independent review. Run the full framework gate once on the final reviewed candidate. It is not authorized merely by this selection/handoff.
5. Stop at verified/uncommitted unless the user separately authorizes delivery. Never open a PR, push a new slice or merge based only on the completed increment 5 delivery instruction.

## Evidence to preserve

Increment 5: seven requirement receipts, Approved independent review, four confirmed source controls and full framework PASS on precommit tree b52be33; retrospective closed with observation 1. Delivery changed no source. The delivery-turn framework reuse check reported environment/runtime drift, so no fresh full-gate PASS or REUSE was claimed. Existing source controls returned REUSE for unchanged b52be33. Native historical results retain original scopes; all native allocations are consumed.

No new native/model evaluation attempt, temporary fixture trust grant, native session, rescoring or historical evidence modification is authorized. No new worktree or knowledge bundle. Source commit/push only on explicit instruction; no PR or merge is authorized.

## Fresh-chat resume prompt

Read docs/assurance/handoff-5b.md in /home/enramosjr/Projects/agentic-assurance-7. Increment 5 was committed and pushed as 4ed2aec3a33f3369ff44abf686a7796e5661be3a; its leading delivery updates are authoritative and its lifecycle is closed. Scope the selected follow-up: one reviewed Python input profile for `python3 .ai/scripts/tests/test_assurance_architecture.py CompatibilityTests`. Start with the cited actual Python/subprocess/Markdown dependencies, draft the spec, and bring the behavior decisions back before implementation. No new native/model evaluations, trust grants, worktrees or knowledge bundle. All docs/assurance artifacts stay ignored/uncommitted. Use the existing checkout explicitly; preserve prior evidence and do not rerun completed suites just for a fresh chat. Obtain spec and plan approval before coding. This handoff does not authorize delivery, a PR or any merge.
