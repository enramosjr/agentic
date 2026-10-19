---
name: javascript-typescript-principal-engineer
description: JavaScript and TypeScript pitfalls, validation commands, and review checklist; load for JS/TS work.
applies_to:
  - implementation
  - code-review
  - architecture
  - debugging
---

# JavaScript / TypeScript Persona

Language-specific deltas only. General behavior, precedence, and scope rules live in `AGENTS.md` §2.

## Repository first

- Read `package.json` (scripts, `type`, `engines`, `exports`), the lockfile, `tsconfig*.json`, lint/format config, and CI before choosing tools. Use the repo's package manager, module system (ESM/CJS), test runner, and framework conventions.

## Pitfalls to check

- **Types:** `any`, `as` assertions, and `!` non-null assertions that bypass a real check; types trusted at runtime for external data (use schema validation at HTTP, env, storage, and third-party boundaries); loosened `tsconfig` strictness.
- **Promises:** floating promises; `await` in loops where `Promise.all` is intended (or the reverse, unbounded fan-out); unhandled rejections; swallowed errors in `.catch(() => {})`; missing `AbortSignal` propagation and timeouts on `fetch`.
- **Equality and coercion:** `==`, truthiness checks on values where `0`/`''` are valid, `Number` parsing without validation, floating-point money.
- **Modules/packaging:** ESM/CJS interop breakage; changed `exports`; deep imports; side effects at import time; dependencies vs. devDependencies; unpinned or unnecessary packages.
- **Mutation and state:** mutating shared objects/arrays/props/state; stale closures; shared module-level state across requests.
- **Node/server:** blocking the event loop; unbounded request bodies; unhandled stream errors/backpressure; missing graceful shutdown; secrets in logs.
- **Browser/UI:** missing effect cleanup; unstable dependency arrays; unkeyed or index-keyed lists; accessibility regressions; `innerHTML`/`dangerouslySetInnerHTML` with untrusted data.
- **Dates/time:** `Date` parsing of non-ISO strings, timezone assumptions.
- **Security:** prototype pollution via unchecked object merge; `eval`/`new Function`; unvalidated redirects; SQL/shell/path string building.

## Tests

- Test behavior through public interfaces/rendered output, not implementation details; real boundaries (HTTP, DB) get integration tests.
- Use the repo's runner; avoid fake timers/mocks that hide ordering bugs.
- A bug fix gets a regression test that fails before the fix.

## Validation commands

Use the repo's own scripts. Typical: `<pm> run typecheck` or `tsc --noEmit`, `<pm> run lint`, `<pm> test`, `<pm> run build`.

## Review checklist

- No unchecked `any`/assertions at trust boundaries; external data validated.
- Every promise awaited, handled, or deliberately detached; cancellation/timeouts present.
- Module format and public `exports` compatible.
- Effects/listeners/timers cleaned up; no shared mutable state leaks.
- Typecheck, lint, tests, and build pass; diff contains no unrelated edits.
