# Next slice handoff: static harness-wiring input profile

Prepared 2026-10-29 America/Chicago at the user's request. This is a selected candidate and fresh-chat brief, not an approved specification or implementation plan. No implementation is authorized by this handoff.

## Start here

Run EVERY repository command explicitly with cwd `/home/enramosjr/Projects/agentic-assurance-7`. The saved project's default `/home/enramosjr/Projects/agentic` is a different checkout. Do not use it, create another worktree, change branches or reset this checkout.

Existing branch: `claude/assurance-increment-7`. HEAD: `95c873d896e1ef53b89dcb75e6f6e1c1984c517e`, committed and pushed to the matching origin branch. Exact remote/local match was confirmed at delivery; current handoff inspection found clean tracked status and equal local refs. No remote recheck or fetch was performed for this handoff.

Read the leading Delivery complete update in `implementation-5b.md` first; its delivery update supersedes older uncommitted/pending language below it. Increment 5b is closed through Ship. This handoff uses a separate documentation-only L0 declaration without changing the delivered feature record. L0 has no stages, so Ship is inapplicable to this handoff. The next chat must use `lifecycle.py tier L2 --new ...` after loading context, because registration extends the exporter contract; do not reuse the documentation-only L0 declaration.

Framework mode has no knowledge bundle. Use `python3 .ai/scripts/repo.py context --json`, not `okf.py handoff --prompt` or knowledge initialization. Every docs/assurance artifact stays ignored, local and UNCOMMITTED. Follow AGENTS.md, bounded persona/role reads, and spec/analyst instructions. Persist future drafts in this ignored directory.

## Delivered baseline to preserve

The exporter now has two profiles: python-runner-test and python-architecture-compatibility. Increment 5b changed exactly assurance_inputs.py, test_assurance_inputs.py and lifecycle.md. Production change was one literal catalog entry; exporter algorithms, original profile, inference and full-suite behavior stayed unchanged.

Evidence: six requirements PASS, zero FAIL/MANUAL in converge-5b.log; four confirmed source controls rejected for their intended criteria; complete Approved independent review in review-5b.md; one frozen-candidate full framework PASS on source tree e59f8f4 in framework-5b.log; formal Verify and Ship recorded. Retrospective closed with no new lessons, applying existing independent-count and confirmed-mutation observations. Successful full-gate child output was suppressed; no full-suite count is claimed.

Delivery changed no source. Reuse at delivery reported environment/runtime drift, NOT a new PASS or REUSE. Historical evidence retains its recorded source/runtime scope. Do not rerun old suites just because this is a fresh chat, or claim those receipts verify a third profile. Preserve increment 5 and earlier native evidence unchanged; all native allocations are consumed.

## Selected next useful slice

Add one reviewed profile for this EXISTING exact command, subject to spec approval:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py HarnessWiring
```

Suggested ID: `python-harness-wiring`. The class currently contains three tests that parse Claude, Codex and Cursor hook JSON and assert required wiring declarations. A third profile supplies a useful cross-harness configuration boundary beyond the existing Python-file and Markdown examples, while remaining small enough to inspect.

Claim only static wiring conformance. These tests do not execute a native hook, establish actual edit/commit enforcement, authenticate sessions or qualify model behavior. No new native/model run, session allocation or trust operation is needed or authorized.

Keep both existing profiles and full-suite behavior unchanged. No additional command forms, options, inference, automatic adoption, schemas, profile loaders or approval authority are selected.

## Source-backed candidate scope

An initial conservative candidate, NOT an approved or verified complete read set:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.claude/settings.json
.codex/hooks.json
.cursor/hooks.json
```

The script-directory pattern conservatively covers production imports/lazy-loader setup, not a copied-directory requirement of this selected class. It includes unused non-test descendants and can cause extra invalidation. Unlike the architecture class, HarnessWiring does not itself copy scripts or read lifecycle.md. Do not reuse that class's rationale or add its fixture helpers/Markdown dependency by analogy. Inspect complete import-time effects before approving any scope; compare a smaller explicit production list only after establishing its actual closure. Preserve ordered fnmatch semantics.

Inspected evidence:

