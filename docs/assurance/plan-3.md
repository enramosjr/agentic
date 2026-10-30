# Implementation Plan: governed architecture constraints

Draft for human review, 2026-10-28. L2; Python principal engineer.
Specification: `docs/assurance/specification-3.md`, approved by human:enramosjr. This plan awaits human approval and authorizes no implementation yet.

## Objective

Connect ordinary capability requirements to governing architecture decisions, validate and report those references, and demonstrate forbidden-dependency detection through existing assurance commands and evidence.

## Success criteria

- R1/R2: Optional governed declarations resolve using existing OKF document/bundle-relative conventions; invalid declarations receive actionable INVALID diagnostics without execution.
- R3: Text and schema-version-1 JSON expose declared governance for passing and nonpassing requirements; ungoverned output fields stay unchanged.
- R4/R5: Governance changes neither commands nor evidence scopes and retains mechanical, MANUAL and UNDECLARED outcomes.
- R6: Approved deltas preserve declarations/IDs; matching convergence executes once with exact existing scopes; existing touched-requirement enforcement composes with governed constraints.
- R7: The published stdlib fixture asserts a real dependency violation and its repair, with compatibility coverage.

## Current state

- `assurance.py:80`, `parse`, recognizes Verify, Inputs and Accept-risk, with early INVALID, MANUAL and UNDECLARED returns.
- `assurance.py:135`, `requirements`, supplies repository-relative capability filenames. `lifecycle.py:1229`, `cmd_converge`, calls the parser with a bundle-relative delta target such as `/capabilities/example.md`. Both need explicit root/document context.
- `assurance.py:309`, `result`, constructs status objects; `render` at line 461 produces text; `document` at line 487 preserves schema version 1.
- `assurance.py:328` matches command/effective inputs. `Obligation.evidence_globs` derives only from Inputs. `touched` at line 388 and `gate_problem` at line 427 already select and block the approved statuses.
- `brownfield.py:74`, `blocks`, retains indented requirement text; no production merge changes are expected.
- `okf.py:555`, `resolve_spec_path`, and `_check_links` at line 785 establish document/bundle-relative resolution and local-path decoding conventions; anchors are not validated.
- `test_assurance.py:29`, `Case`, supplies temporary adopter CLI fixtures. `test_assurance_gate.py:15`, `GateCase`, supplies gate setup and record assertions. Reuse fixture helpers without inheriting unrelated test suites.
- `assurance_demo.py:55`, `Session`, and `build` at line 89 provide a throwaway-repository runner and preparation callback.

## Proposed approach

Five source/test/document files are in scope:

1. Existing `.ai/scripts/assurance.py`.
2. Existing `.ai/scripts/lifecycle.py`, limited to the convergence parse call's context.
3. Existing `.ai/lifecycle.md`.
4. NEW `.ai/scripts/tests/test_assurance_architecture.py`.
5. NEW `.ai/scripts/assurance_architecture_demo.py`.

Continue in the existing isolated checkout `/home/enramosjr/Projects/agentic-assurance-7`, branch `claude/assurance-increment-7`; no new worktree or branch is needed. Intent is already recorded on that branch. Do not restart completed tasks.

### Parsing and reference resolution

Extend `Obligation` with optional governance metadata. Recognize Governed-by under the existing pre-scenario placement and duplicate rules. Preserve the raw value for invalid-value diagnostics.

Give `parse` explicit repository context via an optional keyword argument. Discovery passes its root; convergence passes its root and the target capability's document context, not the delta spec's location. Convert a bundle-relative capability target to its actual `knowledge/...` path before resolving document-relative links. Governed parsing without usable context fails closed; existing ungoverned parser calls remain compatible.

Validate exactly one complete Markdown link with nonempty label and target. Mirror existing OKF local-path decoding and document/bundle-relative conventions in a small assurance-local resolver; do not import the OKF command-line module, spawn its CLI, or introduce a general-purpose resolver subsystem. Reject external destinations, missing/non-Markdown files, directories and resolved paths outside the bundle, including escaping symlinks. Preserve the original reference including fragments; do not validate ADR status or fragment existence.

Attach governance once through a wrapper/common finalization path around existing obligation parsing. It must survive valid MANUAL/UNDECLARED outcomes and unrelated invalid Verify/Inputs declarations. Governance invalidity remains INVALID and names the declaration repair.

### Reporting contract

Only declaring requirements gain `governed_by` metadata. The object uses `basis: declared`, `reference` containing the original trimmed declaration value, and, only after successful resolution, `document` containing the normalized repository-relative document path without the fragment. INVALID declarations retain their supplied reference and existing diagnostic. Text adds a governance line explicitly labeled as declared provenance.

