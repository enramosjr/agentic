# Implementation Plan: increment 5 — Python validation input profiles

Status: draft for human approval, 2026-10-28 America/Chicago. Coding and product verification await approval of this plan.

Basis: approved [specification-5.md](specification-5.md), R1–R7 and D1–D5. L2 feature; Python principal engineer and planner role. All repository work stays in `/home/enramosjr/Projects/agentic-assurance-7`, branch `claude/assurance-increment-7`, starting HEAD `5a0ee96136997772e89e978001441dfd7f1261aa`. Working artifacts remain ignored and uncommitted. Intent is recorded with the user's explicit approval; Plan is not yet recorded.

## Objective

Add a standalone, read-only exporter that supplies reusable explicit input scopes for focused framework Python checks. Start with one inspected runner-test profile. Preserve the full suite's broad coverage, existing automatic inference, evidence formats and gates.

## Success criteria

| Requirement | Observable result |
| --- | --- |
| R1 | Exporting runs no target code, imports no test/target dependency modules and changes no repository or lifecycle files. |
| R2 | Only exact registered argv from the registered root matches a validated declared profile. |
| R3 | The pilot covers the selected test, temporary-directory helper, scratch helper and subprocess runner. |
| R4 | Unsupported commands and invalid catalog/paths/supplements refuse with diagnostics and no usable candidate. |
| R5 | Text and JSON expose identical ordered scope, rationale and limitations; output is usable as lifecycle argv and assurance syntax. |
| R6 | Full-suite coverage, automatic inference, assurance evidence identity/status/schemas, receipt exclusions and gates remain unchanged. |
| R7 | Real local framework and adopter fixtures prove focused execution, reuse and invalidation, with nonzero test-count proof and independent expected reads. |

## Current state

- `.ai/scripts/ledger.py:32-48,73-91`: ordered repo-relative glob matching and Git input inventory. Its basic glob validator does not cover every representation/containment boundary needed by this exporter.
- `.ai/scripts/ledger.py:55-70`: unittest and the parallel runner already have broad inferred inputs. No default changes are needed.
- `.ai/scripts/lifecycle.py:994-1008`: explicit `--inputs` bypasses automatic inference.
- `.ai/scripts/lifecycle.py:1048-1052`: successful target output is suppressed; the lifecycle summary cannot prove a unittest count.
- `.ai/scripts/ledger.py:223-267`: explicit-input reuse requires a resolvable recorded commit and current input digests.
- `.ai/scripts/assurance.py:367-393`: evidence matches exact argv and ordered input scope before freshness evaluation.
- `.ai/scripts/tests/test_run_tests.py:9,25-32`: imports disk_tmp and invokes run_tests.py by path, without a unittest main entry point.
- `.ai/scripts/tests/disk_tmp.py:10-20`: imports scratch and may change temp storage on import. The exporter must import neither.
- `.ai/scripts/tests/test_assurance.py:29-43`: established ordinary adopter fixture pattern, copying framework scripts before `okf.py init`.
- `.ai/scripts/tests/test_project_context.py:23-31,43-50`: framework identity via `.agentic.json`, with lifecycle records outside an adopter bundle.
- `.ai/scripts/install.py:21-28,43-61`: installation includes the `.ai/` tree; new script packaging requires no installer change.
- Framework mode has no knowledge bundle. The planner's `okf.py affected` over the three planned paths reports no bundle: INAPPLICABLE, not PASS; do not initialize one.

No product tests, import probes or native/model evaluations were run during planning.

## Proposed approach

### Files and ownership

One implementer owns this coherent slice; no parallel source edits are needed.

| File | Planned change |
| --- | --- |
| `.ai/scripts/assurance_inputs.py` | New: literal pilot catalog, validation, exact matching, rendering and CLI. |
| `.ai/scripts/tests/test_assurance_inputs.py` | New: seven acceptance classes, isolated fixture builders and bounded controls. |
| `.ai/lifecycle.md` | Existing: short input-profile usage/limits subsection and exporter example near the assurance documentation. |

