---
name: csharp-principal-engineer
description: C# and .NET pitfalls, validation commands, and review checklist; load for C# work.
applies_to:
  - implementation
  - code-review
  - architecture
  - debugging
---

# C# Persona

Language-specific deltas only. General behavior, precedence, and scope rules live in `AGENTS.md` §2.

## Repository first

- Read the `.sln`/`.csproj` files, `Directory.Build.props`, `global.json`, `.editorconfig`, analyzers, and `Nullable`/`LangVersion` settings before choosing patterns. Follow the existing DI, logging, options, and test-framework conventions.

## Pitfalls to check

- **Async:** `.Result`/`.Wait()`/`GetAwaiter().GetResult()` (deadlocks, thread-pool starvation); `async void` outside event handlers; missing `CancellationToken` propagation; fire-and-forget tasks with unobserved exceptions; `Task.Run` wrapping already-async work; `ConfigureAwait` policy inconsistent with the project type (library vs. app).
- **Disposal:** `IDisposable`/`IAsyncDisposable` not in `using`/`await using`; `HttpClient` created per request (use `IHttpClientFactory`); event handlers never unsubscribed.
- **DI:** captive dependencies (singleton holding scoped/transient); service locator calls; `new` of services that belong in the container; `DbContext` shared across threads.
- **Nullability:** `!` suppression hiding a real contract gap; nullable warnings silenced; nullability of public API changed silently.
- **EF Core:** N+1 and client-side evaluation; tracking where `AsNoTracking` fits; unbounded queries; migrations editing already-applied history; transactions spanning external calls.
- **Exceptions:** `catch (Exception)` without rethrow via `throw;` (not `throw ex;`); exceptions for control flow; leaking internals through API responses.
- **Concurrency:** `lock` held across `await`; shared mutable state in singletons; non-thread-safe collections.
- **Time/money:** `DateTime.Now`/unspecified kind (use `DateTimeOffset`/`TimeProvider`); `double` for currency (use `decimal`).
- **API/serialization:** public contract or JSON shape changes; model binding over-posting; `System.Text.Json` vs. `Newtonsoft` mixed.
- **Security:** string-built SQL; secrets in config/logs; missing authorization on new endpoints.

## Tests

- Test behavior through public APIs; fakes over mocks; real database (e.g., containers/in-memory provider chosen deliberately) for query behavior.
- A bug fix gets a regression test that fails before the fix.

## Validation commands

Use the repo's own. Typical: `dotnet build -warnaserror`, `dotnet test`, `dotnet format --verify-no-changes`.

## Review checklist

- Async end to end, cancellation propagated, no sync-over-async.
- Disposables and HTTP clients managed correctly; DI lifetimes valid.
- Nullable contracts honest; EF queries bounded and efficient.
- Public API/serialization compatibility preserved.
- Analyzer/warning policy respected; diff contains no unrelated edits.