No change to status, basis, evidence, summary, exits or approval claims. No governance object or new output line for ungoverned requirements. No new persisted ledger format.

### Evidence and integration

Do not add ADR paths to argv, globs or evidence_globs. Explicit Inputs alone govern freshness. Do not alter ledger matching, touched selection, gate prerequisites, native enforcement, lease ownership or lifecycle stage rules. The convergence change supplies parser context; existing invalid-obligation exclusion must prevent req evidence for invalid governance. Test brownfield preservation before considering a production change there.

### Runnable fixture

Add `assurance_architecture_demo.py` using unchanged `assurance_demo.Session`, `build`, `_base` and failure handling. A preparation callback creates a fixture ADR, governed requirement and stdlib AST checker before the fixture's initial commit. The checker rejects an import of a designated adapter module from the constrained source. Inputs explicitly include the ADR, checker and constrained source.

Drive actual lifecycle commands and assert UNVERIFIED → explicit successful execution → VERIFIED → forbidden import edit → STALE → explicit failing execution → FAILED → repair and execution → VERIFIED. Check real command exits and JSON statuses. Clean up only the fixture; verify that the invoking source checkout is unchanged. The guide publishes the demo command and matching declaration/checker example.

## Boundaries and invariants

Standard library only; Python 3.9+. No special architecture namespace/type, mandatory ADR directory, approval schema, anchor validator, automatic execution, inferred inputs, new gate or waiver. Ungoverned public behavior and historical evidence remain unchanged. Working documents stay ignored/uncommitted; framework mode creates no knowledge bundle. Do not change old demo/measurement implementations, native guards or historical campaign artifacts.

## Implementation steps

### Step 1: governed declarations resolve consistently or become INVALID

Requirements R1/R2. Files: new test module, assurance.py and convergence parser context in lifecycle.py.

Write DeclarationTests and ReferenceTests first; record RED for the intended missing behavior, then implement and record GREEN. Cover ordinary capabilities, omission, duplicates, placement, empty/malformed links, missing/non-Markdown/directory targets, external references, decoded paths, both resolution conventions, fragments and escaping symlinks. Exercise discovery and delta-target context from a working directory unrelated to the fixture, proving no accidental cwd dependency.

Verification: the approved direct DeclarationTests and ReferenceTests commands; missing file/class must fail, not produce empty discovery success.

### Step 2: every status reports governance without changing its meaning

Requirements R3/R5. Files: new test module and assurance.py.

Write ReportTests first. Add metadata through the common result path and text rendering. Cover all statuses, valid governance beside an invalid existing Verify declaration, and malformed governance. Compare ungoverned text/JSON fields against existing behavior. Assert unchanged status/basis/summary/exits/evidence/approval and a command counter proving reports execute nothing.

Verification: approved ReportTests command and focused affected report cases after edits.

### Step 3: explicit Inputs control freshness and the checker detects a violation

Requirements R4/R5. Files: new test module and demo script.

Write FreshnessTests and ConstraintFlowTests first. Assert exact recorded argv/scopes. Editing an explicitly scoped ADR must produce STALE; omitting the ADR retains existing freshness behavior. Include a whole-tree case to document existing Markdown exemptions rather than inventing governance dependencies. Test MANUAL and UNDECLARED.

Build the runnable AST-checker fixture and drive the actual forbidden-import/status sequence. Confirm a disabled-checker mutation is present and makes the test fail on the expected missing detection.

Verification: approved FreshnessTests and ConstraintFlowTests commands. Final convergence later supplies the completed slice E2E; do not repeat unchanged checks solely for a new phase.

### Step 4: governed deltas compose with convergence and Verify

Requirements R2/R4/R6. Files: new test module; repair only earlier implementation seams if failures require it.

Write IntegrationTests first using existing adopter/gate/delta fixtures. Drive approved add/modify/converge/merge, preserving ID and exact declaration. Assert one acceptance execution, matching req evidence and unchanged input scope. Document-relative ADR links must resolve from the target capability in the delta path.

Assert invalid governed declarations publish no passing req evidence. Actual Verify attempts must record no Verify for selected INVALID, UNVERIFIED, STALE or FAILED constraints; repair and passing evidence permit Verify. MANUAL/UNDECLARED remain nonblocking. Do not change gate policy to obtain a pass.

Verification: approved IntegrationTests command with actual CLI exits, ledger contents and recorded-stage assertions.

### Step 5: publish the example and close compatibility coverage

Requirements R1/R2/R3/R4/R5/R6/R7. Files: lifecycle guide, new tests and new demo.