Ignored artifacts under docs/assurance hold the plan, implementation notes, review, convergence output and control evidence. They are not shipped. No existing producer, ledger, runner, pilot test/helper, installer, hook, tier/stage rule or evaluation tool is changed.

### Catalog and matching

Use literal declarative `PROFILES` data inside the new exporter. No external catalog file, configuration loader, runtime profile override, executable profile callback or plugin mechanism.

The single initial profile contains:

- ID `python-runner-test` and working directory equal to repository root.
- Exact argv `["python3", "-m", "unittest", "discover", "-s", ".ai/scripts/tests", "-p", "test_run_tests.py"]`.
- Ordered inputs: `.ai/scripts/tests/test_run_tests.py`, `.ai/scripts/tests/disk_tmp.py`, `.ai/scripts/scratch.py`, `.ai/scripts/run_tests.py`.
- Per-input rationale: selected test, imported helper, transitive helper and subprocess script. Explicit runtime limitations accompany it.

Keep data separate from validation/rendering functions. Pure functions accept a catalog value for deterministic tests; the public CLI uses only built-in data. Do not mutate shared catalog objects or use mutable default arguments.

Validate required fields/types, nonempty strings/lists, unique IDs, unique argv/root matches and rationale coverage. A malformed catalog refuses as a whole rather than silently selecting another entry. Profiles express declared scope, not approval authority.

Anchor the expected root at `Path(__file__).resolve().parents[2]`, require the current directory to resolve to that root and verify it is the Git worktree root. Never change cwd, resolve a different checkout or normalize argv. Different interpreter argv, reordered flags or added options do not match; no alternate spellings are registered in this increment.

### Input validation

Set `sys.dont_write_bytecode` before importing local helpers. Reuse ledger's glob validation/matching and supported inventory; importing ledger does not import the pilot's target dependencies. Do not import scratch, the runner, tests, lifecycle or assurance in the exporter.

Exporter-specific checks cover:

- Declaration-unrepresentable values, including backticks/control characters, empty values and invalid types.
- Absolute paths and parent traversal, including the path part of catalog exclusion patterns.
- Positive-only supplements, appended after catalog inputs without reordering/normalizing the scope.
- Missing required literal profile files and required files absent from the Git-supported inventory.
- Symlink-resolved containment, including any existing literal prefix of a wildcard pattern and each selected inventory path; escaping the root refuses.
- Existing submodule inventory refusal.
- Malformed or unsupported boundaries; no guessed partial candidate.

Treat a profile's required literal filenames containing glob metacharacters as ambiguous rather than escaping them into another scope. Ordinary explicit wildcard globs remain globs, not claims of literal identity. Preserve spaces as values. No shell quoting or executable shell strings.

Read-only Git inspection is permitted; target execution, test discovery/imports, scratch initialization, catalog updates and evidence writes are not part of export. Keep ambient runtime, temp/mount and ignored/external-data limitations explicit. Known unresolved application-data dependencies do not become unrelated by omission.

Do not append the catalog definition to the pilot target's scope: the target does not read it. Changing the exported declaration is an explicit adoption event handled by existing evidence matching.

### CLI and output

Interface: `python3 .ai/scripts/assurance_inputs.py [--json] [--extra-input GLOB]... -- COMMAND...`.

Require the separator and a nonempty command. Exit 0 for a suggestion, 2 for refusal. Argument/catalog/path failures are rendered consistently; when JSON is requested, emit one structured refusal without partial candidate fields. Standard help remains help, not a scope suggestion.

The new exporter's JSON uses its own `schema_version: 1`; assurance JSON is unchanged.

- Success fields: `ok: true`, `profile_id`, `argv`, `inputs`, `inputs_line`, `lifecycle_inputs_argv`, `rationale`, `limitations`, `review_required: true`.
- Refusal fields: `ok: false`, `reason`, `remediation`, with no candidate inputs, declaration or lifecycle-input array.
- `lifecycle_inputs_argv` is `["--inputs", ...ordered_globs]`; the caller places these tokens before the target command separator.
- `inputs_line` is one existing-syntax indented `- Inputs:` declaration, preserving the same ordered values.

