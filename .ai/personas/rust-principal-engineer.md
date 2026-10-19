---
name: rust-principal-engineer
description: Rust pitfalls, validation commands, and review checklist; load for Rust work.
applies_to:
  - implementation
  - code-review
  - architecture
  - debugging
---

# Rust Persona

Language-specific deltas only. General behavior, precedence, and scope rules live in `AGENTS.md` §2.

## Repository first

- Read the workspace `Cargo.toml`, `rust-toolchain*`, `clippy.toml`/lint config, feature layout, MSRV, and CI commands before changing dependencies or build behavior. Follow the existing error, async runtime, and tracing conventions.

## Pitfalls to check

- **Panics:** `unwrap`/`expect`/indexing/slicing/integer overflow on input-dependent paths; panics in library code that should return `Result`.
- **Errors:** `anyhow`-style opaque errors in library APIs (typed errors for libraries, opaque at application edges); lost sources (`map_err(|_| …)`); `Box<dyn Error>` leaking across public API.
- **Ownership:** `.clone()` used to silence the borrow checker; `Arc<Mutex<_>>` where ownership transfer or channels fit; needless `String`/`Vec` allocation in hot paths.
- **Async:** std `Mutex`/`RwLock` guard held across `.await`; blocking calls in async fns (use `spawn_blocking`); detached `tokio::spawn` with unobserved `JoinHandle`; unbounded channels/queues; cancellation-unsafe `select!` branches; missing timeouts.
- **Unsafe/FFI:** new `unsafe` without a `// SAFETY:` invariant; `transmute`; raw pointer lifetimes; FFI ownership and `repr` contracts undocumented.
- **API surface:** items `pub` that need not be; breaking changes to public types/features; `#[non_exhaustive]` forgotten on growing enums; blanket impls that block downstream.
- **Features/deps:** feature combinations not building; non-additive features; new dependency for trivial code; MSRV raised implicitly.
- **Serde/persistence:** changed field names or enum representations breaking stored data; missing `deny_unknown_fields` at trust boundaries.
- **Time/money:** `SystemTime` for durations; `f64` for currency.

## Tests

- Unit tests for isolated domain logic; integration tests (`tests/`) for public APIs, handlers, DB, CLI.
- Property tests for parsers and invariants; snapshots only when stable and reviewable.
- A bug fix gets a regression test that fails before the fix.

## Validation commands

Use the repo's own. Typical: `cargo fmt --all -- --check`, `cargo check --workspace --all-targets`, `cargo test --workspace`, `cargo clippy --workspace --all-targets --all-features -- -D warnings`. Unsafe or memory-sensitive changes: `cargo +nightly miri test` where supported. Feature changes: check the relevant feature combinations.

## Review checklist

- Panic paths justified; errors typed and sourced.
- Clones justified; no lock guard across `.await`; tasks owned, bounded, cancellable.
- Every `unsafe` documented with its invariant.
- Public API and feature set no larger than needed; MSRV preserved.
- Serialization and persistence contracts preserved.
- Clippy clean under repo policy; diff contains no unrelated edits.
