---
name: go-principal-engineer
description: Go pitfalls, validation commands, and review checklist; load for Go work.
applies_to:
  - implementation
  - code-review
  - architecture
  - debugging
---

# Go Persona

Language-specific deltas only. General behavior, precedence, and scope rules live in `AGENTS.md` §2.

## Repository first

- Read `go.mod` (Go version, module path), `Makefile`/CI, and `.golangci.yml` before choosing tools. Follow existing package layout, error, logging, and config conventions; do not add a competing framework.

## Pitfalls to check

- **Errors:** dropped errors; `%v` where `%w` is needed; string matching instead of `errors.Is`/`errors.As`; logging and returning the same error; `panic` for expected failures.
- **Context:** `context.Context` not first parameter, not propagated, stored in structs, or replaced with `context.Background()` mid-call-chain; missing `cancel` defers.
- **Goroutines:** no owner or exit path; unbounded fan-out; loop-variable capture (pre-1.22 modules); sends on channels with no receiver; `WaitGroup.Add` inside the goroutine; `sync.Mutex` copied by value.
- **Resources:** `resp.Body` not closed/drained; `defer` in loops; `http.DefaultClient`/no timeout; `time.After` leaking in loops; rows/files not closed.
- **Interfaces:** declared on the producer side or "just in case"; accept interfaces, return concrete types; no giant interfaces for mocking.
- **Nil and zero values:** typed-nil in interface values; maps written before `make`; slice aliasing after `append`; returning internal slices/maps without copy.
- **HTTP/API:** handlers writing after error response; no request size limits; leaking internal errors to clients.
- **Concurrency changes** require `go test -race`.
- **Dependencies:** new modules for trivial helpers; `go.sum` drift.

## Tests

- Table-driven where cases share setup; separate named tests otherwise. Use `t.Helper`, `t.Cleanup`, `t.TempDir`, `t.Parallel` deliberately.
- Fakes over mocks; integration tests for SQL, handlers, serialization.
- Do not assert on incidental error text; assert with `errors.Is`/`As`.
- A bug fix gets a regression test that fails before the fix.

## Validation commands

Use the repo's own. Typical: `gofmt -l .`, `go vet ./...`, `go test ./...`, `go test -race ./...`, `golangci-lint run`.

## Review checklist

- Errors wrapped once, classified, never dropped.
- Context propagated; every goroutine bounded, cancellable, and owned.
- Bodies/files/rows closed; timeouts set.
- Interfaces small and consumer-defined.
- Race detector run for concurrency changes.
- Diff contains no unrelated edits.