Text exposes the same values and renders lifecycle tokens as a JSON array instead of an executable shell string. Limits identify declared review-required repository scope, with no claim of VERIFIED, complete reads, runtime portability or approval. Refusal recommends retaining the current scope; omitted Inputs is not equated with explicit `**`.

## Boundaries and invariants

Export never imports or runs the supplied target. No automatic adoption, inference change, test selection, gate, evidence migration or native trust operation. Full runner and unrestricted discovery requests remain unsupported narrowing requests regardless of concurrency.

Only four initial pilot inputs are registered. More mappings require separate reviewed changes. The catalog/renderer is upstream of explicit adoption; existing evidence producers/readers remain unchanged.

Fixture writes and ordinary fixture commits are confined to temporary repositories. Reuse the existing checkout and branch; create no worktree or source commit. Preserve historical evidence at its original scope. No automatic fetch, base merge or other delivery mutation is part of this authorized plan; candidate checks name the actual starting/current revision instead of claiming unperformed base refresh.

## Implementation steps

### Step 1: Acceptance fails closed before exporter implementation

Requirements: R1–R7. File: new test_assurance_inputs.py.

Write `ReadOnlyTests`, `ProfileTests`, `DependencyCoverageTests`, `RefusalTests`, `OutputTests`, `CompatibilityTests` and `EndToEndTests` first. Use a handwritten four-file oracle independent of production catalog data. CLI helpers use explicit cwd/env and timeouts; no global cwd-changing fixture base.

The new test file must have a unittest main entry point and requested missing classes must fail. No skipped fallback or empty discovery can count as success.

Check: record RED using the grouped seven-class command below. Inspect failures to establish that intended tests ran and failed for absent exporter behavior, not a broken test loader or unrelated environment error.

### Step 2: Exact-command suggestions validate and render without executing

Requirements: R1–R5. Files: new exporter and tests.

Implement literal catalog, pure validators, exact root/argv match, structured result, text/JSON rendering and CLI. Validate before emitting candidate fields. Use sentinels and before/after inventories to prove no target import/execution, bytecode or evidence writes. Malformed in-memory catalog values exercise validators without a public override.

Tests first: ReadOnlyTests, ProfileTests, DependencyCoverageTests, RefusalTests and OutputTests from Step 1. Check: focused named classes prove exact scope, refusal behavior, parser-compatible declaration and equal ordered text/JSON outputs. Do not modify core inference to make tests pass.

### Step 3: Real focused checks support reuse and assurance freshness

Requirements: R3, R6, R7. File: fixture builders and cases in the new test module.

Build two disk-backed Git repositories with the actual framework scripts and only the pilot test plus disk_tmp under the test directory:

1. Framework fixture: `.agentic.json` declares `repository_kind: framework`; baseline commit and ordinary L1 fixture lifecycle; never initialize knowledge.
2. Adopter fixture: ordinary bundle initialized using existing assurance patterns; a temporary capability uses the exact pilot Verify argv and the public exporter's Inputs line.

Sanitize inherited invocation-root variables as existing fixture helpers do and use ordinary bytecode/temp settings and disk-backed scratch. No native registration or trust grant.

Nonzero execution proof: preflight the exact pilot directly once, capture unittest output and require at least one real test. Freeze/hash all four inputs and relevant execution settings across the subsequent lifecycle run. Then execute the unchanged target through public `lifecycle.py run --inputs` using the exported token array. These two tiny executions cover distinct assertions: nonempty real discovery and lifecycle evidence production. Never infer a test count from lifecycle's output-suppressed success summary or change the producer to expose one.

Framework assertions:

