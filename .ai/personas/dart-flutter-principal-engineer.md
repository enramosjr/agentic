---
name: dart-flutter-principal-engineer
description: Dart and Flutter pitfalls, validation commands, and review checklist; load for Dart/Flutter work.
applies_to:
  - implementation
  - code-review
  - architecture
  - debugging
---

# Dart / Flutter Persona

Language-specific deltas only. General behavior, precedence, and scope rules live in `AGENTS.md` §2.

## Repository first

- Read `pubspec.yaml` (SDK/Flutter constraints, dependencies), `analysis_options.yaml`, and CI before choosing tools. Follow the existing state-management approach (Provider/Riverpod/Bloc/etc.), navigation, DI, and folder structure; do not introduce a second one.

## Pitfalls to check

- **Lifecycle:** using `BuildContext` after an `await` without `mounted` checks; controllers, `StreamSubscription`s, timers, and focus nodes not disposed; work started in `build()`.
- **Rebuilds:** state placed too high so large subtrees rebuild; missing `const` constructors; expensive computation or allocation in `build()`; unstable keys in lists; `setState` after dispose.
- **State:** business logic in widgets; mutable state shared across widgets without an owner; mixing state-management approaches.
- **Async:** un-awaited futures (`unawaited_futures` lint), unhandled stream errors, missing cancellation/debounce for user-driven requests, isolates not used for heavy CPU work.
- **Null safety:** `!` and `late` hiding real initialization gaps; `dynamic` leaking from JSON.
- **Serialization:** hand-rolled `fromJson` without validation; generated code (`build_runner`) not regenerated or committed per repo policy.
- **Platform:** platform-channel and plugin changes missing iOS/Android/web handling; platform-specific code in shared layers; permissions and manifest/Info.plist entries.
- **UI quality:** missing semantics/accessibility labels, text scaling, and overflow handling; hard-coded sizes and strings where theming/localization exists.
- **Performance:** large lists without lazy builders; images not sized/cached; animations rebuilding whole trees.
- **Security:** secrets in source or assets; sensitive data in logs or insecure storage.

## Tests

- Unit tests for logic; widget tests for behavior and states (loading, error, empty); integration tests for critical flows. Prefer fakes over mocks; avoid golden tests unless the repo already maintains them.
- A bug fix gets a regression test that fails before the fix.

## Validation commands

Use the repo's own. Typical: `dart format --set-exit-if-changed .`, `flutter analyze` (or `dart analyze`), `flutter test`; `dart run build_runner build` when generated code is involved.

## Review checklist

- Context never used across async gaps unguarded; everything disposable disposed.
- Rebuild scope small; no work in `build()`.
- State owned in one place using the repo's approach.
- Platform/accessibility/localization implications handled.
- Analyzer clean, tests pass; diff contains no unrelated edits.
