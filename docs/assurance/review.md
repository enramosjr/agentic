# Review: Requirement assurance status (increment 1)

Reviewer: `reviewer` subagent, independent of the implementation. Report saved verbatim by the implementing session because the reviewer had no file-write tool.

## Verdict

Approved. No Critical, High or Medium issues; two Low findings and one note.

## Validation Reviewed

Ran by the reviewer:
- `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py` passed, 28 tests.
- `python3 -m unittest discover -s .ai/scripts/tests -p test_lifecycle_conformance.py -k Assurance` passed.
- Three manual invocations: `assure --run NOPE` refused with exit 1; `assure --changed --base nonsense` refused with exit 2; `assure --run --changed` runs and silently ignores `--changed`.
- `okf.py affected` could not run: framework source has no `knowledge/`, which is expected.

Read but not rerun: the full suite (`run_tests.py`, exit 0), converge (10 PASS) and the redgreen record, as reported by the implementer. The reviewer did not check that each new test class fails against a deliberately broken variant (spec §8.6 line).

## Spec compliance (R1–R10)

- R1: `parse` in `assurance.py` covers each malformed form: duplicate line, line after a scenario, `Inputs:` without `Verify:`, empty command, bad glob via `ledger.check_globs`.
- R2: prose and obligation-free capabilities report UNDECLARED or nothing.
- R3: `assure --run` uses the shared `execute_check`, label `req:<ID>`, declared inputs and per-file hashes; refuses without an active task and under `lifecycle.py run`.
- R4, R6: evaluation reuses `ledger._entry_verdict`, matches on argv and inputs, orders by `at`, record, index; no `Inputs:` falls back to the tree comparison.
- R5: invalid JSON and `ledger.audit` failures contribute no evidence and are named in diagnostics.
- R7: `changed` runs no command and uses the ledger's include/exclude order.
- R8, R9: text and JSON fields present; the report path takes no state lock and writes nothing, asserted by a test.
- R10: documented in `.ai/lifecycle.md`, guarded by a conformance test.
- Constraints: standard library only, no second store, no gate changes, `cmd_run` behavior preserved.

## Findings

Low:
1. Refusals in `assure_run` raise `LifecycleError` (exit 1), so a caller cannot tell a refusal from a FAILED run by exit code. R9's exit 2 is worded for `assure` and `assure --changed`, so this is arguably within spec. Use exit 2 or document the difference.
2. `--run` with `--changed` silently ignores `--changed`, `--base`, `--strict` and `--json`. Suggest rejecting the combination with exit 2.

Note:
- `--run` entries carry `runtime_sha256`. Evidence recorded on one machine or Python install shows STALE ("runtime executable changed") elsewhere, for example a committed record read in CI. Conservative and consistent with the spec; consider saying so in `.ai/lifecycle.md`.

## Completeness (AGENTS.md §8.1)

No stubs, TODOs or deferred behavior on the critical path. Tests assert statuses, reasons, ledger entry contents and tree/state immutability. The `--run` path is exercised through the real CLI.

## OKF sync

Framework source has no `knowledge/`. Documentation is in `.ai/lifecycle.md` with a conformance test. No log entry applies.
