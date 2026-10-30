# Plan: Requirement assurance status (increment 1)

Spec: [specification.md](specification.md) (approved 2026-10-27). Tier L2, feature.
Persona: Python (`.ai/personas/python-principal-engineer.md`): subprocess timeouts and
`shell=False`, validation at the record-file trust boundary, Python 3.9 compatibility.

## Design decisions

- New stdlib module `.ai/scripts/assurance.py` holds parsing, evidence selection,
  evaluation and rendering. It imports `ledger` and `brownfield` (for the same
  capability block parser merge uses) and never imports `lifecycle`. `lifecycle.py`
  passes it the root, records directory, active state and current tree hash.
- Records directory follows `record_path`: Git scratch for framework source,
  `knowledge/history/lifecycle/` otherwise. The active task's state replaces its own
  committed record when both exist.
- Evidence globs are the declared `Inputs:` plus `!knowledge/history/lifecycle/**`,
  because recording evidence must not stale it. Equality checks compare against that form.
- Freshness uses `ledger._entry_verdict` unchanged in logic. `req:` entries store
  `input_files` (per-file hashes) and a new optional `runtime_sha256` (resolved
  executable plus its content hash). The full environment digest is not used:
  it differs across shell sessions, so no cross-task evidence would survive.
- An entry whose commit is no longer resolvable (for example after a squash merge)
  is STALE. This is conservative and documented as a limit.
- `--run` refusal follows other lifecycle mutations (exit 1, nothing run);
  report forms use exit 2 for refused input.

## Steps

1. **Tests first** (R1–R9): add `.ai/scripts/tests/test_assurance.py` with classes
   `ObligationSyntaxTests` (R1), `CompatibilityTests` (R2), `AssureRunTests` (R3),
   `StatusTests` (R4), `IntegrityTests` (R5), `UnscopedTests` (R6), `ChangedTests` (R7),
   `ReportFormatTests` (R8), `ExitCodeTests` (R9). Fixtures copy the scripts into a
   temporary Git repository with an OKF bundle and a structured capability, as
   `test_brownfield_deltas.py` does. Record red with `lifecycle.py redgreen red`.
   Check: the suite fails because `assure` does not exist.
2. **Ledger extension** (R4): `ledger.runtime_digest(argv)`, `runtime_sha256` in
   `OPTIONAL_KEYS`, and a STALE reason in `_entry_verdict` when it differs.
   Check: `test_ledger.py` still passes; `StatusTests` runtime case passes.
3. **Obligation parsing** (R1, R2): `assurance.obligations(block)` returns command,
   manual reason, globs or an INVALID reason; `assurance.requirements(bundle)` walks
   structured capabilities (frontmatter `namespace`), skipping prose ones, and
   reports unparseable capabilities as diagnostics with exit 1.
   Check: `ObligationSyntaxTests`, `CompatibilityTests`.
4. **Evidence and evaluation** (R4, R5, R6): `assurance.evidence(records_dir, state)`
   loads records, drops and names invalid JSON or `ledger.audit` failures, and indexes
   `req:` entries; `assurance.evaluate(...)` picks the newest matching entry by `at`,
   record name and index, and maps verdicts to VERIFIED, STALE, FAILED, UNVERIFIED.
   Check: `StatusTests`, `IntegrityTests`, `UnscopedTests`.
5. **Changed set** (R7): `assurance.changed(root, base, requirements)` uses
   `git diff --name-only BASE` plus untracked files and the same include/exclude glob
   semantics as `ledger.input_paths`; unscoped obligations are always listed.
   Check: `ChangedTests`.
6. **Rendering and exits** (R8, R9): one text line per requirement, `--json` with
   `schema_version: 1` and `basis`, diagnostics section, exit mapping and `--strict`.
   Check: `ReportFormatTests`, `ExitCodeTests`.
7. **CLI wiring** (R3, R9): extract the execution core of `cmd_run` into one helper
   used by `run` and `assure --run`; add `cmd_assure` and its parser; treat `assure`
   as a mutation only with `--run`, and run it outside the state lock like `run`.
   Check: `AssureRunTests`; existing `test_lifecycle.py` and `test_ledger.py` pass.
8. **Documentation** (R10): add an "Assurance status" section to `.ai/lifecycle.md`
   (syntax, statuses, commands, scope of VERIFIED, unscoped rule, squash-merge limit)
   and a conformance test `Assurance` in `test_lifecycle_conformance.py`.
   Check: that test passes.
9. **Verify**: show each new test class fails against a deliberately broken variant;
   `lifecycle.py converge docs/assurance/specification.md`; full suite
   `python3 .ai/scripts/run_tests.py` through `lifecycle.py run`; independent review.

## Requirement map

| Requirement | Steps | Check |
|---|---|---|
| R1 | 1, 3 | `ObligationSyntaxTests` |
| R2 | 1, 3, 9 | `CompatibilityTests`, full suite |
| R3 | 1, 7 | `AssureRunTests` |
| R4 | 1, 2, 4 | `StatusTests` |
| R5 | 1, 4 | `IntegrityTests` |
| R6 | 1, 4 | `UnscopedTests` |
| R7 | 1, 5 | `ChangedTests` |
| R8 | 1, 6 | `ReportFormatTests` |
| R9 | 1, 6, 7 | `ExitCodeTests` |
| R10 | 8 | conformance `Assurance` |
