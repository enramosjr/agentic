# Spec: Requirement assurance status (increment 1)

Version: **0.1.0-draft**, 2026-10-27. Framework base: `5f81468`. Tier: L2, kind feature.
Context: [assessment](assessment.md), [architecture](architecture.md) §3 and §6.

## Problem and outcome

AGENTIC binds execution evidence to exact inputs, but only inside the task that ran
it. After a task ships, nothing answers whether a capability requirement is still
verified at the current revision, or which earlier verification a later change
invalidated. Delta merges also drop the acceptance command, so living requirements
carry no verification obligation.

When this ships, a capability requirement can declare how it is verified and which
files that verification depends on. `lifecycle.py assure` reports, for every
requirement, whether current mechanical evidence supports it, and names the changed
files when earlier evidence no longer applies. `assure --changed` lists what must be
reverified for a diff. The increment is report-only and changes no existing gate.

## Users and scenarios

- An agent finishing an L2 task checks that it did not stale another requirement.
- A maintainer or CI job asks which requirements are verified at HEAD.
- A second agent changes a shared file; the first agent's earlier evidence becomes STALE.
- An adopter with existing prose or structured capabilities upgrades and sees no new failures.

## Requirements

- R1: A structured capability requirement block MUST accept, before its first scenario, at most one indented `- Verify:` line holding either one backticked command or `manual` followed by a reason, and at most one indented `- Inputs:` line holding one or more backticked repo-relative globs; a duplicate line, a line after a scenario, `Inputs:` without `Verify:`, an empty command, or an absolute or `..` glob MUST yield status INVALID for that requirement.
- R2: Requirements without a `Verify:` line MUST report UNDECLARED, and existing `okf.py validate`, `lifecycle.py analyze`, `lifecycle.py merge` and every existing framework test MUST keep their current outcomes.
- R3: `lifecycle.py assure --run [ID ...]` MUST execute each selected non-manual obligation through the same execution path as `lifecycle.py run`, recording one ledger entry per requirement labeled `req:<ID>` with the declared inputs, and MUST refuse with nothing run when no lifecycle task is active or when invoked inside `lifecycle.py run`.
- R4: `lifecycle.py assure` MUST evaluate each declared obligation from the newest `req:<ID>` ledger entry, across committed lifecycle records and the active task, whose command and inputs equal the current obligation, reporting VERIFIED when that entry passed and the existing ledger freshness rules hold, STALE with the changed file names or environment reason when they do not, FAILED when it exited nonzero, and UNVERIFIED when no such entry exists.
- R5: A lifecycle record that is not valid JSON or fails the existing ledger schema audit MUST contribute no evidence and MUST be named in the report diagnostics; no VERIFIED status may derive from it.
- R6: An obligation without `Inputs:` MUST be treated as depending on the whole tree, so its evidence is VERIFIED only for an identical working tree and STALE after any commit or edit.
- R7: `lifecycle.py assure --changed --base REV` MUST list, without running any command, each declared obligation whose inputs match a file changed between REV and the working tree, plus every obligation without `Inputs:`, each with the reason it is listed.
- R8: The report MUST print one line per requirement with its status, ID, capability, evidence head and timestamp when present, and reason, and `--json` MUST emit `schema_version` 1 with the same fields plus the evidence basis (`mechanical` for ledger evidence, `declared` for MANUAL, `none` otherwise); neither form may print stored command output.
- R9: `assure` and `assure --changed` MUST exit 0 when no requirement is STALE, FAILED, UNVERIFIED or INVALID (UNDECLARED also counts with `--strict`), 1 otherwise, and 2 for refused input, and MUST NOT write any file or alter lifecycle state; MANUAL requirements MUST be listed without affecting the exit code.
- R10: `.ai/lifecycle.md` MUST document the obligation syntax, the statuses, `assure`, `--run`, `--changed` and `--strict`, and state that a VERIFIED status covers only that command on those inputs.

## Acceptance

- R1: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py -k ObligationSyntaxTests` passes, covering each malformed form and a valid command and manual form.
- R2: `python3 .ai/scripts/run_tests.py` passes, and `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py -k CompatibilityTests` passes against prose and obligation-free structured capabilities.
- R3: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py -k AssureRunTests` passes, asserting the `req:` label, declared inputs, per-file hashes, and refusal without an active task or under `lifecycle.py run`.
- R4: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py -k StatusTests` passes, covering an input edit (STALE naming the file), an unrelated edit (VERIFIED), a deleted input, a changed obligation command (UNVERIFIED), a newer failure after an older pass (FAILED), and evidence from an earlier committed record.
- R5: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py -k IntegrityTests` passes, using a record with invalid JSON and a record carrying an output key, both reported and neither yielding VERIFIED.
- R6: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py -k UnscopedTests` passes, asserting VERIFIED on the identical tree and STALE after a commit.
- R7: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py -k ChangedTests` passes, asserting matched, unmatched and unscoped obligations and that no ledger entry is added.
- R8: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py -k ReportFormatTests` passes, asserting the text fields, the JSON schema and basis values, and the absence of command output.
- R9: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py -k ExitCodeTests` passes, asserting each exit code, `--strict`, MANUAL handling, and an unchanged tree and state file after a report.
- R10: `python3 -m unittest discover -s .ai/scripts/tests -p test_lifecycle_conformance.py -k Assurance` passes, asserting the documented terms appear in `.ai/lifecycle.md`.

Each new test class is shown to fail against a deliberately broken variant before
it is accepted (`AGENTS.md` §8.6).

## Constraints

- Standard library only, Python 3.9+, matching `lifecycle.py`.
- Reuse `ledger.py` freshness (`_entry_verdict`, `inputs_snapshot`, `context_digest`);
  no second ledger, store, daemon or service.
- No hook, stage, tier or gate behavior changes in this increment.
- Obligation lines precede scenarios, so `Scenarios: replace` and modification
  semantics in `brownfield.py` stay unchanged.
- Framework source reads records from Git scratch, as `record_path` does.

## Non-goals

- Gating `stage verify` on assurance status (increment 2).
- Architecture constraint rules, attested review evidence, risk acceptance, input
  adapters, LLM gap review, dashboards (increments 3–6).
- Carrying `R<n>` IDs of whole-feature specs across tasks; they are not stable.
- Seeing evidence on unmerged branches or other worktrees.
- Paid or long evaluation runs.

## Assumptions

- Replaces "where do obligations live?": inside capability blocks, not a separate
  file, so deltas, hashing and review already cover them.
- Replaces "should a pass under different inputs count?": no; evidence counts only
  when command and declared inputs equal the current obligation.
- Replaces "which record is newest?": entry timestamp `at`, then record file name.
- Replaces "should UNDECLARED fail?": not by default, to keep existing adopters green.

## Open questions

None. The spec is ready for planning.