- Evidence records exact argv/exported inputs and exit 0.
- A handwritten-oracle unrelated edit, such as copied assurance.py, leaves `reuse` at REUSE.
- Change each of the four inputs individually with a harmless comment; `reuse` must report RERUN.
- Restore each before the next case and reuse the original passing entry; do not execute the check four more times.
- No framework knowledge bundle appears; the invoking checkout is unchanged.

Adopter assertions:

- Explicit `assure --run` produces VERIFIED.
- Known unrelated edit retains VERIFIED; declared input edit produces STALE.
- Changing to an unmatched declaration produces UNVERIFIED without a new matching run.
- Existing receipt exclusion appears in evidence, not as a new implicit exporter input.

Tests first: CompatibilityTests and EndToEndTests from Step 1. Check: R7's public-CLI acceptance asserts every required state against the independent oracle. Fixture preflight hashes/settings must match the recorded execution's inputs; runtime portability is not inferred.

### Step 4: Usage and bounded controls expose silent failures

Requirements: R1–R7, especially R3–R6. Files: exporter/tests and existing lifecycle guide; ignored evidence artifacts.

Add a short guide subsection with the exact pilot, structured output, explicit adoption, profile maintenance, full-suite refusal and runtime limits. Do not change normative stage/tier rules. Include the usage/contract assertions in CompatibilityTests; parser validation already belongs in OutputTests.

Confirm isolated mutated source bytes before running each bounded control:

1. Remove the subprocess runner input and its rationale, leaving a structurally valid catalog.
2. Remove a helper input and rationale.
3. Keep profile-matched paths but remove/rename the selected test class or method, producing zero discovery.
4. Relax exact matching to accept a different selection.

Relevant acceptance must reject each variant. Zero discovery must fail count validation rather than earn a PASS. Record operator/source hashes, target command, actual exit and killed/equivalent status. An unapplied mutation is not evidence. Keep operators/results ignored, with no native/model or trust operations.

Check: targeted controls plus requirement-to-plan/test trace; no repeat of an unchanged E2E merely to write its report.

### Step 5: Review and verify the frozen slice

Requirements: R1–R7. Files: the three-file slice and ignored evidence reports.

After focused checks pass, complete impact/guide synchronization and the RED/GREEN pair. Close the retrospective with evidence-backed lessons or an honest no-new-lessons reason. Run requirement convergence, then obtain an independent two-pass reviewer verdict against the approved spec/plan and completeness rules; preserve findings and repair evidence. Reuse unchanged receipts; rerun changed requirements after repairs.

Freeze the repaired source, run the full framework gate once, finish diff/scan/trace/audit evidence and record Review/Verify only when their prerequisites pass. No earlier increment's native evidence or historical claims are rescored. Source delivery remains outside scope; stop at a verified uncommitted candidate unless separately authorized.

Check: seven passing requirement receipts, Approved independent review, passing full framework gate, closed retrospective and current audit. Record exact commands/outcomes, not assumed results.

## Testing strategy

Use stdlib unittest, public subprocess interfaces for CLI behavior and deterministic catalog values for pure validation. Cover exact command/root/interpreter differences; missing/deleted/ignored required files; escaping symlinks; submodules; duplicate IDs/argv matches; malformed rationale; unsafe globs; spaces and declaration encoding; positive supplement order; full-suite concurrency variants; read-only success/refusal; and a synthetic catalog's declared Markdown/configuration input without `.py` filtering.

R7 supplies the two connected CLI flows. Confirmed controls cover missing dependencies, vacuous discovery and permissive matching. No general mutation campaign, runtime tracer or real-agent evaluation is added.

## Validation commands

Except for the planning checks recorded at the end, these are FUTURE implementation commands, not executed results. Run from the existing checkout. No existing formatter/type-checker/package tool is introduced; retain repository conventions.

### Test-first grouped command

Use the same target after `lifecycle.py redgreen red --` and `lifecycle.py redgreen green --`:

```text
python3 .ai/scripts/tests/test_assurance_inputs.py ReadOnlyTests ProfileTests DependencyCoverageTests RefusalTests OutputTests CompatibilityTests EndToEndTests
```

