---
name: python-principal-engineer
description: Python pitfalls, validation commands, and review checklist; load for Python work.
applies_to:
  - implementation
  - code-review
  - architecture
  - debugging
---

# Python Persona

Language-specific deltas only. General behavior, precedence, and scope rules live in `AGENTS.md` §2.

## Repository first

- Read `pyproject.toml` (or `setup.cfg`/`tox.ini`/`noxfile.py`) and CI config before choosing tools. Use the repo's package manager, formatter, type checker, and Python floor; do not introduce a second one.
- Match the existing async model (asyncio/trio/sync), error style, and test layout.

## Pitfalls to check

- **Mutable defaults and shared state:** mutable default arguments, module-level singletons mutated at import time, class-level mutable attributes.
- **Exceptions:** bare/broad `except`, swallowed errors, `raise X` without `from error` when translating, catching `CancelledError` (or `BaseException`) without re-raising, logging and re-raising at every layer.
- **Async:** blocking calls (file/network/CPU, `time.sleep`, sync DB drivers) inside `async def`; fire-and-forget `create_task` with no reference or error handling; unbounded `gather`; missing timeouts; sync/async API duplication.
- **Resources:** files, sockets, sessions, and locks not in `with`/`async with`; subprocesses without timeout, `check`, or explicit `shell=False`.
- **Types:** `Any`/`cast`/`# type: ignore` hiding a real contract gap; runtime validation missing at trust boundaries (request bodies, env, files, third-party payloads) since annotations are not enforced.
- **Time and money:** naive datetimes, local-time arithmetic, `float` for currency (use `Decimal` or integer minor units).
- **Serialization:** `pickle`/`yaml.load`/`eval` on untrusted input; dict-shaped contracts with no schema.
- **Compatibility:** syntax or stdlib features newer than the project's minimum Python.
- **Packaging:** unpinned or undeclared dependencies; imports of transitive dependencies; import-time side effects.
- **Security:** string-built SQL/shell/paths; secrets in logs or exceptions; `assert` used for validation (stripped under `-O`).

## Tests

- Test behavior through public interfaces; prefer fakes over mocks for I/O boundaries; use real integration tests for SQL, HTTP handlers, and serialization.
- A bug fix gets a regression test that fails before the fix.
- Mark async tests per the repo's plugin (`pytest-asyncio`/`anyio`); do not leave un-awaited coroutines.

## Validation commands

Use the repo's own. Typical: `python -m pytest`, `python -m mypy .` or `pyright`, `python -m ruff check .`, `python -m ruff format --check .`; packages also `python -m build` and `twine check dist/*`.

## Review checklist

- Failure paths and cancellation handled deliberately.
- No blocking work on the event loop; tasks owned and bounded.
- Resources closed on every path.
- Public types precise; boundaries validated.
- No dependency, config, or interpreter-version change without need.
- Tests assert behavior and would fail without the change.
- Diff contains no unrelated edits.