- `test_lifecycle_conformance.py:15-20,26-27`: repository-root path calculation, disk_tmp and lifecycle imports, text helper reads from that root.
- `:270-294`: HarnessWiring reads exactly the three hook JSON files above; asserts Claude Edit/Write/Bash and SessionStart wiring, Codex apply_patch/Bash and SessionStart wiring, and Cursor preToolUse/beforeShellExecution/sessionStart declarations. Three test methods exist.
- `:297-298`: unittest main makes direct class-selected execution an executing command shape. This handoff did not execute it.
- Other classes in the same module read roles, skills, docs, recurse over trees or use historical Git revisions (`:68-131,150-187`). They are not selected. Full-module registration would require a much broader, separately reviewed boundary; do not silently add it.
- `lifecycle.py:41-66`: eager scratch/review_guard imports plus lazy setup for brownfield, okf, learning, ledger, scan, project_context and assurance. `review_guard.py:23-26` imports ledger/scratch. This is a starting import inspection, not proof all transitive import-time reads are settled.
- `disk_tmp.py:10-20` imports scratch, probes temporary storage and may configure it. `scratch.py:11-25` reads runtime mount information. Ambient runtime/temp/mount state remains outside the repository-file claim.
- `assurance_inputs.py:17-46` contains the two current literal profiles; use the existing mechanism and path validation.
- Existing architecture acceptance in test_assurance_inputs.py demonstrates independent read oracles, exact counts, public export, framework/adopter freshness and confirmed disposable source controls. Reuse conventions, not copied assumptions about this target's dependencies.

The three hook JSON paths exist in the tracked inventory. Their bytes were not interpreted as instructions. No product/test command, hook or native evaluation was executed during selection.

## Decisions for the next analyst to bring to the user

1. Exact registration: class-selected command only or broader forms? Recommended: this exact argv and ID only; no aliases or full-module profile.
2. Input conservatism: approve the seven candidate patterns after complete import/read review, or use an independently justified explicit production list? Recommended starting point: the conservative scripts scope plus two actual test files and three required JSON literals; state extra invalidation clearly. New evidence can require widening or a different proposal.
3. Freshness/execution proof: recommended actual three-test count independently captured before interpreting exit status, real lifecycle run/reuse, REUSE after an unrelated test or non-input document edit, RERUN/STALE after each hook JSON/helper/production input edit, and explicit adopter command/declaration identity checks. A confirmed omitted-JSON scope control must break the intended freshness assertion. Invalid JSON or removed required wiring must make the actual command fail; export itself should remain existing path validation, not a new hook-JSON parser. Final criteria/control breadth require spec approval.
4. Compatibility/application: recommended standalone advisory export/manual adoption, both prior profiles unchanged, no hook edits or actual native enforcement claim. In fixtures only, hook JSON content is test data; do not install/activate hooks or invoke model/native sessions.

## Fresh-chat task

Read this handoff and authoritative increment 5b delivery update. Inspect the cited target/import paths under analyst/Python guidance, draft an ignored `docs/assurance/specification-5c.md`, run non-executing analyze/trace as appropriate, and bring behavior decisions back to the user BEFORE planning or coding. Recommended defaults here are proposals, not approvals. Human specification approval permits drafting a plan; a separately approved plan is required before implementation.

No feature source edits, product tests, commits, pushes, PRs, merges, base refresh, new worktrees, knowledge bundles, native/model evaluations, native sessions, fixture trust grants, rescoring or historical evidence modifications are authorized for that initial spec task. The completed increment 5b commit/push authorization is fulfilled and does not carry forward.

## Copyable resume prompt

Read docs/assurance/handoff-5c.md in /home/enramosjr/Projects/agentic-assurance-7, explicitly using that cwd for every repository command. The delivered architecture profile is committed/pushed as 95c873d896e1ef53b89dcb75e6f6e1c1984c517e on claude/assurance-increment-7; read the leading delivery update in implementation-5b.md and preserve its evidence scopes. Start a fresh L2/Python spec-only lifecycle for a proposed exact profile for `python3 .ai/scripts/tests/test_lifecycle_conformance.py HarnessWiring`. Inspect actual imports, runtime boundaries and the three hook JSON reads; draft the spec and bring consequential decisions back before any plan or implementation. Both existing profiles and full-suite behavior stay unchanged. Static wiring only: no native/model qualification, session, trust grant, historical rescoring, product test execution, source change or delivery is authorized. No new worktree or knowledge bundle. Keep all docs/assurance artifacts ignored and uncommitted. Obtain spec approval, then plan approval, before coding.