Write CompatibilityTests before completing documentation/fixture behavior. Document grammar, declared provenance, exact report metadata, ADR inclusion in Inputs, statuses/gate behavior and limits. Run the published command through CompatibilityTests, asserting its real sequence, failure detection, cleanup and invoking-checkout immutability. Assert documented declarations agree with the runnable fixture and ungoverned behavior is unchanged.

Verification: final convergence executes all seven approved acceptance classes once, including connected-flow and documented-example E2Es.

### Step 6: review and verify the frozen candidate

Requirements R1/R2/R3/R4/R5/R6/R7. Save ignored implementation evidence. Run current acceptance convergence after edits/sync, then obtain independent two-pass review: spec compliance followed by quality/completeness. Retain the whole returned report and record Review only after Approved. Fix findings through focused checks and reuse unaffected evidence.

Close the retrospective before Verify. Freeze edits after review repairs; run the full framework gate once for that candidate, with one validation owner/background job. If a current-base refresh is required by the delivery workflow, complete it before the expensive gate, within the user's authorized Git scope. No delivery or source integration is authorized by this draft. Finish current convergence/audit/scan/diff evidence and framework-aware synchronization, then record Verify only when requirements are met.

## Testing strategy

Implement exactly the seven named classes from the approved spec in the new module, supporting direct unittest.main execution. Use real temporary Git/adopter CLI fixtures for statuses, path resolution, deltas and stage recording; table-driven unit cases cover pure parsing.

Confirmed negative controls target silent failures: disabled containment, lost governance on an early-return status, implicit ADR input insertion, disabled constraint checker, and invalid delta publishing passing req evidence. Confirm changed bytes before counting a killed mutation; reject unapplied/equivalent variants. Keep controls proportional rather than replaying earlier campaigns.

Fixture-created source files must exist and detect the claimed forbidden dependency. Space separate historical task records across the known second-precision boundary where needed; do not fix unrelated timestamp behavior.

## Validation commands

During development use each exact acceptance command from the approved specification, wrapped with lifecycle redgreen for intended new-logic failures and passing implementations. Focus repairs on affected classes.

Trace and final acceptance:

- `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-3.md`
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-3.md --plan docs/assurance/plan-3.md --tests .ai/scripts/tests/test_assurance_architecture.py`
- `python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-3.md`

Convergence runs the seven direct commands and supplies both connected E2Es. Do not separately repeat the entire module or demo afterward on identical inputs.

Full framework gate once per frozen candidate:

`python3 .ai/scripts/lifecycle.py run assurance-3-framework -- python3 .ai/scripts/run_tests.py -j 8`

Final ledger checks:

- `python3 .ai/scripts/lifecycle.py run assurance-3-diff -- git diff --check`
- `python3 .ai/scripts/lifecycle.py run assurance-3-scan -- python3 .ai/scripts/lifecycle.py scan-diff`
- `python3 .ai/scripts/lifecycle.py run assurance-3-audit -- python3 .ai/scripts/lifecycle.py audit`

Before repeating recorded checks, run lifecycle.py reuse and honor REUSE. Load applicable validation-policy sections before Gate 4 or long execution. The full framework suite includes scripted lifecycle checks required for script/guide edits.

No tier/stage or native enforcement rule changes are planned, so no fresh native/model campaign is proposed or authorized. If implementation requires such a rule change, stop and surface its scope and verification implications; do not invent an exemption or launch another campaign.

## OKF impact

Framework mode has no bundle; planning-time affected reports no bundle. This is INAPPLICABLE, not PASS. Do not initialize knowledge/. Update the existing lifecycle guide and keep spec/plan/review/evidence under ignored docs/assurance; lifecycle receipts stay in Git scratch. Before completion run required framework-aware checks, report actual outcomes and close the retrospective.

## Risks and mitigations

- Wrong reference base in convergence: test normal discovery and delta-target context separately.
- Lost metadata on early returns: attach once and cover all statuses.
- Silent scope expansion: assert exact ledger scope and omitted-ADR behavior.
- Path/symlink escape: check resolved containment before accepting the reference.
- Ineffective demo: assert actual forbidden import failure and kill a confirmed disabled-checker variant.
- Scope expansion into stage rules: stop and disclose rather than change native evaluation obligations silently.

## Out of scope

Increment 5/adapters, dependency inference, ADR approval/status governance, anchor validation, extra checker packages, automatic constraint extraction, historical evidence rescoring, native/model allocations, trust grants, commits, pushes, PRs, merges and additional worktrees.

## Open decisions

None. The plan is ready for human review and approval before implementation. All D1–D3 behavior decisions follow the approved specification.