During repairs, invoke only the affected named class. Before repeating a recorded check, run reuse; a REUSE verdict is reused rather than rerun.

### Requirement receipts and trace

```text
python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5.md --plan docs/assurance/plan-5.md --tests .ai/scripts/tests/test_assurance_inputs.py
python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-5.md
```

Convergence executes the seven approved acceptance commands. EndToEndTests is the narrow connected slice; no separate unchanged E2E rerun is needed for another report.

### Frozen-candidate full framework gate

```text
python3 .ai/scripts/lifecycle.py run inputs-5-framework -- python3 .ai/scripts/run_tests.py -j 8
```

Run once after repairs/review on frozen source; new scripts and guide affect the framework suite, so old full-suite PASS evidence does not cover this candidate. Preserve logs under ignored artifacts or Git scratch. The suite provides existing installer/conformance/evidence regression coverage. Tier/stage rules are unchanged, so no real-agent lifecycle evaluation is required. Follow long-check supervision policy with a background job instead of short model polling.

### Final checks and stage closeout

```text
python3 .ai/scripts/lifecycle.py run inputs-5-diff -- git diff --check
python3 .ai/scripts/lifecycle.py run inputs-5-scan -- python3 .ai/scripts/lifecycle.py scan-diff
python3 .ai/scripts/lifecycle.py audit
```

Use `lifecycle.py reuse LABEL_OR_CMD` before repeating any recorded check and retain command-scoped failures. Source changes after the frozen gate require affected-evidence reevaluation. Record the independent review and formal Verify at their proper gates; do not record Ship or perform source delivery without authorization.

## OKF impact

Framework mode has no knowledge bundle. `okf.py affected .ai/scripts/assurance_inputs.py .ai/scripts/tests/test_assurance_inputs.py .ai/lifecycle.md` reports no bundle, which is inapplicable rather than a PASS. Do not initialize one or create a knowledge log. Synchronize the existing lifecycle guide and keep all working reports ignored. Framework lifecycle audit/Verify provides the applicable record handling; do not invent an adopter `okf.py records` PASS.

## Risks and mitigations

- Profile maintenance can miss new reads: explicit rationale and normal input-completeness review; no automatic-completeness claim.
- Zero-test invocation can exit successfully: real count preflight, unchanged inputs/settings and confirmed empty-discovery control.
- Imports can write files: no target/helper imports, bytecode disabled before local helper import, before/after snapshots.
- Path/glob semantics can widen or omit reads: reuse ordered matching and refuse unsafe representation/containment.
- Runtime/temp/mount state exceeds repository inputs: report that boundary and preserve existing evidence semantics.
- Fixtures can pollute the checkout: explicit roots/env, isolated writes, no global cwd-changing base and immutability assertions.

## Out of scope

Additional profiles/language adapters; automatic import-graph inference; test selection; automatic adoption; changes to inference/ledger/gates/runner; real-adopter completeness or project-wide speed claims; historical evidence modification; native/model evaluation/trust grants; new worktrees; commit, push, PR, merge or other delivery actions.

## Open decisions

None. Implementation mechanics fit the approved specification. The plan is ready for human approval; coding waits for that approval.

## Planning checks

`lifecycle.py analyze docs/assurance/specification-5.md` exited 0. `lifecycle.py trace docs/assurance/specification-5.md` exited 0 with seven requirements. Intent was recorded with human:enramosjr from the user's explicit approval, and `lifecycle.py audit` exited 0.

`lifecycle.py trace docs/assurance/specification-5.md --plan docs/assurance/plan-5.md` exited 0: all seven requirements traced to this plan. `lifecycle.py status` shows Intent complete and Plan/Review/Verify pending. `git status --short --branch` shows no tracked source changes; git check-ignore confirms the spec, plan and investigation are ignored. No product verification is claimed. Plan remains unapproved and its stage has not been recorded.
